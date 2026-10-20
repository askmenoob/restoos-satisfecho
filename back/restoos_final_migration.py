"""Transactional, idempotent IMAI RestoOS V1 -> Satisfecho V2 staging importer.

Input: /app/uploads/_import/legacy-export.json (private, generated from a fresh V1 database backup).
Usage: python restoos_final_migration.py --dry-run|--apply|--verify
When applying, generate independent strong one-time stage credentials (never copy old credentials).
Do not run against production before comparing backups, grants and database target.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import os
import sys

from sqlalchemy import text
from sqlmodel import Session, select
from app.db import engine
from app import models
from app.security import get_password_hash

parser = argparse.ArgumentParser()
pgroup=parser.add_mutually_exclusive_group(required=True)
pgroup.add_argument('--dry-run', action='store_true')
pgroup.add_argument('--apply', action='store_true')
pgroup.add_argument('--verify', action='store_true')
args=parser.parse_args()
export_path=Path('/app/uploads/_import/legacy-export.json')
if not export_path.is_file():
    raise SystemExit('Private V1 export missing')
data=json.loads(export_path.read_text())
tenant_name='Restoran IMAI Demo'

def iso(s):
    if s is None:return None
    if isinstance(s,datetime):return s
    return datetime.fromisoformat(s.replace('Z','+00:00'))

def row_index(key):
    return {str(r['id']):r for r in data[key]}

staff=row_index('staff')
tables=row_index('tables')
sessions=row_index('sessions')
orders=sorted(data['orders'],key=lambda r:(r['created_at'],r['id']))
order_items=data['order_items']
payments=sorted(data['payments'],key=lambda r:(r['created_at'],r['id']))
by_session_orders=defaultdict(list)
by_session_payments=defaultdict(list)
by_order_items=defaultdict(list)
for o in orders:by_session_orders[str(o['session_id'])].append(o)
for p in payments:by_session_payments[str(p['session_id'])].append(p)
for i in order_items:by_order_items[str(i['order_id'])].append(i)

assert len(data['staff'])>=5, 'Expected legacy staff'
assert len(tables)==12,'Table export mismatch'
assert len(orders)==12 and len(order_items)==15 and len(payments)==7,'Unexpected V1 snapshot changed; review source before rerun'
assert all(str(s['status'])=='CLOSED' for s in sessions.values()),'Open legacy table sessions require manual reconciliation'
for sid,old_orders in by_session_orders.items():
    owed=sum(int(o['total_cents']) for o in old_orders)
    paid=sum(int(p['amount_cents']) for p in by_session_payments[sid])
    assert owed==paid,(sid,'unbalanced session',owed,paid)
for o in orders:
    items=by_order_items[str(o['id'])]
    assert items and sum(int(i['price_cents'])*int(i['quantity']) for i in items)==int(o['total_cents']),str(o['id'])
expected_total=sum(int(o['total_cents']) for o in orders)
assert expected_total==sum(int(p['amount_cents']) for p in payments)
assert expected_total==23920, 'Source snapshot differs from verified V1 baseline'
print('V1_EXPORT_VALID',{'staff':len(staff),'tables':len(tables),'sessions':len(sessions),'orders':len(orders),'items':len(order_items),'payments':len(payments),'value_cents':expected_total},flush=True)

role_map={
 'OWNER':models.UserRole.owner,
 'WAITER':models.UserRole.waiter,
 'KITCHEN':models.UserRole.kitchen,
 'CASHIER':models.UserRole.waiter,  # upstream waiter has ORDER_MARK_PAID, not a distinct cashier permission role
 'SUPER_ADMIN':models.UserRole.platform_operator
}
with Session(engine) as session:
    tenant=session.exec(select(models.Tenant).where(models.Tenant.name==tenant_name)).first()
    assert tenant and tenant.currency_code=='MYR' and tenant.timezone=='Asia/Kuala_Lumpur','Unexpected target; refusing import'
    assert tenant.id==1,'Unexpected target tenant id'
    products={p.name:p for p in session.exec(select(models.Product).where(models.Product.tenant_id==tenant.id)).all()}
    stage_tables={t.name:t for t in session.exec(select(models.Table).where(models.Table.tenant_id==tenant.id)).all()}
    assert len(products)==10 and len(stage_tables)==12,'Incomplete staging catalog/tables'
    assert all(any(t['code'] in name for name in stage_tables) for t in tables.values())
    for r in order_items:
        assert r['name_snapshot'] in products,'Legacy product missing: '+r['name_snapshot']
    if args.dry_run:
        print('DRY_RUN_PASS','target_tenant='+str(tenant.id),'legacy_total_cents='+str(expected_total),'staging_user_count='+str(len(session.exec(select(models.User)).all())))
        sys.exit(0)
    if args.apply:
        creds_file=Path('/app/uploads/_import/legacy-staff-temp-credentials.json')
        temp_creds=json.loads(creds_file.read_text()) if creds_file.is_file() else {}
        needs_creds=any(u['email'].lower() not in temp_creds for u in staff.values())
        if needs_creds:
            for legacy in staff.values():
                temp_creds.setdefault(legacy['email'].lower(),secrets.token_urlsafe(24))
            fd=os.open(str(creds_file),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:json.dump(temp_creds,f)
            os.chmod(creds_file,0o600)
        assert all(len(x)>=24 for x in temp_creds.values())
        print('TEMP_CREDENTIALS_SECURED_ON_SERVER',str(creds_file),flush=True)
        # Independent audit mapping: native POS tables hold operational history, mapping holds immutable legacy identifiers/statuses.
        session.exec(text("""CREATE TABLE IF NOT EXISTS restoos_legacy_order_map(
            legacy_order_id UUID PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES tenant(id),
            satis_order_id INTEGER NOT NULL UNIQUE REFERENCES "order"(id),
            legacy_session_id UUID NOT NULL,
            legacy_source TEXT NOT NULL,
            legacy_status TEXT NOT NULL,
            legacy_created_at TIMESTAMPTZ NOT NULL,
            migrated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )"""))
        session.exec(text("""CREATE TABLE IF NOT EXISTS restoos_legacy_payment_map(
            id BIGSERIAL PRIMARY KEY,
            legacy_payment_id UUID NOT NULL,
            legacy_order_id UUID NOT NULL REFERENCES restoos_legacy_order_map(legacy_order_id),
            satis_order_payment_id INTEGER NOT NULL UNIQUE REFERENCES order_payment(id),
            amount_cents INTEGER NOT NULL CHECK(amount_cents>0)
        )"""))
        # Create users with Satisfecho-compatible hashes, preserve original email/role mapping.
        stage_users={}
        for old in staff.values():
            email=old['email'].strip().lower()
            existing=session.exec(select(models.User).where(models.User.email==email)).first()
            if existing is None:
                existing=models.User(email=email,hashed_password=get_password_hash(temp_creds[email]),
                    full_name=old['name'],tenant_id=None if old['role']=='SUPER_ADMIN' else tenant.id,
                    role=role_map[old['role']])
                session.add(existing);session.flush()
                print('STAFF_CREATED',email,role_map[old['role']].value,flush=True)
            else:
                assert existing.role==role_map[old['role']] and (
                    existing.tenant_id==(None if old['role']=='SUPER_ADMIN' else tenant.id)
                ),'Conflicting account '+email
            stage_users[str(old['id'])]=existing.id
        # Preserve existing physical-table QR tokens; no source sessions are active.
        old_code_to_stage={}
        for old in tables.values():
            name='Meja '+old['code']
            stage=stage_tables[name]
            token=str(old['table_token'])
            if stage.token!=token:
                duplicate=session.exec(select(models.Table).where(models.Table.token==token)).first()
                assert duplicate is None, 'QR token collision '+name
                stage.token=token
                session.add(stage)
            old_code_to_stage[str(old['id'])]=stage
        session.flush()
        # Retain historical accounting as native paid orders and payment legs, with original UUID mapping.
        imported=0
        for old in orders:
            oid=str(old['id'])
            mapped=session.exec(text('SELECT satis_order_id FROM restoos_legacy_order_map WHERE legacy_order_id=CAST(:id AS uuid)'),
                params={'id':oid}).first()
            if mapped:
                assert session.get(models.Order,mapped[0]) is not None,'Broken existing migration map'
                continue
            src_session=sessions[str(old['session_id'])]
            table=old_code_to_stage[str(src_session['table_id'])]
            related_payments=by_session_payments[str(old['session_id'])]
            paid_at=max(iso(p['created_at']) for p in related_payments)
            cashier_id=stage_users[str(related_payments[-1]['received_by'])]
            new=models.Order(tenant_id=tenant.id,table_id=table.id,
                status=models.OrderStatus.paid,created_at=iso(old['created_at']),
                session_id=str(old['session_id']),paid_at=paid_at,
                paid_by_user_id=cashier_id,payment_method='cash' if related_payments[-1]['method']=='CASH' else 'other',
                notes='Migrated from IMAI RestoOS V1: '+oid+' (original '+old['status']+'; '+old['source']+')')
            session.add(new);session.flush()
            for item in by_order_items[oid]:
                product=products[item['name_snapshot']]
                session.add(models.OrderItem(order_id=new.id,product_id=product.id,
                    product_name=item['name_snapshot'],quantity=int(item['quantity']),
                    price_cents=int(item['price_cents']),notes=item.get('note') or None,
                    status=models.OrderItemStatus.delivered, status_updated_at=paid_at))
            session.exec(text("""INSERT INTO restoos_legacy_order_map(
                legacy_order_id,tenant_id,satis_order_id,legacy_session_id,
                legacy_source,legacy_status,legacy_created_at)
                VALUES(CAST(:old AS uuid),:tenant,:new,CAST(:session AS uuid),:source,:status,:created)"""),
                params=dict(old=oid,tenant=tenant.id,new=new.id,session=old['session_id'],
                     source=old['source'],status=old['status'],created=iso(old['created_at'])))
            imported+=1
        session.flush()
        # Distribute original session-level receipts across the original orders in order order.
        # Payment totals exactly match order totals for every source session.
        new_allocations=0
        for sid,old_orders in by_session_orders.items():
            pay_cursor=[{'row':p,'remaining':int(p['amount_cents'])} for p in by_session_payments[sid]]
            for old in old_orders:
                oid=str(old['id'])
                target=session.exec(text('SELECT satis_order_id FROM restoos_legacy_order_map WHERE legacy_order_id=CAST(:id AS uuid)'),
                    params={'id':oid}).one()[0]
                remain=int(old['total_cents'])
                for pstate in pay_cursor:
                    if remain==0:break
                    pay=pstate['row']
                    # Already mapped legs are counted only when rerunning after a prior complete import.
                    exists=session.exec(text("""SELECT amount_cents FROM restoos_legacy_payment_map
                        WHERE legacy_payment_id=CAST(:payment AS uuid) AND legacy_order_id=CAST(:order AS uuid)"""),
                        params={'payment':pay['id'],'order':oid}).all()
                    if exists:
                        allocated=sum(int(x[0]) for x in exists)
                        remain-=allocated
                        pstate['remaining']-=allocated
                        continue
                    if pstate['remaining']<=0:continue
                    amount=min(remain,pstate['remaining'])
                    if amount<=0:continue
                    method={'CASH':'cash','CARD':'terminal','QR_MANUAL':'other'}[pay['method']]
                    leg=models.OrderPayment(tenant_id=tenant.id,order_id=target,
                        amount_cents=amount,payment_method=method,payer_label='Legacy POS V1',
                        paid_by_user_id=stage_users[str(pay['received_by'])],
                        paid_at=iso(pay['created_at']),
                        note='Migrated, old receipt '+str(pay['id']))
                    session.add(leg);session.flush()
                    session.exec(text("""INSERT INTO restoos_legacy_payment_map(
                        legacy_payment_id, legacy_order_id,satis_order_payment_id,amount_cents)
                        VALUES(CAST(:pid AS uuid),CAST(:oid AS uuid),:new,:amount)"""),
                        params={'pid':pay['id'],'oid':oid,'new':leg.id,'amount':amount})
                    remain-=amount;pstate['remaining']-=amount
                    new_allocations+=1
                assert remain==0,'Cannot reconcile order payment '+oid
            assert all(p['remaining']==0 for p in pay_cursor),'Payments not fully consumed session '+sid
        session.commit()
        print('APPLY_PASS',{'new_orders':imported,'new_payment_legs':new_allocations},flush=True)
    # Verify persisted migration / native ledger and staff.
    maps=session.exec(text("""SELECT count(*) AS n, count(distinct satis_order_id) AS unique_orders
        FROM restoos_legacy_order_map WHERE tenant_id=:tenant"""),params={'tenant':tenant.id}).one()
    native=session.exec(text("""SELECT count(*) AS n, coalesce(sum(i.price_cents*i.quantity),0)::integer AS cents
        FROM restoos_legacy_order_map m JOIN orderitem i ON i.order_id=m.satis_order_id WHERE m.tenant_id=:tenant"""),params={'tenant':tenant.id}).one()
    cash=session.exec(text("""SELECT count(*) AS n,coalesce(sum(p.amount_cents),0)::integer AS cents
        FROM restoos_legacy_payment_map m JOIN order_payment p ON p.id=m.satis_order_payment_id""")).one()
    assert int(maps[0])==len(orders)==int(maps[1])
    assert int(native[1])==int(cash[1])==expected_total
    for old in staff.values():
        existing=session.exec(select(models.User).where(models.User.email==old['email'])).first()
        assert existing is not None and existing.role==role_map[old['role']]
    for old in tables.values():
        assert stage_tables['Meja '+old['code']].token==str(old['table_token'])
    print('VERIFY_PASS',{'staff_migrated':len(staff),'tables_preserved':len(tables),
        'orders':int(maps[0]),'items':int(native[0]),'payment_legs':int(cash[0]),
        'order_value_cents':int(native[1]),'payment_cents':int(cash[1])},flush=True)
