# Local setup quicksteps

## Backend
1) `cd backend`
2) `python -m venv .venv && .\.venv\Scripts\activate`
3) `pip install -r requirements.txt`
4) Copy `backend/.env.example` to `backend/.env`, then adjust values for your machine
5) `python manage.py makemigrations accounts tenancy menu`
6) `python manage.py migrate_schemas --shared`
7) `python manage.py migrate_schemas --tenant`
8) Seed plans (and optional demo): `python manage.py seed_plans --with-demo --domain demo.localhost --email admin@example.com --password admin123`
9) Run server: `python manage.py runserver`
10) Verify local tenant host mapping (PowerShell):
   - Check only: `powershell -ExecutionPolicy Bypass -File .\infra\bootstrap-local-tenants.ps1 -TenantSlugs demo,dede`
   - Apply missing hosts entries (run PowerShell as Administrator): `powershell -ExecutionPolicy Bypass -File .\infra\bootstrap-local-tenants.ps1 -TenantSlugs demo,dede -Apply`

## Frontend
1) `cd frontend`
2) `npm install`
3) Optional: copy `frontend/.env.example` to `frontend/.env`
4) `npm run dev`

## One-Command Local Run (Windows)
- Start backend + frontend in separate PowerShell windows:
  - `powershell -ExecutionPolicy Bypass -File .\infra\run_local.ps1 -TenantHost demo.localhost`
- Stop listeners on local ports:
  - `powershell -ExecutionPolicy Bypass -File .\infra\stop_local.ps1`

Default local test logins (demo tenant):
- Platform admin (for admin console): `admin@example.com` / `admin123`
- Tenant owner (for owner workspace): `test_resto_user@demo.local` / `admin123`

## Tests
- Lint (after installing pre-commit): `pre-commit install && pre-commit run --all-files`
- Backend app tests: `cd backend && python manage.py test tests -v 2`
- OpenAPI contract export:
  - Windows: `powershell -ExecutionPolicy Bypass -File .\infra\export_openapi.ps1`
  - Linux/macOS: `bash ./infra/export_openapi.sh`
- Browser E2E critical + mobile regression:
  - Prepare deterministic admin/demo seed:
    - Windows: `powershell -ExecutionPolicy Bypass -File .\infra\prepare_e2e.ps1`
    - Linux/macOS: `bash ./infra/prepare_e2e.sh`
    - Also ensures owner login for workspace regression tests: `test_resto_user@demo.local / admin123`
    - If backend is already running, restart it after preparation to reset in-process throttle cache.
  - Start app locally:
    - Windows: `powershell -ExecutionPolicy Bypass -File .\infra\run_local.ps1 -TenantHost demo.localhost`
  - Install Playwright browser (first run only):
    - `cd frontend && npm run e2e:install`
  - Run suite:
    - `cd frontend && npm run e2e:critical`
    - `cd frontend && npm run e2e:mobile`
    - `cd frontend && npm run e2e`
  - Optional env overrides:
    - `E2E_FRONTEND_URL`, `E2E_PUBLIC_FRONTEND_URL`, `E2E_API_URL`, `E2E_ADMIN_EMAIL`, `E2E_ADMIN_PASSWORD`, `E2E_OWNER_EMAIL`, `E2E_OWNER_PASSWORD`
  - Included spec also validates cross-host auth/CSRF behavior:
    - tenant-host admin session + host isolation (`localhost` vs `demo.localhost`)
    - CSRF required for unsafe auth endpoint (`POST /api/logout/`)
  - Included mobile spec validates no horizontal overflow across landing, customer flow, owner workspace, and admin console at 390x844.

## Plan-gated order handoff
- Endpoints:
  - `POST /api/order-handoff/`
  - `POST /api/checkout-intent/`
  - `GET /api/tier-upgrade-targets/` (owner upgrade options, backend-driven)
  - `GET|POST /api/tier-upgrade-requests/` (owner request flow)
  - `GET /api/admin-tier-upgrade-requests/` (admin list)
  - `PUT /api/admin-tier-upgrade-requests/<id>/decision/` (admin approve/reject)
  - `GET|POST|PUT|DELETE /api/tables/` (owner table links + QR context management)
  - `POST /api/tables/bulk-generate/` (owner bulk table creation: Table 1..N)
  - `GET /api/tables/qr-export/` (owner server-side export; `export_format=zip` for QR PNG + CSV manifest, `export_format=pdf` for A4 cards)
  - `GET /api/tables/<id>/qr-image/` (owner server-side QR PNG download per table)
  - `GET /api/table-context/<slug>/` (public table context lookup for `/t/<slug>` links)
  - POST /api/uploads/image-delete/ (tenant-scoped cleanup for wizard image replace/remove)
- Public tier codes:
  - `basic` (maps internally to plan code `starter`)
  - `growth`
  - `pro`
- Behavior:
  - Returns WhatsApp URL only when tenant plan allows WhatsApp ordering.
  - Supports optional `table_label`, `table_slug`, `customer_name`, and `customer_phone` in order-handoff payload.
  - Customer links support `?table=<label>` (or `?t=<label>`) and short table links `/t/<slug>` for QR cards.
  - If `table_slug` is provided, backend validates the table link is active and resolves canonical table label.
  - Owner table cards are printable with branding (logo/name), local first-party generated QR images, and short fallback URLs.
  - Owner can export table assets as CSV and an offline HTML QR pack (shareable/printable without live API calls).
  - Owner can download QR PNGs directly (single table or bulk batch).
  - Server QR export URLs use `PUBLIC_MENU_BASE_URL` when configured; otherwise they infer from current host.
  - Owner UI supports server ZIP and PDF downloads directly from the table workspace.
  - Checkout intent enforces `can_checkout` and currently returns a pending-payment response until Stripe integration.
  - Owner can request a higher tier (cash-first workflow), and tenant plan switches only after admin approval.
  - Enforces published/open/menu-disabled policy on server side.
  - Prevents client-side bypass of plan entitlements (including checkout restrictions).

Notes: Use LF endings; secrets stay out of VCS; tenant routing uses subdomains.

## Production env essentials
- Secure cookies:
  - `DJANGO_SESSION_COOKIE_SECURE=True`
  - `DJANGO_CSRF_COOKIE_SECURE=True`
  - `DJANGO_SESSION_COOKIE_SAMESITE=Lax` (or `None` if cross-site is required)
  - `DJANGO_SESSION_COOKIE_DOMAIN=.yourdomain.com`
  - `DJANGO_CSRF_COOKIE_DOMAIN=.yourdomain.com`
  - `DJANGO_PUBLIC_SCHEMA_HOSTS=yourdomain.com,admin.yourdomain.com,localhost,127.0.0.1`
- SMTP delivery:
  - `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
  - `DJANGO_DEFAULT_FROM_EMAIL=noreply@yourdomain.com`
  - `DJANGO_EMAIL_HOST=smtp.yourprovider.com`
  - `DJANGO_EMAIL_PORT=587`
  - `DJANGO_EMAIL_HOST_USER=...`
  - `DJANGO_EMAIL_HOST_PASSWORD=...`
  - `DJANGO_EMAIL_USE_TLS=True`

- Frontend runtime API:
  - `VITE_API_BASE_URL=auto`
  - `VITE_ADMIN_API_BASE_URL=auto`
  - `VITE_PLATFORM_PUBLIC_HOSTS=yourdomain.com,admin.yourdomain.com`

## Release utilities
- Pre-release smoke test script: `infra/pre_release_smoke.ps1`
- Deployment + rollback guide: `infra/DEPLOYMENT_RUNBOOK.md`
- Analytics retention cleanup (scheduled): `cd backend && .\.venv\Scripts\python.exe manage.py prune_analytics_events --days 90`
