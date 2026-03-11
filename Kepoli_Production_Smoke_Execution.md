# Kepoli Production Smoke Execution
## Purpose
This is the exact operator sequence to validate a real tenant on production before treating the platform as ready for live restaurant onboarding.

Use this after:
- Coolify deploy is healthy
- wildcard DNS for `*.menu.kepoli.com` resolves to the VPS
- `menu.kepoli.com`, `admin.menu.kepoli.com`, and tenant subdomains are reachable over HTTPS

## Required Inputs
- Public site: `https://menu.kepoli.com`
- Admin console: `https://admin.menu.kepoli.com/admin-console`
- Test tenant slug: choose one fresh slug, for example `smoke-20260310`
- Expected tenant host: `https://smoke-20260310.menu.kepoli.com`
- Test table slug after onboarding: `table-1`

## Credentials You Need Before Starting
- Platform admin account for `admin.menu.kepoli.com`
- A fresh lead email and phone number that you control
- A test WhatsApp-accessible phone if you want to verify order handoff end-to-end

## Phase 1 - Platform Precheck
Run from your machine in the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\release_candidate_freeze.ps1
```

Then run the production wrapper in dry-run mode to confirm the exact tenant URLs:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\production_tenant_smoke.ps1 `
  -TenantSlug smoke-20260310 `
  -BaseDomain menu.kepoli.com `
  -PublicHost menu.kepoli.com `
  -AdminHost admin.menu.kepoli.com `
  -TableSlug table-1 `
  -DryRun
```

Expected:
- freeze validation passes
- dry-run prints the exact production URLs and smoke commands

## Phase 2 - Public Lead Capture
1. Open `https://menu.kepoli.com/get-started`
2. Submit a new lead using the chosen tenant slug context in your notes
3. Use the `basic` plan for this validation

Record immediately:
- lead name
- lead email
- lead phone
- timestamp
- chosen target slug

Expected:
- success confirmation on public site
- lead appears in admin console

## Phase 3 - Admin Provisioning
1. Open `https://admin.menu.kepoli.com/admin-console`
2. Find the new lead
3. Click `Check`
4. Confirm preview resolves to `smoke-20260310.menu.kepoli.com`
5. Click `Provision`

Expected package content:
- tenant URL
- workspace URL
- onboarding URL
- sign-in URL
- activation URL
- public menu URL
- owner next steps

Hard fail if:
- any URL contains `.localhost`
- wrong domain suffix is used
- tenant host is missing

## Phase 4 - Owner Activation
1. Open the activation URL from the provisioning package
2. Set the owner password
3. Confirm redirect lands in owner onboarding or owner sign-in flow
4. If redirected to sign-in, open the sign-in URL from package and log in

Expected:
- activation succeeds
- owner can access `/owner`
- no 403/500/auth loop

## Phase 5 - Owner Onboarding
Use the owner workspace on `https://smoke-20260310.menu.kepoli.com/owner`.

Complete at least:
- Brand step:
  - restaurant name
  - phone
  - WhatsApp
  - address
  - Google Maps URL
  - social links
- Categories:
  - add at least 3 categories
- Dishes:
  - add at least 8 dishes
  - add at least 1 dish variant/option
- Theme:
  - save logo/hero/colors
- Publish:
  - pass checklist
  - click `Publish menu`

Expected:
- owner reaches launch summary
- no save/publish error

## Phase 6 - Automated Tenant Smoke
Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\production_tenant_smoke.ps1 `
  -TenantSlug smoke-20260310 `
  -BaseDomain menu.kepoli.com `
  -PublicHost menu.kepoli.com `
  -AdminHost admin.menu.kepoli.com `
  -TableSlug table-1
```

This runs:
- health checks for public/admin/tenant
- `infra/pre_release_smoke.ps1` on tenant host
- `infra/customer_flow_smoke.ps1` on tenant host

Expected:
- all checks pass

## Phase 7 - Manual Customer Verification
Open and verify:
- `https://smoke-20260310.menu.kepoli.com/menu`
- `https://smoke-20260310.menu.kepoli.com/browse`
- `https://smoke-20260310.menu.kepoli.com/cart`
- `https://smoke-20260310.menu.kepoli.com/reserve`
- `https://smoke-20260310.menu.kepoli.com/t/table-1`

Check:
- tenant branding is correct
- no demo fallback content appears
- category and dish pages load
- cart accepts item add/remove
- table route carries table context into cart
- reservation form submits
- WhatsApp order handoff opens correctly for Basic tier

Hard fail if:
- console shows blocking errors
- `/api/meta/` or `/api/categories/` fails on tenant host
- customer pages render public marketing content instead of tenant content

## Phase 8 - Manual Owner Verification
Open:
- `https://smoke-20260310.menu.kepoli.com/owner`
- `https://smoke-20260310.menu.kepoli.com/owner/tables`
- `https://smoke-20260310.menu.kepoli.com/owner/reservations`

Check:
- readiness metrics render
- public menu URL copy works
- tables page creates/loads QR table links
- reservations page loads without auth/cors/tenant issues

## Phase 9 - Manual Admin Follow-up
Return to:
- `https://admin.menu.kepoli.com/admin-console`

Check:
- `Load package` still works
- `Resend activation` still works
- tenant appears in lifecycle section
- tenant timeline shows provisioning activity

## Go / No-Go Rule
Go only if all are true:
- package links are production-safe
- activation works
- onboarding works
- publish works
- tenant pages work on the tenant subdomain
- automated smoke passes
- no blocking browser/network errors remain

## Operator Record Template
- Date/time:
- Tenant slug:
- Lead email:
- Lead id:
- Provision package verified: yes/no
- Activation verified: yes/no
- Onboarding verified: yes/no
- Publish verified: yes/no
- Automated smoke result: pass/fail
- Manual customer flow result: pass/fail
- Manual owner flow result: pass/fail
- Issues found:
