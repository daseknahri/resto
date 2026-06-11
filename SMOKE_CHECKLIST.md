# Restaurant v1.0 — manual smoke checklist (run after each production deploy)

Run top to bottom on the deployed environment with one test tenant. ~20 minutes.
Prereqs: Coolify deploy done (migrate_schemas auto-ran), Celery worker + beat up,
the two sweeps + daily summary in beat (see LAUNCH_CHECKLIST).

## 1. Owner setup (5 min)
- [ ] Sign in to the owner workspace; dashboard loads with the revenue tile showing
      the "cash · wallet" split line.
- [ ] Templates: open the picker — 27 templates, filter chips by business type work
      (incl. Pharmacy). Apply one with sample content → categories + dishes appear
      and the theme changes. No 500.
- [ ] Theme page: presets show palettes from the templates; "Browse templates" opens
      the same picker; brand preview shows the mini menu mockup in your colors.
- [ ] Pause a category (StepCategories → Pause) → it disappears from the public menu
      and the marketplace menu; Resume brings it back.

## 2. Customer dine-in via QR (4 min)
- [ ] Scan a table QR → menu loads (FR and AR render correctly, AR is RTL).
- [ ] Place a table order with one item that has options.
- [ ] Kitchen (OwnerKitchen): order appears; mark the item ready.

## 3. Mid-meal service — the R2/R4 flows (5 min)
- [ ] Waiter app: the table order appears grouped under its table with a combined
      outstanding total.
- [ ] "Add items" on the open order → add a drink → kitchen shows the NEW item as
      not-ready; order total increased.
- [ ] Void the drink (with a reason) → struck-through in waiter/owner views, total
      back down. (If the order had been wallet-paid: customer wallet refunded the
      exact line — check the wallet transactions list.)
- [ ] Split settle: enter HALF the outstanding, record as cash → card shows
      "Paid X · remaining Y" and stays open. Settle the rest → "fully paid",
      order leaves the active list. Printed receipt renders.

## 4. Pickup + delivery (3 min)
- [ ] Marketplace (/order): hub rail shows 5 services; Shops lens + Pharmacy
      sub-chip filter correctly.
- [ ] Place a prepaid pickup order from a customer account; cancel it while pending
      → wallet refunded, stock restored.
- [ ] Place a delivery order (platform delivery on) → driver app receives the job;
      accept → live tracking on the customer side; complete with the delivery code.

## 5. Money close (2 min)
- [ ] Dashboard revenue split reflects today's cash vs wallet from the steps above.
- [ ] Trigger `python manage.py send_daily_summary --dry-run` on the server →
      output shows the tenant with correct totals; re-run without --dry-run twice →
      exactly ONE push/email received (idempotent).

## 6. Link previews + PWA (1 min)
- [ ] `curl -s -A "WhatsApp/2.23" https://<tenant-host>/ | grep og:title` → tenant name.
- [ ] `curl -s -A "Mozilla/5.0" https://<tenant-host>/ | grep '<div id="app">'` → SPA.
- [ ] Share the menu link in a real WhatsApp chat → name + image unfurl.

## 7. Reservations (1 min)
- [ ] Create a reservation from the public page → owner sees it; the confirmation
      email's manage/cancel link works.

Any failure: file it in BACKLOG.md (or fix immediately if it blocks service) before
announcing the deploy done.
