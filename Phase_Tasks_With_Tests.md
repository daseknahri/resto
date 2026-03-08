# Detailed Phase Tasks with Tests

## Phase 0: Setup and Standards (Day 1-2)
- Repo layout: create `backend/`, `frontend/`, `infra/`; add README with dev commands.
- Tooling: python venv, node version manager, pre-commit hooks (black/isort/ruff + eslint/prettier/stylelint), git attrs for LF.
- Env: sample `.env.example` for backend/frontend; secrets excluded via `.gitignore`.
- CI: lint + unit placeholders for both stacks; cache deps.
- Tests to run: lint all; backend `pytest -q` (even if minimal); frontend `npm run lint`; verify `docker compose up` boots blank stack.

## Phase 1: Multi-Tenant Core (Week 1)
- Backend init: Django, DRF, PostgreSQL config, django-tenants (subdomain strategy), shared vs public schema setup.
- Models: Tenant, Domain, Plan, FeatureFlag, User with roles (`platform_superadmin`, `tenant_owner`, `tenant_staff`).
- Middleware + routers: tenant resolution per request; plan/feature flag injection in context; 403 on cross-tenant access.
- Auth: token/JWT setup; password policies; admin superuser bootstrap.
- Tests to run: unit for tenant resolution; isolation test (Tenant A cannot read Tenant B); feature flag toggles block endpoints; role-based permissions per route; migrations apply cleanly.

## Phase 2: Menu Management CMS (Week 2)
- Models: Category, Dish, DishOption/AddOn, Price, Media (image), PublishStatus.
- Admin/owner UI: CRUD forms, image upload, publish/unpublish toggle, ordering of categories/dishes.
- API: tenant-scoped CRUD endpoints with validation (required fields, price formats, image limits).
- Permissions: owners/staff edit; read-only for public.
- Tests to run: API CRUD happy + validation errors; publish flag hides unpublished items from public API; media upload size/type; staff cannot edit outside tenant.

## Phase 3: Customer Mobile Experience (Week 3)
- Frontend init: Vue 3 + Vite + Pinia + Tailwind configured for mobile-first; base layout components; theme tokens per tenant.
- Pages: Home (logo, socials, map/reviews, reservation CTA, menu button); Categories list (card banners); Dishes list/detail with images and descriptions.
- Performance: lazy image loading; skeleton loaders; CDN-ready image URLs.
- Tests to run: component unit tests for cards/list; Cypress e2e smoke (home -> category -> dish); Lighthouse mobile score target set and logged.

## Phase 4: Starter Cart (Week 4)
- State: Pinia cart store (add, remove, qty, notes, clear); totals; persistence in localStorage.
- UI: cart drawer/page; contact CTA (call/WhatsApp) shown because plan blocks checkout; messaging text includes cart summary.
- Backend: order endpoints present but gated by feature flag `can_checkout` (returns 403 for Starter); telemetry for cart interactions.
- Tests to run: store unit tests for add/remove/totals; e2e flow add items then open contact CTA; API returns 403 when checkout disabled; ensure no Order rows created in Starter plan.

## Phase 5: Super-Admin Sales Console (Week 5)
- Models: Lead, Deal, Subscription, ProvisioningJob, ActivationToken.
- Console UI: pipeline board, deal detail, `Confirm Sale` action; tenant provisioning service (creates tenant, domain, owner user, assigns plan Starter).
- Messaging: activation link generator (24h token); WhatsApp/email template with admin URL + activation link; audit log of sends.
- Tests to run: provisioning job success/failure paths; activation token expiry and single-use; message content includes correct URLs; role permissions (only superadmin can confirm sale).

## Phase 6: Marketing Landing and Lead Capture (Week 6)
- Public site: hero/value prop, demo screenshots, pricing (Starter live, Growth/Pro “coming soon”), FAQs, CTA buttons.
- Lead form: posts to backend CRM endpoint, stores Lead tied to source; optional WhatsApp quick-contact link.
- Analytics: basic events (CTA clicks, form submit success/fail).
- Tests to run: form validation client/server; lead persists to DB; spam/rate limits; page performance budget; CTAs resolve correctly on mobile.

## Phase 7: Deployment and Operations (Week 7)
- Infra: Docker Compose for `nginx`, `django`, `frontend`, `postgres`, optional `redis`; `.env.prod` documented.
- Nginx: SSL via Let’s Encrypt; wildcard/subdomain routing to tenants; gzip/brotli.
- Ops: daily DB dumps + retention; media backup plan; log rotation; Sentry or equivalent.
- Runbook: deploy steps, rollback steps, health checks.
- Tests to run: staging deploy; TLS check; tenant subdomain resolves; backup + restore rehearsal; load test smoke; 0-downtime deploy verification.

## Phase 8: Launch and Early Sales (Week 8)
- Pilot onboarding: import first tenants, assist menu setup, gather feedback.
- Support: shared inbox/WhatsApp number; SLA guidelines.
- Analytics: monitor activation funnel, cart interaction, page performance per tenant.
- Backlog: collect issues from pilots; prioritize next sprint.
- Tests to run: full end-to-end on pilot tenant (menu browse, cart, contact CTA); verify monitoring alerts; manual UX review on real devices.

## Post-Launch Milestones (Planned)
- Enable Growth plan: WhatsApp checkout endpoint + UI; order persistence and status timeline.
- Billing: subscription lifecycle, invoices/receipts, grace periods, dunning.
- Pro features: analytics dashboard, multi-branch, custom domain mapping, advanced theming.
- Compliance: privacy policy, data export/delete per tenant.
Phase 0 done: repo layout created, gitignore/gitattributes set, pre-commit config added, env templates added, README includes dev commands.
Phase 1 scaffold created: Django config with django-tenants, custom user roles, plan/feature flag models, placeholder tests. Migrations pending when DB ready.
- Start Phase 2: Menu CMS scaffold
- Create menu app with models/admin/serializers/views
- Wire DRF routes and permissions
- Add placeholder tests
Phase 2 scaffold created: menu app with Category/Dish/DishOption models, DRF viewsets/routes, public URL separation, permissions, placeholder tests.
Phase 2 extras: added seed_plans management command for plans/superadmin/demo tenant; updated README with setup/migrations/seed steps.
Phase 3 scaffold: Vue 3 + Vite + Tailwind frontend added with landing/menus, custom cards, routing; npm build succeeds. Pending: wire real API + cart state in Phase 4.
Phase 3 enhancements: Added CORS, published-only filtering, demo menu seeder, Vue Pinia stores (menu/cart), API-driven pages, and successful frontend build.
Phase 3 completed with runtime plan gating: added tenant meta API, published-only menu queries, demo menu seeder, frontend tenant/cart stores, and build verified.
Phase 4 (Starter cart flow) implemented: Cart page with WhatsApp CTA, plan gating from tenant meta, nav link, env vars for contact phone/message; backend meta endpoint added.
Added lint/format tooling: ESLint flat config, Prettier, scripts, editorconfig; lint now passes. Production cart flow remains. Pending: CI wiring.
Phase 4 CI: Added GitHub Actions workflow for backend migrations/checks against Postgres service and frontend lint/build; created .github/workflows/ci.yml.
Phase 5 start: Added sales app with Lead/Deal/Subscription/ProvisioningJob/ActivationToken models, admin actions for confirm sale provisioning, lead API endpoint, settings/urls updated, migrations applied.
Phase 5 extension: sales app hardened with provisioning service, lead API (public create + admin list), throttles for public leads, DRF settings split, migrations applied.
Phase 5 add: provisioning service now issues activation tokens, logs admin URL and token, provision API returns tenant/admin/token. Ready for messaging hook next.
Phase 5 messaging: provisioning now emails activation details and returns WhatsApp deep link; logs admin URL/token/link in provisioning job.
Phase 5: Added provisioning job API/list, fixed Lead serializer, reran checks (clean). Next: connect landing lead form and UI for job logs.
Phase 6 start: Added lead store and landing lead capture page (/get-started) posting to /api/leads, build fixed after BOM cleanup. Next: surface success messaging in marketing flow.
Phase 6 tweak: Lead capture adds honeypot anti-spam, success text updates; backend lead serializer enforces honeypot blank. Build passes.
Phase 6 UX: Lead form now shows success message and auto-redirects home; lead store reset helper added. Build still clean.
Phase 6 UX: Home now shows lead-success banner via query param, dismissible; build passes. Ready for admin provisioning view next.
Phase 5 admin ops: resend activation action in admin, messaging now picks primary domain for admin URL, issue_activation helper added. Checks clean.
Phase refinement: Cart badge added to header, tenant store now directly sets cart flags (removing dynamic import warning); build clean.
Phase enhancement: Added admin console page listing provisioning jobs via API with status chips; shared axios client with credentials; cart badge retained. Build passes.
Next pre-deploy refinements completed: header cart badge, shared axios client, admin console for provisioning jobs, configurable CORS origins (env), builds/checks clean. Ready to move into tiering and deployment.
Tier hardening UI: cart now distinguishes Starter (WhatsApp) vs Growth/Pro (checkout), shows plan label, stores track canWhatsapp; CORS env refined earlier. Build clean.
