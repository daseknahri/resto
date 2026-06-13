# Operator-grade audit — 2026-06-13 (evidence base for the §4d OPS program)

8 parallel lenses, each tracing real flows through real code; every finding carries
file:line evidence verified at audit time. Clustered + deduplicated (cross-lens
corroboration noted). Line numbers drift as code changes — they locate the area, the
titles locate the problem. Consumed by KEPOLI_ARCHITECTURE.md §4d (OPS-1…OPS-6).

## Lens verdicts (one line each)
- service-speed: YES daily driver; biggest gap = no real-time push (10s kitchen / 15s waiter blind windows) + 86-a-dish is a 5-step navigation.
- end-of-day-money: NO — no Z-report/shift close; revenue includes in-flight orders; refunds invisible; day boundaries wrong (UTC / device-tz).
- failure-modes: CONDITIONAL — offline queue is in-memory only; refresh during outage silently loses transitions; idempotency holes on status/wallet-paid/placement.
- scale-one-year: YES today; biggest gap = OwnerOrderListView full-table scan + JOIN COUNT every 15s, no date fence, 200-row silent cap.
- onboarding-ttfo: NOT self-serve — human provisioning + no online wallet top-up (marketplace effectively invite-only without a PSP).
- multi-device: CONDITIONAL — biggest gap = no Screen Wake Lock; kitchen tablet sleeps, poll skipped while hidden, beeps never fire.
- platform-ops: BORDERLINE — Sentry has no tenant context; health check misses Celery/channel-layer/media; support is blind into live tenant state.
- professional-polish: YES behind login; the public page hard-renders a dev domain and has no prices — first 30 seconds undermine the pitch.

## THEME 1: Real-time delivery & polling architecture
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| Polling latency: kitchen ≤10s blind, waiter ≤15s; no WS path actually working | every_shift / major_friction / large | service-speed, failure-modes, multi-device | OwnerKitchen.vue:582-585; WaiterPage.vue:1605-1608; useRealtimeChannel.js:24 | setInterval 10000/15000ms; audio alert fires only on next poll cycle. |
| InMemoryChannelLayer in multi-worker deploy: broadcast from worker A never reaches worker B's clients | every_shift / major_friction / small | failure-modes, platform-ops | config/settings.py:238-241; realtime/broadcast.py:26-29 | Without REDIS_URL channel layer is process-scoped; the 10s poll is the real mechanism even when realtime "looks" configured. |
| WS reconnect gives up after 6 attempts (~63s), permanent silent fallback | weekly / annoyance / small | failure-modes, multi-device | useRealtimeChannel.js:24; OwnerLayout.vue:697-700 | No further reconnect; no "live vs polling" indicator. |
| WS event triggers full order-list refetch instead of targeted patch | every_shift / annoyance / medium | multi-device | OwnerLayout.vue:624-627, 592-594; menu/views.py:5633-5635 | Payload {order_number, status} is enough for a targeted update; 4 devices = 4× full reloads per status change. |
| No Screen Wake Lock — kitchen screen sleeps, poll skipped while hidden, beep never fires | every_shift / blocker / small | multi-device | OwnerKitchen.vue:479-487, 582-585; sw.js:1-60 | zero 'wakeLock' matches in frontend/src; visibilityState='hidden' explicitly skips the poll. |

## THEME 2: Data integrity & concurrency
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| Offline queue is plain Pinia state — refresh during outage silently discards queued transitions | daily / major_friction / medium | failure-modes, multi-device | waiter.js:37, 166-172 | No localStorage/IndexedDB persistence; replay also unsafe (no idempotency on the PATCH). |
| Status-advance PATCH not idempotent, no row lock — last-write-wins, timeout+retry unsafe | daily / major_friction / medium | failure-modes, multi-device | menu/views.py:5532, 5540-5548; retry.js:13; waiter.js:145-158 | Cancel path is locked; common pending→confirmed advances are not. |
| Wallet mark-paid has no idempotency key (cash path has one) | daily / major_friction / small | failure-modes | waiter.js:196-215; menu/views.py:5798-5851 | Timeout → re-settle can double-handle an already-paid order. |
| Stale-state ghost after concurrent advance — losing device never self-heals | daily / major_friction / small | multi-device, failure-modes | waiter.js:153-156, 281-303; OwnerKitchen.vue:643-645 | No refetch after failure; queue re-queues permanent 400s forever (waiter.js:298). |
| Redis down nullifies cache-based payment idempotency; no DB unique backstop | rare / blocker / small | failure-modes | settings.py:207-215 (IGNORE_EXCEPTIONS); menu/views.py:4302-4311 | Add unique (order, idempotency_key) on OrderPayment. |
| Waiter order placement has no dedup — timeout + resubmit = two kitchen tickets | weekly / major_friction / medium | failure-modes | WaiterNewOrder.vue:651-674; menu/views.py:1966-1978 | submitting guard only stops same-lifecycle double-taps. |

## THEME 3: Financial reporting & end-of-day close
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| No Z-report / shift-close view; revenue windows are rolling N-day | daily / blocker / medium | end-of-day-money | sales/views.py:2318; menu/views.py:3413-3427 | StaffShiftSummaryView is per-waiter only, no cash/wallet split. |
| Dashboard + digest count PREPARING/READY/CONFIRMED as revenue | daily / major_friction / small | end-of-day-money | sales/views.py:2466-2470; send_daily_summary.py:94-99 | Drawer total inflated by in-flight orders at close time. |
| Refunds/cancellations absent from every financial surface | daily / major_friction / medium | end-of-day-money | sales/views.py:2466-2470, 2685-2692; menu/views.py:2932 | Refund wallet credits fire but no aggregate is shown anywhere. |
| No payment-method correction flow | weekly / major_friction / medium | end-of-day-money | grep change_payment = 0 matches | Miscoded cash/wallet is permanently wrong. |
| void_reason / recorded_by_name never surfaced (UI or CSV) | daily / major_friction / small | end-of-day-money | menu/models.py:585, 643; menu/views.py:5909-5915 | Owner cannot audit who voided what or who took cash. |
| Charts bucket days in UTC (TruncDate no tz); owner/waiter "today" uses DEVICE timezone | daily / annoyance / small | end-of-day-money | sales/views.py:2544-2550; OwnerOrders.vue:931, 966-968 | Digest is tz-correct; dashboard disagrees with it. |
| Waiter shift summary: no cash/wallet split, no custom window | daily / major_friction / small | end-of-day-money | menu/views.py:3419-3427, 3452-3460 | Unusable for cash handover. |

## THEME 4: Database performance & unbounded growth
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| OwnerOrderListView: full-table scan + JOIN-COUNT every 15s, no date fence | every_shift / major_friction / medium | scale-one-year, service-speed | menu/views.py:4757-4769; OwnerOrders.vue:1459-1463 | 4+ heavyweight queries/min against all historical rows. |
| 200-row silent cap — oldest (stuck) orders drop off with passive warning | daily / major_friction / medium | service-speed, scale | menu/views.py:4763-4769; OwnerOrders.vue:188-192 | No load-more control. |
| Customer list: double GROUP BY, no pagination, 3k-row JSON | daily / major_friction / medium | scale | menu/views.py:7374-7405; OwnerCustomers.vue:181 | JS-side filtering over the fully loaded list. |
| Order.customer_phone unindexed; 4 query paths scan | daily / annoyance / small | scale | menu/models.py:398; sales/views.py:2705 | One-line migration. |
| Return-rate query: Python IN-list of 2000+ phones | daily / major_friction / small | scale | sales/views.py:2696-2711 | Subquery instead. |
| NotificationLog + WinbackNudge never pruned | daily / annoyance / small | scale | accounts/models.py:980-1053; settings.py:322-337 | analytics + audit ARE pruned; these two grow unbounded. |
| revenue.py ledger_order_ids still materialized as Python set on dashboard path | daily / annoyance / small | scale | menu/revenue.py:39-63 | Finish the subquery conversion. |

## THEME 5: Operational service UX (kitchen & waiter)
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| 86-a-dish from kitchen = 5-step navigation away | daily / major_friction / small | service-speed | OwnerKitchen.vue (no toggle); OwnerDashboardDishPanel.vue:82-145 | Cook exits fullscreen, navigates, toggles, returns. |
| Free-text table label — typos split table groups + mis-target course firing | every_shift / major_friction / small | service-speed | WaiterNewOrder.vue:52-61; WaiterPage.vue:1225-1253 | Use TableLink dropdown. |
| Mark-all-ready = N serial PATCHes | every_shift / annoyance / small | service-speed | OwnerKitchen.vue:667-678 | Bulk endpoint. |
| Search: no urgency sort, no table quick-jump; grouping only on 'all' tab | every_shift / annoyance / medium | service-speed | WaiterPage.vue:1521-1537; waiter.js:50-55 | |
| WaiterNewOrder lazy-loads categories serially on open | every_shift / annoyance / small | service-speed | WaiterNewOrder.vue:701-719 | Prefetch on page load. |
| Staff throttle is per-IP — shared NAT bursts exhaust it | weekly / major_friction / small | multi-device | menu/throttles.py:28-29; rest_framework.py:48 | Scope per-user. |

## THEME 6: Onboarding & tenant provisioning
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| No self-service signup (human admin provisions every tenant) | blocker / large — DECISION-GATED | onboarding | sales/services.py:248-318; AdminConsole.vue:255 | Sales-motion choice; activation token 24h; provision email failure swallowed (services.py:135-145). |
| No online wallet top-up — marketplace effectively invite-only | blocker / large — BLOCKED ON PSP | onboarding | accounts/views.py:3025-3039; grep psp/stripe/cmi = 0 | First-time remote customers must visit in person. |
| CSV import exists but hidden post-wizard | every_shift / major_friction / small | onboarding | menu/views.py:7935-7937; StepDishes.vue (0 refs) | Surface inside the wizard. |
| Category delete silently CASCADEs dishes, no count in confirm | weekly / major_friction / small | onboarding | menu/models.py:74; StepCategories.vue:758-772 | |
| Staff temp password shown once; no in-app change | weekly / major_friction / small | onboarding | accounts/views.py:1043-1098; WaiterPage grep = 0 | Shared-phone waiters need delete+recreate today. |
| QR print = window.print() all-tables A4 only | monthly / annoyance / medium | onboarding | OwnerTables.vue:947-1015 | Per-table PDF export. |
| price=0 publishes silently; placeable with empty wallet | weekly / annoyance / small | onboarding | menu/serializers.py:542-545; accounts/views.py:3026 | Publish-checklist warning. |

## THEME 7: Platform operations & observability
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| Sentry has no tenant tag (backend scope or SPA setTag) | every_shift / blocker / small | platform-ops | config/sentry.py:37-44; lib/sentry.js:59-85 | Errors unattributable to a restaurant. |
| /api/health/ checks DB+cache only — Celery/channel-layer/media unmonitored | every_shift / blocker / small | platform-ops, failure-modes | config/api.py:36-94 | Dead worker = notifications queue forever, silently. |
| No read-only support view into a live tenant's queue | weekly / major_friction / medium | platform-ops | AdminConsole.vue:40-88 | Phone-only support today. |
| Billing fully manual; invoice_amount needs Django /admin/ edit before receipt works | weekly→monthly / major_friction / small-large | platform-ops | enforce_subscriptions.py:13-16; sales/services.py:656-671; OwnerBilling.vue:313-329 | Renewal-date column + set amount on approve = quick wins; full automation = PSP-gated. |
| Backups: one checklist sentence; no automation; no per-schema restore runbook | monthly / blocker / medium | platform-ops | LAUNCH_CHECKLIST.md:87; docker-compose.coolify.yml:222-239 | django-tenants restore semantics need a rehearsed runbook. |
| Migrations auto-run on deploy; no rollback section | monthly / major_friction / medium | platform-ops | docker/entrypoint.sh:4-18 | |
| AnalyticsEventIngestView AllowAny 600/h can flood | weekly / annoyance / medium | platform-ops | rest_framework.py:27-33; accounts/views.py:2729 | |

## THEME 8: PWA, session & device hygiene
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| Manifest locks portrait-primary for ALL personas — kills landscape kitchen installs | daily / major_friction / small | multi-device | public/manifest.json:8 | Driver already has a dynamic manifest; staff don't. |
| Session: fixed 90-day window, no SAVE_EVERY_REQUEST, Redis restart logs out the whole floor | monthly / major_friction / small | multi-device | settings.py:347-354; api.js:162-169 | No expiring-soon banner. |
| Perms too coarse: settle implies void (loss-creating) rights | daily / annoyance / medium | multi-device | accounts/models.py:438-473; OwnerStaffPage.vue:294-310 | Add perm_void separate from manage_orders. |
| Kitchen excluded from KeepAlive — refresh = blind skeleton | daily / annoyance / small | failure-modes, multi-device | OwnerLayout.vue:650-657 | |
| Status-update view has no throttle; queue flush bursts unlimited | weekly / annoyance / small | multi-device | menu/views.py:5503-5505; waiter.js:281-303 | |

## THEME 9: Professional polish & marketing credibility
| Title | Freq/Impact/Effort | Lenses | Evidence | Detail |
|---|---|---|---|---|
| Hardcoded dev domain 'doro.menu.ibnbatoutaweb.com' in production hero/CTA | every_shift / blocker / small | polish | Home.vue:113, 385; DemoLanding.vue:25; LandingLayout.vue:198 | Config-driven brand domain. |
| Plans section shows no prices; same stats repeated 5× | every_shift / major_friction / medium | polish | Home.vue:314-356, 427-455 | Owner supplies prices (decision-gated input). |
| Currency fallback paths emit raw toFixed(2) | daily / major_friction / small | polish | OwnerDashboardInsights.vue:426-430; RevenueBarChart.vue:340; +3 | Centralised formatCurrency exists — use it everywhere. |
| RTL gaps: physical text-right + inline styles in charts/tables | daily / major_friction / medium | polish | OwnerDashboardRevenue.vue:189; OwnerOrders.vue:221 | |
| toLocaleString(undefined) reads OS locale (5 sites) | daily / annoyance / small | polish | OwnerOrders.vue:1058; OrderStatus.vue:947; +3 | |
| Raw backend `detail` reaches customers in Cart fallback | weekly / annoyance / small | polish | Cart.vue:2008-2016 | |
| 'Available' badge = 3 different concepts on one page | every_shift / annoyance / small | polish | Home.vue:77, 146, 325-337 | |
| Orders empty-state for published-but-quiet tenant is a dead icon | daily / major_friction / small | polish | OwnerOrders.vue:264-270 | CTA: share menu link / QR. |
| No print stylesheet for reports (dark-theme dump) | weekly / annoyance / small | polish | tailwind.css (no @media print); usePrintTicket.js:136 | Z-report print covers part of this (OPS-2). |
| PWA icon 'any maskable' single entry; no safe zone | rare / annoyance / small | polish | public/manifest.json:14-29 | |
