# Browser E2E - SaaS Critical + Mobile Regression

This suite validates the core production onboarding journey in one path:

1. Public lead submission (`/get-started`)
2. Admin sign-in and lead provisioning (`/admin-console`)
3. Owner activation (`/activate?token=...`)
4. Owner onboarding wizard completion (`/owner/onboarding`)
5. Publish and public menu verification (`/browse`)

And validates security/session behavior:

1. Tenant-host admin session works on tenant host
2. Session is not shared automatically with a different local host (`localhost` vs `demo.localhost`)
3. Unsafe auth endpoint (`POST /api/logout/`) is blocked without CSRF header and accepted with CSRF header

And validates mobile breakpoint safety (390x844):

1. Landing + customer routes (`/get-started`, `/menu`, `/browse`, `/cart`, `/reserve`) do not overflow horizontally
2. Owner workspace routes (`/owner`, `/owner/onboarding`, `/owner/tables`, `/owner/reservations`) stay readable
3. Admin console mobile layout stays overflow-safe

## Preconditions

- Backend API running on `demo.localhost:8000`
- Frontend running on `demo.localhost:5173`
- Database reachable
- E2E admin account prepared

Use:

- `powershell -ExecutionPolicy Bypass -File .\infra\prepare_e2e.ps1`
- `powershell -ExecutionPolicy Bypass -File .\infra\run_local.ps1 -TenantHost demo.localhost`
- `prepare_e2e` also ensures owner credentials: `test_resto_user@demo.local / admin123`
- If backend was already running before preparation, restart backend once so throttling cache is reset for E2E.

## Execute

```bash
cd frontend
npm run e2e:install   # first run only
npm run e2e:critical
npm run e2e:mobile
npm run e2e
```

Optional env vars:

- `E2E_FRONTEND_URL`
- `E2E_PUBLIC_FRONTEND_URL`
- `E2E_API_URL`
- `E2E_ADMIN_EMAIL`
- `E2E_ADMIN_PASSWORD`
- `E2E_OWNER_EMAIL`
- `E2E_OWNER_PASSWORD`
