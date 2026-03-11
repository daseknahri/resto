# Production Enhancements TODO
## Working Rules
- [ ] Keep this file updated every session: mark completed tasks, add new risks/tasks discovered during implementation.
- [ ] For each completed task, add short proof in commit/PR notes (endpoint, screenshot, test, or command output).
- [ ] Do not start Phase 2/3 items before all Phase 1 blockers are complete.

## Phase 1 - Launch Blockers (Must Finish Before Selling)

### 1. Access, Auth, and Permissions
- [x] Add dedicated sign-in flow (separate from activation).
- [x] Add session endpoint and role-aware route guards.
- [x] Restrict `/admin-console` and `/onboarding` to authorized roles only.
- [x] Add password reset flow (request reset, email token, set new password).
- [x] Add login/activation/password-reset brute-force protection and lockout policy (IP throttles).
- [x] Add explicit unauthorized UX on guarded pages (friendly screen + action button).

### 2. Tenant Resolution and Local Dev Stability
- [x] Local multi-tenant host handling (`*.localhost`) fixed for ALLOWED_HOSTS/CORS/CSRF.
- [x] Runtime API base supports tenant host correctly.
- [x] Auto-redirect local frontend host `localhost:5173` to configured tenant host.
- [x] Add tenant-not-found JSON response with actionable hint.
- [x] Add `/api/health/` endpoint for tenant/public debugging.
- [x] Add local bootstrap script to map tenant hosts and verify hosts file/DNS setup.
- [x] Make public-schema hosts configurable for production (`DJANGO_PUBLIC_SCHEMA_HOSTS`) so root/admin domains bypass tenant lookup cleanly.
- [x] Expose shared auth/admin/lead API routes on public hosts (`config.public_urls`) for same-host `/api` production routing.

### 3. Sales and Provisioning Operations
- [x] Persist publish state (`is_menu_published`, `published_at`) in backend profile.
- [x] Improve admin error rendering for provisioning failures.
- [x] Add tenant slug/domain collision pre-check in admin provisioning UI.
- [x] Add resend activation token action in admin console.
- [x] Add server-side generated activation URL endpoint (single source of truth).
- [x] Add "Copy full onboarding package" action:
- [x] Include tenant URL, admin URL, activation URL, WhatsApp message template.
- [x] Expand onboarding package with operator-safe owner journey fields (`onboarding_url`, `public_menu_url`, ordered next steps) so first production handoff is deterministic.
- [x] Add soft-delete/archive for leads (replace frontend-only remove).
- [x] Add `onboarded_at` timestamp and expose in admin console.
- [x] Add idempotent re-provision guard (prevent duplicate tenants when same lead is provisioned twice).
- [x] Stop storing raw activation tokens in provisioning job logs (store masked/hashed token only).
- [x] Auto-infer provisioning domain suffix from production base URL (avoid accidental `.localhost` links in live onboarding packages).
- [x] Attach lead submissions created on tenant domains to that tenant (`Lead.tenant`) for cleaner ops context.
- [x] Add admin lead visibility improvements: show lead source and tenant slug in cards.
- [x] Change onboarding package links to owner-safe URLs (`/activate`, `/signin`, `/owner`) instead of sending restaurant owners to Django admin.

### 4. Core Product Correctness (Menu Builder)
- [x] Fix category/dish slug collision behavior in onboarding.
- [x] Enforce publish policy on public menu routes (public blocked until publish; tenant editor preview allowed when logged in).
- [x] Add strong field validation and inline error display for onboarding forms.
- [x] Add empty-state guardrails (cannot publish without minimum required content).
- [x] Add image upload flow (storage + compression + fallback image handling).
- [x] Add onboarding image-upload UX hardening (client-side file validation + progress indicators per upload).
- [x] Add drag-and-drop active-state feedback in onboarding upload zones (theme/category/dish).
- [x] Add tenant-scoped image cleanup flow (remove image endpoint + wizard cleanup on replace/remove).
- [x] Defer managed image cleanup until successful save/publish to avoid broken DB references.
- [x] Upgrade publish step checklist to real live checks (brand/category/dish/theme status + publish guardrails).
- [x] Add open/closed status toggle and temporary menu disable toggle.
- [x] Add owner table-link management (CRUD) with QR-ready menu URLs for dine-in flow.
- [x] Add bulk table generation flow (prefix/start/count) for fast dine-in setup.
- [x] Add branded printable table QR cards (logo/name, short `/t/<slug>` fallback links, print-friendly cards-only layout).
- [x] Add public table context resolution (`/api/table-context/<slug>/`) and validate `table_slug` in order handoff (reject disabled/missing table links).
- [x] Add owner exports for table operations (CSV export + downloadable offline HTML QR pack for print/share).
- [x] Add owner QR PNG download actions (per-table PNG + bulk QR PNG batch download for print workflows).
- [x] Separate frontend into distinct interface shells (Landing, Owner workspace, Customer menu) with dedicated route groups.
- [x] Fix customer cart line pricing and quantity logic (unit-price storage + option-aware line keys + in-cart quantity steppers).
- [x] Include dish option selections in cart/order handoff notes so restaurant sees selected modifiers.
- [x] Add server-side option-aware price calculation in order-handoff/checkout-intent (totals now include selected option deltas).
- [x] Add table-aware WhatsApp handoff support (optional table label in cart/API/message, auto-captured from `?table=` QR links).
- [x] Add optional customer identity capture (name/phone) in cart and include it in WhatsApp handoff payload/message.

### 5. Security and Compliance Baseline
- [ ] Configure production transactional email provider (SMTP/API) for activation and password reset delivery.
- [x] Add env-driven email delivery settings (backend supports SMTP/secure transport switches via env vars).
- [x] Wire full SMTP runtime env mapping in Coolify compose (`DJANGO_EMAIL_*`) and add validator checks (host/port/TLS/SSL/fail-silently policy).
- [x] Add email delivery observability (`app.email` logger + warning when mail backend returns zero sent count).
- [x] Add `check_email_delivery` management command for post-deploy SMTP verification + test send.
- [x] Add `email_delivery_drill` management command to verify real activation + password-reset templates through SMTP.
- [x] Add Coolify host-side email verification script + runbook (`infra/coolify/verify_email_delivery.sh`, `infra/COOLIFY_EMAIL_VERIFICATION.md`).
- [x] Add DNS deliverability check script + runbook for SPF/DMARC/DKIM (`infra/coolify/check_email_dns.sh`, `infra/COOLIFY_EMAIL_DNS_CHECK.md`).
- [ ] Connect live provider credentials/domain (SendGrid/Mailgun/SES) and verify deliverability (SPF/DKIM/DMARC).
- [x] Add security monitoring for throttled auth attempts (logs/alerts dashboard).
- [x] Log throttled auth attempts through DRF exception handler (`security.throttle` logger).
- [x] Add configurable security log handler/rotation (`DJANGO_SECURITY_LOG_FILE`, `DJANGO_SECURITY_LOG_LEVEL`).
- [x] Route throttle events to alerting/monitoring backend (Sentry/ELK/Grafana) with actionable alerts.
- [x] Add Coolify throttle verification runbook/script for operational checks (`infra/COOLIFY_THROTTLE_ALERT_VERIFICATION.md`, `infra/coolify/verify_throttle_alerts.sh`).
- [ ] Enable secure production cookie settings:
- [x] `SESSION_COOKIE_SECURE=True`
- [x] `CSRF_COOKIE_SECURE=True`
- [x] `SESSION_COOKIE_SAMESITE` reviewed for subdomain auth strategy
- [x] Add audit log for sensitive admin actions (provision, resend activation, role change, tenant deactivation).
- [x] Add legal pages and links in landing/app footer (Privacy Policy, Terms, Contact).

### 6. QA and Release Readiness
- [x] Add end-to-end integration tests:
- [x] lead -> provision -> activation -> onboarding -> publish
- [x] cross-subdomain auth/csrf behavior
- [x] plan gating behavior (starter with WhatsApp enabled, checkout restricted)
- [x] Add backend publish-policy test coverage (public block, preview bypass, temporary disable behavior).
- [x] Add backend order-handoff policy test coverage (plan, unpublished, disabled, closed, unavailable item, success).
- [x] Extend order-handoff/checkout test coverage for split order context rules (table-QR minimal flow vs non-table required fulfillment/contact and delivery location validation).
- [x] Add table-context API tests (active/missing table, policy-block precedence, invalid slug).
- [x] Add backend checkout-intent policy test coverage (plan gating, unavailable item, mixed currency, accepted intent).
- [x] Add smoke test checklist script for pre-release.
- [x] Fix smoke script compatibility for PowerShell 5/7 JSON parsing (`infra/pre_release_smoke.ps1`).
- [x] Add dedicated order-flow API smoke script for split cart behavior (`infra/order_flow_api_smoke.ps1`).
- [x] Add strict role-based pre-deployment QA checklist document (`Pre_Deployment_QA_Checklist.md`).
- [x] Add manual E2E QA guide for customer order flows (table-QR vs general menu) with exact URLs (`Order_Flow_E2E_QA.md`).
- [x] Add first-production-tenant QA checklist with exact operator sequence and production smoke command (`First_Tenant_Production_QA.md`).
- [x] Add VPS deployment readiness report with explicit go/no-go and required production infra tasks (`VPS_Deployment_Readiness_Report.md`).
- [x] Add CI pipeline for backend tests + frontend build.
- [x] Write deployment runbook with rollback procedure.
- [x] Write release-candidate freeze status/checklist for Basic tier launch (`Release_Candidate_Freeze.md`).
- [x] Add local run/stop scripts for QA handoff (`infra/run_local.ps1`, `infra/stop_local.ps1`).

## Phase 2 - Early Post-Launch Hardening (After First Sales)

### 1. Observability and Reliability
- [x] Add structured logging for backend API and provisioning jobs.
- [x] Add Sentry (backend + frontend) with environment tagging.
- [x] Configure production DSN values and verify first captured backend/frontend error event.
- [ ] Tune throttle-to-Sentry alert threshold (`DJANGO_SENTRY_THROTTLE_MIN_WAIT_SECONDS`) after first week of production traffic.
- [x] Add uptime monitoring and alerts for API/frontend.
- [x] Add host-level uptime automation scripts (cron installer + down/recovered drill runner) for Coolify operations.
- [x] Add alert payload format support for webhook providers (generic/slack/discord) in uptime tooling.
- [x] Configure production alert webhook destination and verify down/recovered notifications.
- [x] Add DB backup/restore routine and test restore procedure.
- [ ] Execute and document first production restore drill result (timestamp, backup file, endpoints verified).
- [ ] Move media uploads from local disk to object storage (S3-compatible) with signed URLs and lifecycle policy.
- [x] Add S3-compatible media storage foundation (backend storage toggle + AWS env wiring + Coolify compose runtime mapping + env validator checks).
- [x] Add signed-URL TTL control (`AWS_QUERYSTRING_EXPIRE`) and lifecycle policy template (`infra/coolify/s3_media_lifecycle_policy.example.json`).
- [x] Add retention policy + pagination for admin audit logs to avoid unbounded growth.
- [x] Replace third-party QR image dependency with first-party generated QR assets (local in-app QR generation for print cards).
- [x] Add backend-side QR rendering endpoints for non-JS fallback (`/api/tables/qr-export/` ZIP/PDF + `/api/tables/<id>/qr-image/` PNG).
- [x] Add PDF generation for table-card print packs (A4-ready export from backend via `format=pdf`).

### 2. Tenant Management
- [x] Add tenant lifecycle controls (suspend/reactivate/cancel).
- [x] Add admin action history timeline per tenant.
- [x] Add tenant settings export/import for support operations.
- [x] Add tenant settings import dry-run mode (preview changes + validation report before replacing live data).

### 3. UX and Onboarding Quality
- [x] Add onboarding progress autosave and resume hints.
- [x] Persist onboarding current wizard step per tenant (resume after refresh).
- [x] Add explicit resume hint/reset action in wizard sidebar.
- [x] Add prebuilt starter templates (categories/dishes/theme packs).
- [x] Improve wizard completion feedback and success page with next actions.
- [x] Add dish variant management in owner wizard (extras/options like "Extra cheese" with price delta, required flag, and max-select).
- [x] Add conversion-focused landing sections (offer framing, phased roadmap, plan cards, stronger CTAs).
- [x] Upgrade lead capture UX with inline validation and "what happens next" guidance.
- [x] Link plan cards to prefilled lead form (`?plan=`) to reduce signup friction.
- [x] Upgrade owner dashboard UX with live readiness score and content metrics.
- [x] Add owner reservation inbox (`/owner/reservations`) to review reservation leads and update follow-up status (new/contacted/confirmed/unavailable).
- [x] Add reservation inbox filters and CSV export (status/search/date) for support and operations workflows.
- [x] Add reservation inbox pagination and bulk status actions (multi-select update workflow for owner operations).
- [x] Add reservation follow-up timeline (owner notes + automatic status-change logs per reservation).
- [x] Add reservation SLA alerts (owner inbox badges/counters + admin overdue follow-up panel).
- [x] Add dedicated admin reservation alerts endpoint (`/api/admin-reservation-alerts/`) with server-side SLA filters/counts.
- [x] Add owner one-click WhatsApp reservation reminder action with timeline logging (`POST /api/owner/reservations/<id>/reminder/`).
- [x] Add reservation reminder delivery confirmation state (opened/sent/failed) for true follow-up accountability.
- [x] Surface reminder analytics in owner/admin lists (latest reminder status/time + counts for sent/opened/failed).
- [x] Add owner reminder-status filter with retry queue mode (`reminder_status=failed/opened/sent/none`) for focused follow-up.
- [x] Add bulk retry reminder action for selected reservations (`POST /api/owner/reservations/bulk-reminder/`) with skip/missing reporting.
- [x] Add owner bulk reminder outcome reconciliation for prepared links (`POST /api/owner/reservations/bulk-reminder-result/` + owner inbox pending panel).
- [x] Upgrade customer menu UX with search/sort controls for faster browsing.
- [x] Add shared UI component classes (buttons/panels/layout shells) and align Landing/Owner/Customer interfaces.
- [x] Upgrade cart UX with clear-cart action, inline quantity controls, optional customer note, and actionable API error guidance.
- [x] Split cart order form by context: table-QR flow keeps only optional note, non-table flow requires fulfillment type + customer identity.
- [x] Add non-table delivery location capture options (GPS via browser geolocation or map-link input with coordinate parsing).
- [x] Improve delivery-location UX in cart with clearer guidance, map-link/coordinate fallback, and quick location actions (clear/copy/open map).
- [x] Add embedded in-app map pin selector (Leaflet modal with click-to-pin + apply to delivery coordinates/link) to reduce dependency on external map-link copy/paste.
- [x] Lazy-load map picker assets (Leaflet JS/CSS/icons) only when opening the in-app map modal to keep primary menu/cart bundle lighter.
- [x] Execute visual polish pass across landing/customer/owner surfaces (design tokens, glass panels, improved hierarchy, better mobile nav).
- [x] Execute mobile responsiveness hardening pass across customer/owner/admin/auth pages (touch targets, stacked controls, horizontal-safe tables, sticky mobile CTAs).
- [x] Add customer-facing restaurant landing block on `/menu` with Google/social CTA buttons, lead-capture form, and post-submit confirmation UX.
- [x] Split customer journey into four dedicated pages: info/lead (`/menu`), menu browse (`/browse`), cart (`/cart`), and reservation (`/reserve`).
- [x] Harden public demo host flow (`kepoli.com`) with demo-safe menu fallback so customer pages do not crash when no tenant is resolved.
- [x] Execute dedicated mobile polish pass for the 4-page customer flow (hero hierarchy, quick actions, better form ergonomics, and sticky CTAs).
- [x] Execute owner workspace polish pass (consistent nav pills, stronger dashboard hierarchy, and mobile quick actions across dashboard/onboarding/tables/reservations).
- [x] Add owner operations mobile action rails (tables create/bulk shortcuts and reservation bulk-action sticky bar).
- [x] Complete cross-interface consistency pass (micro-copy alignment, action labels, and spacing rhythm across landing/customer/owner/admin surfaces).
- [x] Align admin console visual rhythm with product shell (max-width container + panelized upgrade/jobs/audit sections).
- [x] Add profile-level reservation link field (`reservation_url`) and expose it in owner onboarding (Brand & Contact).
- [x] Add customer quick-contact actions on menu landing (Call/WhatsApp) and track contact CTA analytics.
- [x] Enrich reservation lead notes with table context + page URL to improve confirmation workflow quality.
- [x] Final UX polish pass: safe-area spacing, premium display typography, stronger mobile CTAs, category search, sticky cart action bar, and responsive owner/admin readability hints.
- [x] Add shared customer journey rail (Info/Menu/Cart/Reserve) across customer layout with active/completed state cues.
- [x] Restrict customer journey rail to desktop/tablet screens (hide on mobile where bottom nav already covers the same steps).
- [x] Remove duplicated hero CTA buttons from menu browse page and reduce hero footprint for cleaner, conversion-focused UX.
- [x] Remove repeated in-page navigation buttons from customer flow pages (lead/cart/reservation) and rely on main app navigation.
- [x] Compress hero/header sections across all 4 customer pages (`/menu`, `/browse`, `/cart`, `/reserve`) to surface core content faster.
- [x] Extend compact, low-clutter pass to category and dish pages (remove duplicate back/cart controls from content area).
- [x] Reduce dish/category visual header height so menu items/options appear earlier on mobile screens.
- [x] Add shared micro-interaction layer (press/lift/reveal motion tokens) and apply it across customer cards, panels, and primary actions.
- [x] Upgrade customer flow typography rhythm (display weight/smoothing + tighter section hierarchy) for a more premium brand feel.
- [x] Improve dish option selection UX with selected-state highlighting and quantity stepper controls (+/- with safe bounds).
- [x] Remove mobile top-header action duplication (reserve/cart actions now primarily in bottom nav; desktop keeps top quick actions).
- [x] Improve category card scan density (shorter card height + stronger overlay metadata for faster menu browsing).
- [x] Add reduced-motion accessibility fallback to disable non-essential animations/transitions for motion-sensitive users.
- [x] Remove owner-workspace nav duplication by centralizing section navigation in `OwnerLayout` (dashboard/builder/tables/reservations/preview).
- [x] Remove repeated per-page owner header link rows (`OwnerHome`, `OwnerTables`, `OwnerReservations`, and onboarding shell).
- [x] Simplify landing navigation and hero CTAs to one clear demo path and one primary conversion action.
- [x] Add explicit post-submit reassurance actions on customer lead + reservation pages ("We will contact you shortly").
- [x] Add true mobile card-mode for admin data tables (upgrade/jobs/audit) to remove horizontal-scroll dependency on very small screens.
- [x] Add customer-flow UI regression tests for 4-page routing (`/menu`, `/browse`, `/cart`, `/reserve`) and table-context carryover from `/t/:slug`.
- [x] Implement executable customer-flow smoke script (`infra/customer_flow_smoke.ps1`) and document run command in `infra/README.md`.
- [x] Harden customer-flow smoke to discover a test dish robustly (category scan + `/api/dishes/` fallback) so QA is stable with uneven seed data.
- [x] Reduce frontend main bundle size (currently >500KB warning) via route-level code splitting/lazy loading for admin/owner-heavy modules.

### 4. Future-Proofing Foundation
- [x] Add frontend i18n foundation (message catalogs, locale store, route-aware language switching, fallback strategy).
- [x] Define multi-language content model strategy before editing translations (profile/category/dish/option fields and migration plan). See `I18N_Content_Model_Strategy.md`.
- [x] Expand i18n coverage across lead capture, reservation flow, owner dashboard, and owner reservations so operations use the locale layer too.
- [x] Expand i18n coverage across owner tables, auth recovery/activation, launch success, and onboarding theme/publish steps.
- [x] Expand i18n coverage across onboarding categories/dishes (including variant management, uploads, and client-side validation toasts).
- [x] Add non-component i18n helper and localize shared router/store guard toasts (router + lead/menu/tenant stores).
- [x] Localize remaining shared runtime fallbacks (`session` store auth errors + API 429 detail message) via message catalog keys.
- [x] Localize Admin Console operational feedback layer (script toasts/errors/prompts/import flow messages).
- [x] Localize Admin Console template labels/actions/states (headers, table columns, empty/loading states, package panel, SLA labels).
- [x] Localize remaining support/legal/auth edge pages (`Unauthorized`, `ContactPage`, `PrivacyPolicy`, `TermsOfService`) with EN/FR message catalogs.
- [x] Localize onboarding shell + shared UI components (`Wizard`, onboarding step metadata, `CategoryCard`, `ToastHost`) and customer lead step labels.
- [x] Localize customer cart + dish detail surfaces end-to-end (template labels, toasts, validation errors, and EN/FR catalogs).
- [x] Add locale propagation to API clients (`Accept-Language` + `lang` query on read endpoints) so backend can return localized menu content.
- [x] Define and implement initial multi-language content model strategy (JSON i18n fields for category/dish/option + locale-aware serializer fallback + settings export/import compatibility; see `I18N_Content_Model_Strategy.md`).
- [x] Expand i18n coverage across remaining admin/auth/owner detail screens now that the locale foundation is in place (all `frontend/src/pages`, `layouts`, `components`, and `onboarding` views use locale helpers).
- [x] Add owner wizard fields for managing translated content (`name_i18n`, `description_i18n`) with plan-aware language limits and UX guidance.
- [x] Add API contract/export workflow (OpenAPI or equivalent) for safer frontend/backend evolution.
- [x] Define Stage 2 central API strategy for future mobile apps/integrations (`api.kepoli.com`, versioning, explicit tenant identity pattern). See `Tenant_Routing_and_API_Architecture.md`.
- [x] Add migration safety check to CI (`makemigrations --check`) so schema drift is caught before deploy.
- [x] Add browser E2E suite for critical SaaS flows (public lead -> admin provision -> activation -> onboarding -> publish) using Playwright (`frontend/tests/e2e/critical-saas-flow.spec.js` + `infra/prepare_e2e.*`).
- [x] Add mobile breakpoint regression QA for Landing, Customer flow, Owner workspace, and Admin console.
- [x] Extract a documented UI system layer for future polish work (shared tokens, layout primitives, form patterns, data-card/table patterns).

## Phase 3 - Revenue and Plan Expansion

### 1. Billing and Subscription
- [ ] Add billing model (`trial`, `active`, `past_due`, `canceled`) and enforce access.
- [ ] Integrate Stripe checkout + webhooks for subscription lifecycle.
- [ ] Add invoice and subscription status pages for tenants.
- [x] Implement cash-first manual upgrade workflow (owner request -> admin approve/reject -> tenant plan switch).

### 2. Plan Entitlements
- [ ] Enforce plan rules in backend and frontend:
- [x] Starter: QR menu + WhatsApp order handoff (no checkout)
- [ ] Growth: in-app order management and operational workflow
- [ ] Pro: checkout, payments, and advanced capabilities
- [x] Harden browse-only fallback UX for plans with ordering disabled.
- [x] Make owner workspace plan-aware: onboarding/publish screens and header now show entitlement mode (Browse-only/WhatsApp/Checkout).
- [x] Add canonical tier structure (`basic/growth/pro`) with backend alias mapping to existing plan codes and computed entitlements in tenant meta.
- [x] Prevent provisioning for inactive/waitlist plans (explicit error message until plan launch).
- [x] Add owner endpoint to submit/list upgrade requests (`/api/tier-upgrade-requests/`).
- [x] Add admin endpoints to review and decide upgrade requests (`/api/admin-tier-upgrade-requests/`, `/api/admin-tier-upgrade-requests/<id>/decision/`).
- [x] Add admin console UI controls for upgrade approvals with audit log entries.
- [x] Disable admin "Approve" action in UI when target tier is inactive (prevents invalid approvals before launch).
- [x] Add owner workspace "Purchase tier" UX with pending-request guard and request history.
- [x] Add backend `order-handoff` API with server-side plan/menu-state gating.
- [x] Switch frontend cart WhatsApp action to backend handoff API (no client-side tier bypass).
- [x] Add checkout-intent API and enforce `can_checkout` before enabling checkout action in UI.
- [ ] Integrate real payment provider and return live `checkout_url` from checkout-intent endpoint.
- [x] Add feature-flag admin controls per plan.
- [x] Expose launched plan catalog from backend so owner upgrade selector is fully data-driven.

### 3. Analytics
- [x] Add tenant analytics events (menu views, category taps, dish views, cart views, checkout/WhatsApp clicks, owner publish).
- [x] Add dashboard cards for tenant performance and conversion trend (30-day interaction snapshot + top categories/dishes).
- [x] Add analytics retention cleanup command (`prune_analytics_events`) for scheduled maintenance on long-running tenants.

## Deployment and Infrastructure Checklist (Production VPS)
- [ ] Provision PostgreSQL with backups and secure credentials.
- [ ] Configure Gunicorn + Nginx + systemd services.
- [ ] Configure HTTPS (Let's Encrypt) and auto-renew.
- [ ] Configure wildcard subdomain routing for tenants.
- [x] Prepare exact Coolify/VPS wildcard proxy configuration and Traefik dynamic-config template for `*.menu.kepoli.com`.
- [ ] Install production wildcard certificate for `menu.kepoli.com` + `*.menu.kepoli.com` and attach it to the Coolify proxy.
- [ ] Apply server-level Traefik wildcard router and verify tenant host resolution on production (`<slug>.menu.kepoli.com`).
- [x] Add explicit tenant domain suffix control (`TENANT_DOMAIN_SUFFIX`) so provisioning can target namespace wildcards (for example `*.menu.kepoli.com`) without coupling to root domain.
- [x] Document Coolify wildcard ownership strategy to avoid cross-app conflicts on shared root domains.
- [x] Document same-host `/api` proxy requirement for `kepoli.com`, `admin.kepoli.com`, and `*.kepoli.com`.
- [x] Simplify production host routing by proxying `/api`, `/admin`, `/media`, and `/static` through frontend/admin Nginx.
- [x] Configure static/media serving and caching (Nginx gzip + cache headers for `/assets`, proxied `/static`, and `/media`).
- [x] Add environment separation (dev/stage/prod) and secrets management (`coolify.env.staging.sample`, `coolify.env.production.sample`, `infra/COOLIFY_ENV_SEPARATION.md`).
- [x] Add post-deploy smoke test script.
- [x] Support both baseline and customer-flow checks post deploy (`infra/pre_release_smoke.ps1`, `infra/customer_flow_smoke.ps1`).
