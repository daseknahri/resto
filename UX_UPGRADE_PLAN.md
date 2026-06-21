# Kepoli UX Upgrade Plan — make every surface extremely easy

_Generated from the kepoli-ux-perf-audit workflow (11 agents). Track: product designer (UX ease)_

## Headline lever

> Collapse the everyday taps: kill double-tap gates (estimate→request, OTP confirm, >3-option full-page navigation) and pre-fill remembered context by default, so every Kepoli role hits its primary action in one motion like Uber/Careem/Toast do.

## Quick wins (10) — high-impact, low-risk, no device needed → ship first

### QW1. Remove the >3 option-group cap that forces a full-page route  _(impact: high · effort: S)_
- **Change:** Delete the `<= 3` clause in `useQuickAdd` (line 379) so QuickAddSheet handles ALL option depths in a single in-place bottom sheet (it already scrolls). Keeps scroll position and avoids an extra page load — Uber Eats/Talabat parity.
- **Files:** `frontend/src/components/DishCard.vue:379 (and align Cart.vue isLineEditable cap at ~1193)`

### QW2. Auto-submit OTP on the 6th digit  _(impact: high · effort: S)_
- **Change:** Add `watch(otpCode, v => { if (v.length === 6 && !verifying.value) verifyOtp() })`. Removes the universal extra 'Verify' tap on the most frequent auth action. Keep the button for paste cases. Verified: no auto-submit watcher exists today (only @keydown.enter and a click handler).
- **Files:** `frontend/src/components/CustomerAuthModal.vue:219,306-317`

### QW3. Express checkout ON by default for returning customers  _(impact: high · effort: S)_
- **Change:** Default `expressCheckout` to true so the last address/fulfillment auto-applies after the first order (first-ever visit is still blank). Eliminates the manual opt-in toggle; matches Uber Eats/Deliveroo 'never a blank form'.
- **Files:** `frontend/src/pages/Cart.vue:1228, frontend/src/stores/cart.js (isExpressCheckoutEnabled default)`

### QW4. Default analytics period to Today, add a 1d tile, persist choice  _(impact: medium · effort: S)_
- **Change:** Change `insightsPeriod` default 30→7, add `1` (today) at index 0 of PERIOD_OPTIONS, persist last selection to localStorage. Fixes the KPI-strip-vs-chart cognitive mismatch owners hit during service.
- **Files:** `frontend/src/pages/OwnerAnalytics.vue:180-181`

### QW5. Instant-filter the Reservations list (drop the Apply button)  _(impact: medium · effort: S)_
- **Change:** Replace @keyup.enter on the search input with a 300ms debounced @input that calls applyFilters; remove the duplicated desktop+mobile Apply buttons, keep Clear. Toast/Square parity.
- **Files:** `frontend/src/pages/OwnerReservations.vue:57,78-93`

### QW6. Land the Menu Builder on the Dishes tab  _(impact: high · effort: S)_
- **Change:** Change the default route segment from 'super-categories' to 'dishes' so a price edit is reachable without 2 prior tab hops. Pairs with inline price edit in Wave 3.
- **Files:** `frontend/src/pages/OwnerMenuBuilder.vue:277, router config`

### QW7. Move Cancel out of the primary action row on owner order cards  _(impact: high · effort: S)_
- **Change:** Relocate the destructive Cancel into a '…' overflow / secondary row with a visual divider, away from the Confirm/Start primary button (currently ~2px gap). Layout-only; the confirm modal already exists. Prevents fat-finger cancels mid-service.
- **Files:** `frontend/src/pages/OwnerOrders.vue:1006-1097`

### QW8. Two-zone settle sheet with one-tap 'Cash — [total]'  _(impact: high · effort: S)_
- **Change:** Make the primary CTA a single full-width 'Cash — [amount]' button that pays the pre-filled full amount; put Wallet equally prominent below; collapse the amount input + ÷2/3/4/5 split controls into a closed-by-default 'Split amount' section. Cuts the standard settle from 3 taps to 2.
- **Files:** `frontend/src/pages/WaiterPage.vue:1457-1501`

### QW9. Inline active/inactive toggle on promotion rows  _(impact: medium · effort: S)_
- **Change:** Add a switch on each promo card that PATCHes {is_active:!is_active} with optimistic badge update, so owners pause a promo without opening the edit drawer.
- **Files:** `frontend/src/pages/OwnerPromotions.vue:113-141`

### QW10. WhatsApp/email share for new staff credentials  _(impact: low · effort: S)_
- **Change:** Add a 'Share on WhatsApp' (wa.me/?text=) and mailto: button on the post-create credential card so the one-time temp password reaches staff via the primary MENA channel. Zero backend.
- **Files:** `frontend/src/pages/OwnerStaffPage.vue:80-95`

## Waves (5)

### Wave 1 — One-tap booking & checkout funnel (customer)

_Goal:_ Bring the highest-traffic consumer funnels to Careem/Uber Eats tap-parity: single-action ride/package booking, auth-first checkout, and pre-filled address. Highest value-per-effort; mostly self-contained page files.

- **Auto-compute ride/package estimate inline; collapse the two-step gate into one Request CTA** _(impact high · effort M · risk low)_
  - Watch pickupLatLng+dropoffLatLng → fire /rides/estimate in the background while the user fills recipient details, show the fare inline, and merge 'Get Estimate' into the single 'Request' button (loading-disabled until estimate resolves). Removes a full network round-trip and a redundant tap — the single biggest booking-funnel speedup.
  - `frontend/src/pages/RidePage.vue:383-495, frontend/src/pages/SendPackagePage.vue:534-646`
- **Auth-gate the checkout BEFORE form fields, not after** _(impact high · effort M · risk medium)_
  - When unauthenticated and not a table-context order, render only the sign-in CTA + read-only summary; v-if the fulfillment/delivery/payment section on isAuthenticated. Stops guests filling address/note/tip then hitting a wall.
  - `frontend/src/pages/Cart.vue:770-788,194-235`
- **GPS → auto-open in-app map picker; hide URL-paste fallback until asked** _(impact high · effort M · risk medium) · **[device-validate]**_
  - On successful useCurrentLocation, auto-open the in-app Leaflet picker pre-centred on the GPS point for confirm/drag; keep 'More location options' (URL paste) hidden until a pin is set. Collapses 3 competing address methods into one path. DEVICE-ONLY validation (real GPS).
  - `frontend/src/pages/Cart.vue:363-449`
- **Pre-select a positive default tip** _(impact medium · effort S · risk low)_
  - Set tipPercent default 0→10 and reorder TIP_OPTIONS so 0% is last (active tap required to remove). Proven driver-retention lever (Uber Eats/DoorDash default 15%).
  - `frontend/src/pages/Cart.vue:1082,1074`
- **Two-step cancel guard + post-request push priming on ride/package** _(impact medium · effort S · risk low)_
  - Replace immediate cancelRide/cancelPackage with a 'Tap again to cancel' 3s pattern (mirror ReservationManage), and call pushPrimingRef.maybeShow() right after a successful request (the highest-intent moment). Prevents fat-finger cancels and surfaces push to the highest-value users.
  - `frontend/src/pages/RidePage.vue:155-165,839-876, frontend/src/pages/SendPackagePage.vue:170-179,1006-1083`
- **Rebook CTA on ride/package history rows** _(impact medium · effort S · risk low)_
  - Add 'Rebook' on each completed history row that pre-fills pickup/dropoff (+coords if stored), clears the estimate, and scrolls to top. Uber 'Request again' parity.
  - `frontend/src/pages/RidePage.vue:542-583, frontend/src/pages/SendPackagePage.vue:694-726`

### Wave 2 — Discovery, dish sheet & order tracking (customer food, shared components)

_Goal:_ Tighten the food browse→add→track loop and de-duplicate the menu/marketplace chrome. Groups the shared customer components (QuickAddSheet, OrderStatus/DeliveryTracker, Marketplace, Menu) into one wave so agents don't collide on them; i18n keys for menu/marketplace ETA strings land here only.

- **Collapse Marketplace double filter rail into one pill strip; whole card a single link** _(impact high · effort M · risk low)_
  - Remove the redundant hub rail (keep one BUSINESS_TYPE_TABS pill strip with embedded icons; move ride/packages into a 'More services' pill/sheet) so cards appear within ~120px of top. Make the <li> itself the router-link and drop the separate bottom CTA + aria-hidden hero cover, yielding one focus ring and shorter cards.
  - `frontend/src/pages/Marketplace.vue:17-57,451-595`
- **Add prep/delivery ETA chip to marketplace restaurant cards** _(impact high · effort M · risk low)_
  - Surface prep_eta_min/max (already on the profile) in /api/marketplace/ and render a 'X–Y min' chip per card — the single most decision-relevant signal for hungry users. Adds one i18n key (menu.etaReadyIn).
  - `frontend/src/pages/Marketplace.vue:549-595, marketplace API serializer, frontend/src/i18n/messages-*.js`
- **Search-first Menu nav: move search to row 1, fold allergens behind a Filter pill** _(impact high · effort S · risk low)_
  - Reorder the sticky nav so the search input is the first child of <nav> (above category pills) and move the always-on allergen strip into a collapsible Filter pill at the end of the category row — cuts the nav from 3 rows to 2 so search is visible on first paint on a 375px phone.
  - `frontend/src/pages/Menu.vue:156-266`
- **QuickAddSheet hero image** _(impact medium · effort S · risk low)_
  - Add a 4:3 object-cover image block at the top of the sheet when dish.image_url exists, so customers keep visual context when adding from a row-layout card (sheet already max-h-85vh + scrolls).
  - `frontend/src/components/QuickAddSheet.vue:10-25`
- **Order tracking: 'Contact restaurant' escape hatch + ETA ring** _(impact high · effort M · risk low)_
  - When status==='preparing' and a tenant phone is available (add to /api/order-status/ if absent), render a tel: button below the status hint. Add an SVG stroke-dashoffset countdown ring over the ETA so 'time left' is scannable in <0.5s. No new deps.
  - `frontend/src/pages/OrderStatus.vue:299-331,859-866, order-status API`
- **Richer live delivery map (taller, 3 pins)** _(impact medium · effort M · risk low) · **[device-validate]**_
  - Raise the tracking map from h-48→h-64, add a pickup (restaurant) marker alongside driver+destination with distinct divIcons, bump maxZoom to 16. DEVICE-ONLY (map fit/zoom on a real phone).
  - `frontend/src/components/DeliveryTracker.vue:89,294-343`

### Wave 3 — Rush-speed operator & waiter surfaces

_Goal:_ Speed up the highest-frequency staff actions during service: order progression, menu edits, table start, item add, and end-of-shift. Owner and waiter page files are disjoint, so two agents can run in parallel within the wave.

- **Pass table context from floor tile into the new-order sheet** _(impact high · effort S · risk low)_
  - Add defaultTableSlug/defaultTableLabel props to WaiterNewOrder and pass the tapped tile's data via an openNewOrderForTable(tile) emit; seed tableSlug/tableLabel on mount. Also add a 'New order' button on empty table-group headers. Removes the redundant dropdown re-pick that every Toast Go/Square flow avoids.
  - `frontend/src/components/WaiterNewOrder.vue:440-490,913-933, frontend/src/pages/WaiterPage.vue:285-290,432-436,642-680`
- **Inline qty stepper on dish rows + Recent/Popular shortcut (waiter)** _(impact high · effort M · risk low)_
  - When cartQty>0 and the dish has no options, swap the single add-button for an inline −/count/+ stepper on the row (no cart round-trip); add a virtual 'Recent/Popular' category seeded from a localStorage top-5 frequency counter.
  - `frontend/src/components/WaiterNewOrder.vue:140-165,664-696`
- **Per-seat Wallet payment (split-by-seat)** _(impact high · effort S · risk low)_
  - Add a Wallet button per seat row calling a new payWalletForSeat (method='wallet'), gated on wallet tenders enabled. CRITICAL: split-by-seat is currently cash-only, which is non-functional under the established wallet-only model.
  - `frontend/src/pages/WaiterPage.vue:1439-1455,2331-2352`
- **Restructure waiter card action footer to one primary CTA + overflow** _(impact high · effort M · risk low)_
  - Replace the 6-7-button unsorted flex-wrap with one full-width primary (advance/settle by state) + ≤3 compact secondary buttons + a '…' overflow sheet for transfer/merge/rate; pull rate-customer out of the footer (already a post-settle modal). Apply to all three duplicated card templates. Cuts accidental taps under rush.
  - `frontend/src/pages/WaiterPage.vue:368-423,827-888,1050-1094,1248-1308`
- **Preset void-reason chips instead of a keyboard prompt** _(impact medium · effort M · risk low)_
  - Replace the PromptModal text input with a bottom-sheet of 3-5 preset reason chips (Wrong item / Customer changed mind / Kitchen error / Comp / Other→text). Cuts a void from 5+ interactions to 2.
  - `frontend/src/pages/WaiterPage.vue:1839-1857`
- **Inline price edit + drag-reorder in the menu builder** _(impact high · effort M · risk low)_
  - Make the price badge tap-to-edit inline (no full modal) and add a ≡ drag handle for reorder (HTML5/pointer events calling existing moveDish), replacing one-tap-per-position chevrons. Pairs with the Wave-0 'land on Dishes tab' quick win.
  - `frontend/src/onboarding/StepDishes.vue:84-98,119`
- **Merge Shift Close into a single 'Close shift & print Z-report' flow** _(impact high · effort M · risk low)_
  - Fold OwnerShiftClose into OwnerZReport as a top close-drawer card with one button that calls /owner/drawer/close/ then window.print(); retire the standalone page. Toast 'End of Day' single-flow parity.
  - `frontend/src/pages/OwnerZReport.vue, frontend/src/pages/OwnerShiftClose.vue`
- **Collapse OwnerOrders filter stack behind a Filter sheet + floating 86-board** _(impact high · effort M · risk low)_
  - Move fulfillment/payment/date filter rows into a single 'Filter' bottom drawer (keep search, status tabs, confirm-all banner inline) so the order list is above the fold; add a floating '86 Board' button that opens the existing OwnerKitchen 86 panel without navigating, and default the dish panel open when soldOutCount>0.
  - `frontend/src/pages/OwnerOrders.vue:87-232, frontend/src/components/OwnerDashboardDishPanel.vue`
- **Per-card elapsed timer on KDS; default focus mode for new owners** _(impact medium · effort S · risk low)_
  - Add a per-card elapsed timer (amber@10m, red@20m) from created_at via the existing useNowTicker, and default OwnerHome focusMode=true for accounts <30 days old with a '← Show full dashboard' link. Surfaces urgency and the best feature to first-time owners.
  - `frontend/src/pages/OwnerKitchen.vue, frontend/src/pages/OwnerHome.vue:843`

### Wave 4 — Driver/courier loop & recipient experience

_Goal:_ Close the real-world delivery gaps (proof-of-delivery fallback, trip-glance map, faster in-trip poll) and fix the brand-breaking recipient page. DriverPage/DriverOfferModal/SendPackagePage/RecipientTrackPage are courier-only files, isolated from waves 1-3.

- **Photo proof-of-delivery fallback** _(impact high · effort M · risk medium)_
  - Add a 'Leave at door / take photo' button beside the code input that opens the camera (<input capture='environment'>) and POSTs status='delivered' with proof_photo when the code can't be obtained. Backend accepts code OR proof_photo. Fixes a real unreachable-recipient dead end.
  - `frontend/src/pages/DriverPage.vue:1217-1268,1629-1658, driver job status API`
- **Route mini-map in the driver offer modal** _(impact high · effort M · risk low)_
  - Add a 160px Leaflet map under the payout with amber pickup + emerald dropoff markers and fitBounds (straight-line, no routing API), lazy-loaded like SendPackagePage. Lets drivers judge the trip at a glance instead of decoding km text.
  - `frontend/src/components/DriverOfferModal.vue (after line 54)`
- **Dark-mode the recipient tracking page (merged: 2 auditors)** _(impact high · effort S · risk low)_
  - Replace every light-mode class (text-slate-900, bg-white, bg-indigo-50, border-slate-200, bg-slate-50) and the bannerClass computed with the app's dark tokens (bg-slate-950/text-slate-100/ui-panel/sky accents). Verified ~6+ light classes present at lines 3,11,35,44,54,68. The first page non-users see — currently jarring and off-brand.
  - `frontend/src/pages/RecipientTrackPage.vue:1-83,127-133`
- **One-tap 'Share tracking link' for the sender** _(impact high · effort S · risk low)_
  - On the active-package card (accepted+), add a button calling navigator.share({url:`/track/${track_token}`}) with clipboard+toast fallback; expose track_token in /rides/active/. Uber Connect parity — sender currently has no way to surface the link.
  - `frontend/src/pages/SendPackagePage.vue:140-179, active-ride API`
- **Adaptive in-trip driver poll + countdown on all offer cards** _(impact medium · effort S · risk low)_
  - Split ensurePoll: 5s when activeJob/activeRide else 15s. Remove the v-if='offered_to_me' guard so open-pool offer cards also show the seconds countdown (amber@10s/red@5s) with a fade-out on expiry. Stops stale UI mid-delivery and silent offer expiry.
  - `frontend/src/pages/DriverPage.vue:1754-1760,665,682-688`
- **Always-visible active address + move sound-enable out of the offer modal** _(impact medium · effort S · risk low) · **[device-validate]**_
  - Surface the currently-relevant pickup/dropoff address (1 truncated line) in the always-visible hero instead of behind the accordion, and move the one-time 'enable sound' prompt to toggleOnline() so the offer modal shows only the Accept button. DEVICE-ONLY (thumb-reach + iOS audio gesture).
  - `frontend/src/pages/DriverPage.vue:212-288,1783, frontend/src/components/DriverOfferModal.vue:89-96`

### Wave 5 — Design-system, RTL & a11y hardening

_Goal:_ Pay down the cross-cutting tokens/RTL/touch-target debt in one coordinated pass (these touch tailwind.css, tailwind.config.js, shared modals and i18n — the system-wide bottleneck files — so they must NOT be split across waves). Lower per-item value but compounding and prevents silent regressions.

- **Fix RTL-breaking physical-direction utilities** _(impact high · effort S · risk low)_
  - Replace text-right→text-end and pl-4 pr-3.5→ps-4 pe-3.5 in price/accent columns across Cart, DishPage, DriverPage, StepDishes. Verified present (Cart:73,108,157). Arabic price columns currently flip to the wrong edge.
  - `frontend/src/pages/Cart.vue:73,108,157, frontend/src/pages/DishPage.vue:355, frontend/src/pages/DriverPage.vue:484, frontend/src/onboarding/StepDishes.vue:1276-1284`
- **Enforce 44px touch targets system-wide (merged: waiter + a11y auditors)** _(impact high · effort M · risk low) · **[device-validate]**_
  - Add min-height:2.75rem to .ui-input/.ui-textarea; unify qty steppers to h-11 w-11 across DishPage/QuickAddSheet/Cart (extract a QtyStepperButton); add min-h/min-w 2.75rem + focus-visible ring to the h-6/h-7 icon buttons in OwnerInventory and WaiterNewOrder cart controls. DEVICE-ONLY tap validation.
  - `frontend/src/styles/tailwind.css:683-689, frontend/src/pages/DishPage.vue:363-366, frontend/src/components/QuickAddSheet.vue:131-144, frontend/src/components/OwnerInventory.vue:132,401,446,453,617, frontend/src/components/WaiterNewOrder.vue:195,201`
- **Add focus traps to onboarding inline modals** _(impact medium · effort M · risk low)_
  - Extract ConfirmModal's FOCUSABLE/trapFocus into a useFocusTrap composable and apply to StepCategories/StepDishes/StepSuperCategories overlays (currently zero trap — Tab escapes to background). WCAG 2.4.3 dialog pattern.
  - `frontend/src/composables/useFocusTrap.js (new), frontend/src/onboarding/StepCategories.vue:177,306, StepDishes.vue:189,895,1332, StepSuperCategories.vue:155,294`
- **Single source of truth for color tokens; respect OS light preference** _(impact medium · effort M · risk medium)_
  - Point tailwind.config.js brand colors at CSS vars (var(--color-primary) etc.) to kill the config/CSS drift (surface differs #0B1C1A vs #0d1722), and seed colorScheme from prefers-color-scheme on first visit instead of hardcoded 'dark'. Add the font-body/font-display Arabic fallbacks in tailwind.config.js.
  - `frontend/tailwind.config.js:14-24, frontend/src/styles/tailwind.css:2-21,29, frontend/src/layouts/CustomerLayout.vue:295-296`
- **Modal/popover a11y consistency** _(impact medium · effort M · risk low)_
  - Fix color-scheme toggle aria (drop aria-pressed; dynamic 'Switch to light/dark' label + i18n keys), move Escape onto document in CustomerAuthModal, add role=dialog + focus trap + focus-restore to the NotificationBell dropdown, and make WalletChargeSheet's role=status a persistent live region.
  - `frontend/src/layouts/CustomerLayout.vue:39-52, frontend/src/components/CustomerAuthModal.vue:13,254-265, frontend/src/components/NotificationBell.vue:8-28,67-79, frontend/src/components/WalletChargeSheet.vue:88-109, frontend/src/i18n/messages-*.js`

## Deferred

- Notification inbox mobile bottom-sheet variant (NotificationBell): medium value but device-only and overlaps the Wave-5 NotificationBell a11y rework — fold in there if cheap, otherwise defer to a dedicated tap-test.
- Custom wheel date/time picker for scheduled rides/packages: effort L and risk medium; ship the short-term dir='ltr' wrapper on the native inputs now and defer the full bottom-sheet picker.
- Address autocomplete (Nominatim/Photon) on ride/package inputs: high value but effort L + external geocoding dependency/rate-limits/privacy review — schedule as its own scoped track after Wave 1's inline-estimate lands.
- Light/warm theme CSS-variable refactor (~900-line override blob): effort L, risk medium, and the token-source-of-truth fix in Wave 5 reduces the bleeding; defer the full @layer/variable-swap rewrite.
- RecipientTrackPage 'confirm receipt' + rating flow and smooth marker/ETA interpolation: needs new public backend endpoints and is lower-frequency; defer until the dark-mode fix (Wave 4) ships.
- RoleSwitcher in a persistent bottom nav and GlobalLiveStatusBar +N tap target: depend on bottom-nav structure outside this audit's file scope; revisit when the shell nav is in scope.
- SignIn/Activate password show/hide + strength meter, token-field hide, MenuSelect flash, seat-chip picker, floor-tile/tab persistence, waiter course-count dynamic, wallet unified search, OwnerNotifications relocation, skeleton shape-awareness, DishPage sticky-bar z-index check: low-severity polish — batch into a later cleanup pass, not worth contending for the shared files now.
- Owner order swipe-to-advance gesture: high value but effort M + risk medium + device-only gesture tuning; defer to a focused gesture spike after the Wave-3 footer restructure stabilizes the card layout.
