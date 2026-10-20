"""Idempotent IMAI RestoOS demo catalog import into isolated Satisfecho staging only."""
import csv, sys, shutil
from pathlib import Path
from sqlmodel import Session, select
from app.db import engine
from app import models
from app.security import get_password_hash
from app.tenant_ui_modules import new_tenant_ui_modules_stored
DEMO_NAME = "Restoran IMAI Demo"
OWNER_EMAIL = "owner@restoos.imai.my"
root = Path("/app/uploads/_import")
assert root.joinpath("menu.csv").exists() and root.joinpath("tables.csv").exists()
pwd = sys.stdin.readline().strip()
if len(pwd) < 12: raise SystemExit("Demo credential input missing")
with Session(engine) as session:
    tenant = session.exec(select(models.Tenant).where(models.Tenant.name == DEMO_NAME)).first()
    if tenant is None:
        tenant = models.Tenant(name=DEMO_NAME, currency_code="MYR", currency="RM",
            country_code="MY", timezone="Asia/Kuala_Lumpur", default_language="en",
            city="Johor Bahru", ui_modules=new_tenant_ui_modules_stored())
        session.add(tenant); session.commit(); session.refresh(tenant)
        print("CREATED demo restaurant tenant:", tenant.id)
    else: print("EXISTING demo restaurant tenant:", tenant.id)
    owner = session.exec(select(models.User).where(models.User.email == OWNER_EMAIL)).first()
    if owner is None:
        owner = models.User(email=OWNER_EMAIL, hashed_password=get_password_hash(pwd),
            full_name="IMAI Demo Owner", tenant_id=tenant.id, role=models.UserRole.owner)
        session.add(owner); session.commit(); print("CREATED demo owner account")
    else: print("EXISTING demo owner preserved")
    with root.joinpath("menu.csv").open(newline="") as src:
        for row in csv.DictReader(src):
            exists = session.exec(select(models.Product).where(models.Product.tenant_id == tenant.id, models.Product.name == row["name"])).first()
            if exists: continue
            filename = Path(row["image_url"]).name if row.get("image_url") else None
            if filename:
                original = root / filename
                if not original.is_file(): raise RuntimeError("Missing image: " + filename)
                target = Path("/app/uploads") / str(tenant.id) / "products"
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target / filename)
            session.add(models.Product(tenant_id=tenant.id,name=row["name"],
                price_cents=int(row["price_cents"]),description=row["description"],
                category=row["category"],image_filename=filename))
    with root.joinpath("tables.csv").open(newline="") as src:
        for row in csv.DictReader(src):
            name = "Meja " + row["code"]
            exists = session.exec(select(models.Table).where(models.Table.tenant_id == tenant.id,models.Table.name == name)).first()
            if not exists:
                session.add(models.Table(tenant_id=tenant.id,name=name,seat_count=int(row["seats"])))
    session.commit()
    print("VERIFIED counts", "products",len(session.exec(select(models.Product).where(models.Product.tenant_id==tenant.id)).all()),
        "tables",len(session.exec(select(models.Table).where(models.Table.tenant_id==tenant.id)).all()))
print("NOTE: historic order/payment rows are archived in original database, not imported.")
