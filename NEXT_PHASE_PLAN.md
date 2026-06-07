# resto — Next Phase Plan

> Written at the close of the UI/UX overhaul phase (`ui-ux-pass`, all gates green). This is the
> prioritized roadmap for what comes next, framed for a senior product + engineering owner.

## 1. Where we are

`resto` is a feature‑complete, production‑hardened, multi‑tenant restaurant SaaS with three live
personas (owner/staff, customer, driver): full tenant provisioning + billing/entitlements, a
production‑grade closed‑loop wallet, the complete order lifecycle (dine‑in / pickup / delivery),
a platform driver app (dispatch, GPS, proof‑of‑delivery, earnings, cash‑out), reservations with
self‑service cancel, an admin console, marketplace/directory, web push + email, and a green CI suite
(~2,700 backend tests). The web frontend has now had a **full UI/UX overhaul** (see
`frontend/UI_UX_OVERHAUL_SUMMARY.md`).

The platform is **ready for real‑world use today**. The next phase is about (a) finishing the UI
polish tail, (b) closing the few remaining operational seams, and (c) the strategic bets that unlock
growth.

## 2. Themes for the next phase

1. **Finish & certify the UI** — complete the polish tail and add the QA we couldn't run via gates.
2. **Payments maturity** — add a real money‑in rail (currently closed‑loop wallet only).
3. **Operational reliability at scale** — turn on the durable async worker; close payout automation.
4. **Growth: multi‑business** — generalize beyond restaurants ("stores").

## 3. Prioritized backlog

| Pri | Item | Why | Effort | Risk |
|---|---|---|---|---|
| **P0** | **Merge `ui-ux-pass` → `main`** after review | Lock in the overhaul; everything else builds on it | S | Low |
| **P0** | **Finish Pass‑2 round‑2 polish** (low‑concurrency, ≤3 agents) | ~40% done; converge to "impeccable"; safe on the laptop | M | Low |
| **P0** | **Visual / RTL screenshot QA** on a live dev server (390px + desktop + Arabic) | Gates don't catch pixel/RTL rendering regressions | M | Low |
| **P1** | **Durable notification worker on Coolify** (Celery + Redis) | Code already exists (`config/celery.py`, `accounts/tasks.enqueue`); needs the worker process + beat. Removes fire‑and‑forget fragility | S–M | Med (deploy topology change) |
| **P1** | **Regenerate the deep‑audit + product‑audit backlogs** (gentle, batched) | Turn the audit lenses into a living, themed backlog | S | Low |
| **P1** | **Stripe as a wallet top‑up funding source** | Real money‑in beyond cash top‑ups; keep the closed‑loop wallet — only add `StripeWebhookView` → existing idempotent `wallet_service.credit` keyed by Stripe event id | M | Med (needs PSP account/keys — owner provides; never commit keys) |
| **P1** | **Automated driver bank‑transfer payouts** | Today cash‑out is in‑person ≥100 MAD; automate via a PSP payout API | M | Med (PSP dependency) |
| **P2** | **Multi‑business "stores" generalization** | Reuse the platform for non‑restaurant shops; `Profile.business_type` + capability flags; vocabulary (Menu→Catalog, Dish→Product). `Order`/`OrderItem`/wallet/delivery/tenancy are already generic | L | High (the `Dish`→`Item` rename crosses every tenant schema via `migrate_schemas` — rehearse on a clone; land last) |
| **P2** | **Design‑system docs refresh** | Update `UI_SYSTEM.md` / `UI_UX_GUIDELINES.md` to match the overhaul; lock conventions for future contributors | S | Low |
| **P2** | **Frontend perf pass** | Route‑level code‑splitting, lazy‑load heavy deps (leaflet), image strategy, bundle audit | M | Low |

## 4. Recommended sequencing

1. **Merge the overhaul** (P0) — review `git diff main...ui-ux-pass`, then merge. Don't let it drift.
2. **Certify the UI** (P0) — finish round‑2 polish + run the visual/RTL QA, in small batches. Ship.
3. **Turn on the worker** (P1) — lowest‑effort reliability win; the code is already written.
4. **Payments** (P1) — Stripe top‑up seam once a PSP account exists; then automated driver payouts.
5. **Stores generalization** (P2) — the big bet; scope it on its own, rehearse the cross‑schema
   rename on a clone, land it last.

## 5. Definition of done (next phase)

- `ui-ux-pass` merged; visual/RTL QA signed off; design‑system docs updated.
- Durable worker running in Coolify with the beat schedule live; notifications no longer fire‑and‑forget.
- Stripe top‑up live behind the existing wallet seam (if a PSP is chosen); driver payouts automated.
- A clear, rehearsed plan (not necessarily shipped) for the stores generalization.

## 6. Operating model (how we run heavy work safely)

The UI/UX phase proved the model — and its limit:

- **Opus is the brain**: plans, orchestrates, synthesizes, verifies, picks each sub‑agent's model.
- **Sonnet does the bulk/parallel grunt work** at a model chosen per‑task.
- **Cap concurrency to the hardware.** Three workflows × wide fan‑out froze the laptop. Going forward:
  **one workflow at a time, ≤3–4 concurrent agents**, or pure‑synthesis work done inline by Opus with
  zero local load. Same output quality, calm machine.
- **Always branch + gate + back up to origin** before long autonomous runs.
