# Kepoli Daily-Use Audit — "clear picture" (2026-07-07)

Read-only audit of every daily-use surface (8 role groups, 55 pages) for **UX-system gaps** and **broken daily-use logic**. 51 findings. Fixes tracked in the same batch as this pass.

Legend: **P0** = breaks a core task / loses money or data · **P1** = frequent friction or wrong state · **P2** = polish.

## P0 (5)
| Page | Cat | Issue |
|---|---|---|
| CategoryPage.vue | logic | Quick-add ignores `is_schedule_available` (DishPage guards it) — customer adds an unorderable item, fails late at checkout. |
| Directory.vue | logic | `filteredRestaurants` calls `.toLowerCase()` on nullable `cuisine_type/city/tagline` — any null tenant field makes search throw and the grid go blank. |
| OwnerOrders.vue | logic | Bulk "Mark all ready" has no busy-guard (scalar `updatingOrderId` clears mid-batch) — double-submit fires overlapping PATCH batches. |
| AdminFlashSales.vue | logic | `createSale()` allows `active_until <= active_from` and past windows — a mistyped flash sale goes live to nobody. |
| OwnerCustomers.vue | logic | Loyalty grant succeeds but card shows stale points until reload — risk of double/under-grant. |

## P1 (selected)
- **OwnerWallet.vue** (logic/security): driver cash-out confirm keys off the raw code string, not the id from lookup — code changing between lookup/confirm can pay the wrong driver. (Cash-out code is a live bearer credential — never log it.)
- **AdminWallet.vue** (logic): `generateVouchers()` has no `idempotency_key` (unlike fund/bonus/credit) — a flaky double-submit mints duplicate voucher batches (real money).
- **AdminConsole.vue** (logic): delivery-pricing modal accepts negative/out-of-range numbers past HTML min/max, saved straight to API.
- **ReservationPage.vue** (logic): free-text time input not gated by slot capacity — guest can book a slot the UI says is full → overbooking.
- **OwnerReservations.vue** (logic): bulk reminder opens only the FIRST WhatsApp link but reports whole-batch success; reconciliation queue silently discardable.
- **OwnerAnalytics.vue** (logic): "today" KPIs derived from the order store which this page never fetches — shows 0/— on a cold visit.
- **AdminDeliveryJobs / AdminRides** (logic): live ops boards never poll or resync on focus — go stale for a whole shift.
- **OwnerShiftClose.vue** (logic): both fetches `.catch(()=>null)` — a real outage renders an ambiguous blank instead of an error+retry.
- **OwnerKitchen.vue** (logic): 86-board re-sorts rows mid-tap → wrong dish gets 86'd.
- **OwnerRatings.vue** (logic x2): CSV blob URL revoked before download starts; reply save/delete never re-fetches to confirm server truth.
- **OwnerPromotions.vue** (logic): clone→duplicate-code failure swallowed into a generic toast (happy-hours surfaces the real detail).
- **OwnerMenuBuilder.vue** (ux): CSV import success toast only fires when dishes>0 — category-only imports look ambiguous.
- **OwnerCustomers.vue** (logic): CSV export failure silently swallowed.
- **OwnerProfile.vue** (ux): two independently-scoped Save CTAs in one scrolling tab — owner thinks both saved; hours silently unsaved.
- **OwnerZReport.vue** (ux): 6-col voids/comps/labor tables have no `ui-table-wrap`/card fallback → 390px overflow.

## P2 (polish, selected)
Cart tip upper-clamp confirm · FindMyOrder in-flight guard · Marketplace favourites/recently-viewed skip sold-out gate · Reservation past-date guard · WaiterPage `loadTableStatuses` swallow · OwnerTables dead whole-card click · OwnerOrders `loadPayments`/history-range feedback · OwnerHome refresh omits drawer state · OwnerLoyalty tier-threshold relational validation · OwnerStaffPage collapsed-row error badge · OwnerBilling future-period guard · AdminDrivers payout>owed JS check · AdminRides saveFares no-op feedback · SendPackagePage phone format · RidePage/SendPackage visibility resync · AdminCustomers ledger-refresh swallow · AdminConsole flag-JSON per-field error + tenant-list flash + lifecycle button spacing · OwnerRatings router-link-active repurposed for chip state · OwnerPromotions winback @change auto-save + double primary CTA.

## Separately fixed this pass (LOG backlog)
LOG-01 order idempotency (Cart/order.js/marketplace) · LOG-02 401 re-auth · LOG-04 availability-safe reorder · LOG-05 driver re-poll on unlock · LOG-06 close shift on staff delete · LOG-07 address lat/lng.
