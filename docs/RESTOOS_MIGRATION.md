# IMAI RestoOS V2 — Satisfecho POS migration

## Source and license
- Upstream: https://github.com/satisfecho/pos (GNU AGPL-3.0).
- Licensed fork: https://github.com/askmenoob/restoos-satisfecho (public; retains LICENSE, upstream attribution, full original source).
- Preserve license, copyright, attribution and network users' right to obtain modified corresponding source. RestoOS fork source URL appears in the marketing footer.

## Infrastructure (20 Oct 2026)
- Existing app: https://restoos.imai.my, code /mnt/data/projects/imai-restoos, port 127.0.0.1:4462. Do not delete this stack.
- Upstream-based staging: https://restoos-v2.imai.my, code /mnt/data/projects/restoos-satisfecho, port 127.0.0.1:4472.
- Isolated Docker Compose project restoos-satisfecho with Angular static frontend, FastAPI, PostgreSQL 18, Redis, WebSocket bridge and standalone Cloudflare tunnel.
- Database volume and Docker network separate from existing RestoOS and /mnt/data/projects/mejalah (whose containers are named pos-*).
- Deployment configuration: docker-compose.yml plus docker-compose.restoos.yml, private config.env (gitignored).
- The upstream FastAPI bootstrap on a fresh PostgreSQL needs user_role and staff-contract ENUM types before SQLModel.create_all. Included ops/20-bootstrap-enums.sql as an initdb-only compatibility shim. Existing staging DB received it once and ran 118 versioned migrations.
- Production-mode FastAPI is enabled on staging with HTTPS origin allowlist, strong random signing/database credentials. Payment provider keys are not configured.

## Legacy data snapshot and staged import
- Original database backup: /mnt/data/projects/restoos-migration-backups/imai-restoos-pre-satisfecho-20261020.dump, pg_restore --list verified.
- Original database counts at import: 1 restaurant, 5 users, 10 menu items, 12 tables, 12 orders, 7 payments and 7 table sessions.
- Staging: 1 demo tenant, 1 owner account, 10 products with actual WebP dish photos, 12 tables, MYR currency and Asia/Kuala_Lumpur timezone.
- Only demo catalog/tables/owner have been imported, not historical orders, payments or previous 4 staff accounts. Those remain preserved in original PostgreSQL and backup.
- The owner staging password was securely reused from legacy demo environment, never written into the repository.
- Stage importer is back/restoos_legacy_import.py, idempotent for tenant, products and tables. Legacy CSVs and photographs are under back/uploads/_import/ (ignored).
- Source photo author/license records: docs/RESTOOS_IMAGE_CREDITS.md, and public /restoos-photo-credits.html.

## Verified
- Full Angular production build from Satisfecho source, FastAPI/PostgreSQL Redis/WebSocket startup.
- Endpoint /api/health: HTTP 200 on localhost and HTTPS preview domain.
- Browser load: public landing, register, login, pricing; zero browser JS errors in tested routes.
- Owner login: dashboard loaded; Products, Tables, Kitchen and Reports routes respond 200.
- Customer QR (demo Meja 01): menu shows MYR prices, photographs and names, no JS errors.
- Original https://restoos.imai.my /api/health stays 200 and old containers remain healthy.

## Not verified — no main domain swap yet
- Kitchen-to-payment end-to-end workflow must be completed using V2 order engine.
- User/role parity: only demo owner migrated; waiter/kitchen/cashier/super-admin need explicit V2 role mapping.
- Historical order and payment migration mapping, totals and traceability are still missing.
- Merchant MY payment gateway support and MyInvois compliance not configured.
- Malay UI translations, custom legal/privacy policies, tenant self-service billing and source-specific security review remain.
- Owner must approve operational go-live and any production cutover that could change current active users' sessions. Existing V1 remains the rollback.

## Operations
- Stage status: docker compose -p restoos-satisfecho --env-file config.env -f docker-compose.yml -f docker-compose.restoos.yml ps
- Stage boot: docker compose -p restoos-satisfecho --env-file config.env -f docker-compose.yml -f docker-compose.restoos.yml up -d db redis back ws-bridge front tunnel
- Stage API health: curl -fsS https://restoos-v2.imai.my/api/health
- Stage logs: docker logs --tail=100 restoos-satisfecho-back
- If a future cutover fails, restore original Cloudflare tunnel's origin to http://127.0.0.1:4462 and restart only the original RestoOS tunnel. Do not restore the old DB over the Satisfecho DB.

## Verified 2026-10-20 23:30 MYT
- Fresh --dry-run passed on staging target tenant 1, source 5 staff, 12 tables, 7 sessions, 12 orders, 15 items and 7 original payments.
- --verify passed on persisted target: 5 migrated staff, 12 preserved QR table tokens, 12 orders, 15 items, 12 allocated receipt legs, RM239.20 order and payment totals.
- Playwright staging_role_uat.mjs passed Owner (Products/Tables/Kitchen/Reports), Waiter (Tables/Orders), Kitchen, Cashier (Orders).
- Both HTTPS health endpoints returned HTTP 200; existing V1 stayed healthy and untouched.
- V2 payment provider Malaysia, MyInvois, cash reconciliation, old QR URL redirects and cutover test still NOT verified. Do not claim production cutover.
- Stage credentials private under ignored back/uploads/_import/legacy-staff-temp-credentials.json. Never commit them.
