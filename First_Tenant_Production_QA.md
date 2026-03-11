# First Tenant Production QA
## Scope
This checklist is for the first real restaurant after deploy on production.

Use it after:
- deployment is healthy
- DNS resolves correctly
- `kepoli.com`, `admin.kepoli.com`, and wildcard tenant subdomains are live

## Required Inputs
- Super admin URL: `https://admin.kepoli.com/admin-console`
- Public landing URL: `https://kepoli.com`
- Test tenant slug: example `firstresto`
- Expected tenant URL: `https://firstresto.kepoli.com`

## 1. Platform Health
- [ ] Open `https://kepoli.com/health`
- [ ] Open `https://admin.kepoli.com/health`
- [ ] Open `https://kepoli.com/api/session/`
- [ ] Confirm no console errors on `kepoli.com`

## 2. Lead Capture
- [ ] Submit a fresh lead from `https://kepoli.com/get-started`
- [ ] Confirm lead appears in `admin-console`
- [ ] Confirm lead card shows plan, source, and contact details

## 3. Provision Preview
- [ ] In admin console, click `Check`
- [ ] Confirm preview shows expected subdomain
- [ ] Confirm no slug/domain collision unless intentionally testing one

## 4. Provision Tenant
- [ ] Click `Provision`
- [ ] Confirm success toast appears
- [ ] Confirm latest package now includes:
  - tenant URL
  - workspace URL
  - onboarding URL
  - sign-in URL
  - activation URL
  - public menu URL
  - owner next steps
- [ ] Copy package and store it in operator notes

## 5. Owner Activation
- [ ] Open activation URL from package
- [ ] Set password successfully
- [ ] Confirm redirect goes into owner onboarding flow
- [ ] If redirected to sign-in, confirm sign-in URL works and lands in owner workspace

## 6. Owner Onboarding
- [ ] Brand step saves
- [ ] Add at least 3 categories
- [ ] Add at least 8 dishes
- [ ] Add at least 1 dish option/variant
- [ ] Theme step saves
- [ ] Publish step passes checklist
- [ ] Click `Publish menu`
- [ ] Confirm owner reaches launch summary

## 7. Public Verification
- [ ] Open tenant public landing: `https://firstresto.kepoli.com/menu`
- [ ] Open tenant browse page: `https://firstresto.kepoli.com/browse`
- [ ] Open reservation page: `https://firstresto.kepoli.com/reserve`
- [ ] Confirm branding is tenant-specific, not demo/public fallback
- [ ] Confirm no console errors on tenant pages

## 8. Customer Flow Smoke
Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -FrontendBaseUrl https://firstresto.kepoli.com -ApiBaseUrl https://firstresto.kepoli.com/api -TableSlug table-1
```

Expected:
- all checks pass

## 9. Owner Workspace Verification
- [ ] Open `https://firstresto.kepoli.com/owner`
- [ ] Confirm readiness metrics render
- [ ] Confirm public URL copy action works
- [ ] Confirm tables page works
- [ ] Confirm reservations page loads

## 10. Admin Follow-up
- [ ] `Load package` still works after provisioning
- [ ] `Resend activation` works and returns updated package
- [ ] Tenant appears in lifecycle section with correct plan and domain
- [ ] Tenant timeline includes provisioning/package actions

## 11. Go / No-Go
Go only if:
- [ ] package URLs are production URLs, not `.localhost`
- [ ] activation succeeds
- [ ] onboarding saves
- [ ] publish succeeds
- [ ] tenant public pages work on the tenant subdomain
- [ ] no blocking console/network errors remain

## Operator Note Template
Record:
- Date/time:
- Tenant slug:
- Lead id:
- Provisioning package verified: yes/no
- Activation verified: yes/no
- Publish verified: yes/no
- Smoke script result: pass/fail
- Issues found:
