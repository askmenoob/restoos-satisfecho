# VeriFactu: staff anulación UI + multi-rate IVA (#431)

## GitHub Issues
- **Issue:** https://github.com/satisfecho/pos/issues/431
- **431**

## Status
- **Implemented:** 2026-10-14T10:00:00Z (agent 010)
- Staff anulación control on Orders (Print Factura + Edit order) when `fiscal_mode` is test/live and an active alta exists.
- Fiskaly SIGN ES / request_payload now carry multi-rate `line_items` from order tax snapshots.

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

## What changed
- **Front:** Orders Factura modal + Edit order show **Cancel fiscal invoice (anulación)** when an active alta is loaded; confirm → `cancelOrderFiscalInvoice`; success toast with anulación number; i18n en/es/de (+ other locales).
- **Back:** `build_fiscal_line_items` → `request_payload.line_items`; Fiskaly SIGN ES uses per-line IVA rates (fallback single 21% if lines missing); anulación reuses alta line items.
- **Tests:** `test_issue_stores_multi_rate_line_items`, `test_fiskaly_items_from_line_items_multi_rate` in `back/tests/test_fiscal_invoice_api.py` (10 passed).
- **Docs:** `docs/0018`, `docs/0065` gap rows updated for UI + payload fidelity.

## Testing instructions

1. **Prereq:** Tenant Settings → fiscal mode **test** (country ES / fiscal block visible). App up (e.g. HAProxy host port).
2. **Issue:** Create/pay an order → Orders → Print Factura (or Edit → Print invoice). Expect fiscal number + QR block.
3. **Immutability:** Try delete or edit line quantity on that order → expect **409** / blocked toast.
4. **Anulación UI:** Re-open Factura or Edit order → see **Cancel fiscal invoice (anulación)** with the alta number → confirm → toast with cancellation number (e.g. `…-C…`).
5. **After cancel:** Delete or edit the order should succeed.
6. **Multi-rate (API/pytest):** `docker compose exec back python3 -m pytest tests/test_fiscal_invoice_api.py -q` — expect pass including multi-rate line_items (10% + 21%).
7. **Front build:** `docker logs --since 10m pos-front` — no TS/NG compile errors after Orders changes.
8. **Out of scope / do not:** Do not set `FISCAL_LIVE_UNLOCK` or add real Fiskaly credentials for this test.
