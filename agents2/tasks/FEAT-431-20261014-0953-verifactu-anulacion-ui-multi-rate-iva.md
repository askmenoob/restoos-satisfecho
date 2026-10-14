# VeriFactu: staff anulación UI + multi-rate IVA (#431)

## GitHub Issues
- **Issue:** https://github.com/satisfecho/pos/issues/431
- **431**

## Problem / goal
Status/gap audit for VeriFactu is **done** (archived `CLOSED-431-20261014-0937-verifactu-status.md`; docs gap table in `docs/0065-verifactu-production.md`). Human follow-up on the issue asks to **implement** the two product next-FEAT items:

1. **Staff UI for anulación** — API `POST …/fiscal-invoice/cancel` and Angular `cancelOrderFiscalInvoice` exist; no dedicated staff control yet. Delete/edit stay blocked with **409** until cancel runs.
2. **Multi-rate IVA / full line-item Fiskaly mapping** — SIGN ES adapter still uses a simplified single-line **21%** invoice; need real line items and multi-rate IVA.

Do **not** re-run the status audit. Do **not** enable live remisión / `FISCAL_LIVE_UNLOCK` or invent vendor credentials. Ops/legal gaps stay out of scope.

## High-level instructions for coder
- Read **`docs/0018-verifactu-fiscal-invoicing.md`**, **`docs/0065-verifactu-production.md`** (*Remaining gaps*), and **`docs/0074-fiscal-certified-middleware.md`**. Reuse existing cancel API + client; extend Fiskaly adapter mapping carefully.
- **Priority 1 — Staff anulación UI:** On orders (Factura / fiscal-aware surfaces), add a clear control to cancel (anulación) when an active alta exists. Wire to `cancelOrderFiscalInvoice`. Surface success (anulación number) and errors; after cancel, delete/edit should work again. i18n for new strings (en/es/de). Keep ES/`fiscal_mode` gating consistent with Settings.
- **Priority 2 — Multi-rate / line items:** Map order lines (and correct IVA rates) into the Fiskaly SIGN ES payload instead of one hardcoded 21% line. Align with product tax fields already on lines; keep mock/test adapters coherent. Extend or add pytest coverage in `tests/test_fiscal_invoice_api.py` (and provider unit tests if they exist).
- Update **`docs/0065`** / **`docs/0018`** so the gap rows for anulación UI and payload fidelity match what shipped.
- Out of scope: commercial Fiskaly credentials, live unlock, SIF declaración responsable, TSE.
- Smoke: fiscal issue in `test` mode → anulación via new UI → delete/edit allowed; multi-rate fixture if available; front build clean in `docker logs --since 10m pos-front`. Never put secrets into the task or GitHub comments.
