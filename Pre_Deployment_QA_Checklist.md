# Pre-Deployment QA Checklist
## Release Context
- Date: 2026-03-07
- Scope: Tier 1 (Basic) production readiness
- Interfaces covered: Landing, Customer, Owner, Super Admin

## Automated Checks (Run Before Manual QA)
- [x] Backend tests pass
  - Command: `cd backend && .\.venv\Scripts\python.exe manage.py test tests -v 2`
  - Expected: `OK` with no failures.
- [x] Frontend build passes
  - Command: `cd frontend && npm run build`
  - Expected: Vite build succeeds.
- [x] Smoke checks pass
  - Command: `powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost demo.localhost -BackendScheme http -FrontendScheme http -BackendPort 8000 -FrontendPort 5173`
  - Expected: all checks `[PASS]`.
- [x] Customer-flow smoke checks pass
  - Command: `powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -TenantHost demo.localhost -ApiPort 8000 -WebPort 5173 -TableSlug table-1`
  - Expected: all checks pass for `/menu`, `/browse`, `/cart`, `/reserve`, `/t/<slug>`, and table-context carryover.

## Environment Prep
- [ ] Host mapping exists for local tenant domains (`demo.localhost`, test tenant slugs).
- [ ] Backend is reachable on `http://demo.localhost:8000`.
- [ ] Frontend is reachable on `http://demo.localhost:5173`.
- [ ] Demo data is seeded (plans + tenant + menu + owner).

## Credentials (Local QA)
- Super admin: `admin@example.com` / `Admin123!`
- Tenant owner: `test_resto_user` / `Owner123!`

## Global UX/Quality Gates
- [ ] No console errors on key pages.
- [ ] Mobile view (390x844) works without overflow breaks.
- [ ] Buttons have clear labels and predictable actions.
- [ ] No dead links in top nav / bottom nav.
- [ ] Language and naming are consistent (`Restaurant landing`, `Menu browse`, `Reserve`).

## Landing Interface QA
Base URL: `http://demo.localhost:5173/`

- [ ] Home page loads with CTA buttons.
- [ ] `View restaurant landing` opens `/menu`.
- [ ] `View menu browse` opens `/browse`.
- [ ] `Get started` opens `/get-started`.
- [ ] `Contact` opens `/contact`.
- [ ] Footer links (`Privacy`, `Terms`, `Contact`) load.

### Lead Capture QA (`/get-started`)
- [ ] Validation blocks submit with empty required fields.
- [ ] Valid lead submits successfully.
- [ ] Success state appears.
- [ ] Plan query prefill works (`/get-started?plan=basic`, `growth`, `pro`).

## Customer Interface QA
Primary URLs:
- `http://demo.localhost:5173/menu` (restaurant landing)
- `http://demo.localhost:5173/browse` (menu browse)
- `http://demo.localhost:5173/cart` (cart)
- `http://demo.localhost:5173/reserve` (reservation form)

### Customer Landing (`/menu`)
- [ ] Hero renders restaurant information correctly.
- [ ] Quick actions work (`Browse menu`, `Reserve`, social/contact links).
- [ ] Lead form validates and submits.
- [ ] Sticky mobile CTA appears on small screens.

### Menu Browse (`/browse`)
- [ ] Categories list loads.
- [ ] Search filters categories.
- [ ] Sort mode changes order.
- [ ] Category card click opens category page.
- [ ] Sticky cart summary appears when cart has items.

### Dish and Cart
- [ ] Dish page loads from category.
- [ ] Variant options can be selected.
- [ ] Quantity changes update pricing.
- [ ] Add to cart succeeds.
- [ ] Cart shows correct line totals and order total.
- [ ] Cart supports quantity increments/decrements and item removal.
- [ ] WhatsApp order button opens handoff URL (Basic plan flow).

### Reservation (`/reserve`)
- [ ] Form validates required fields.
- [ ] Quick party-size chips update value.
- [ ] Submit creates success state.
- [ ] Sticky mobile submit CTA works.

### Table Context
- [ ] Open `http://demo.localhost:5173/t/<valid-table-slug>`.
- [ ] Table label is reflected in customer context/cart.
- [ ] Invalid/disabled table slug is handled gracefully.

## Owner Interface QA
Base URL: `http://demo.localhost:5173/owner`

- [ ] Owner login works.
- [ ] Dashboard renders readiness, analytics, and quick actions.
- [ ] Navigation between dashboard/onboarding/tables/reservations/launch works.
- [ ] `Landing preview` opens `/menu`; `Menu preview` opens `/browse`.

### Onboarding (`/owner/onboarding`)
- [ ] Step navigation works end-to-end.
- [ ] Brand info saves.
- [ ] Category create/edit/delete works.
- [ ] Dish create/edit/delete works.
- [ ] Dish variants (e.g., extra cheese) save correctly.
- [ ] Theme step saves.
- [ ] Publish step changes menu to published state.

### Tables (`/owner/tables`)
- [ ] Create single table works.
- [ ] Bulk generate works.
- [ ] QR preview renders per table.
- [ ] Copy full/short links works.
- [ ] Download single QR PNG works.
- [ ] Export CSV works.
- [ ] Export HTML pack works.
- [ ] Server ZIP/PDF exports work.
- [ ] Enable/disable table updates status.

### Reservations (`/owner/reservations`)
- [ ] List loads with counts.
- [ ] Filters (status, reminder status, search, date) work.
- [ ] Status update actions work (`contacted`, `won`, `lost`, `new`).
- [ ] Reminder action opens WhatsApp and logs state.
- [ ] Bulk actions work for selected reservations.
- [ ] Timeline open/add-note works.

## Super Admin Interface QA
Base URL: `http://demo.localhost:5173/admin-console`

- [ ] Admin login works.
- [ ] Leads load and show source/tenant context.
- [ ] Provision preview check works.
- [ ] Provision action succeeds.
- [ ] Resend activation works for live leads.
- [ ] Load onboarding package works.
- [ ] Archive lead works.

### Reservation Alerts
- [ ] Alerts endpoint data renders.
- [ ] Alert filters (`all`, `overdue`, `due_soon`) work.
- [ ] Tenant owner inbox links open correctly.

### Upgrade Requests
- [ ] Mobile card mode displays requests on small screens.
- [ ] Desktop table displays requests on medium+ screens.
- [ ] Approve/reject actions work.
- [ ] Inactive target plan blocks approval.

### Provisioning Jobs and Audit
- [ ] Jobs load in mobile cards and desktop table.
- [ ] Audit logs load in mobile cards and desktop table.
- [ ] Metadata formatting is readable.

## Security and Policy Checks
- [ ] Anonymous user cannot access owner/admin routes.
- [ ] Non-admin user cannot access admin console.
- [ ] Browse-only behavior blocks ordering actions where applicable.
- [ ] Unpublished/disabled menu policy behavior is enforced.

## Final Go/No-Go
- [ ] All automated checks pass.
- [ ] All manual role flows pass.
- [ ] No blockers in console/network logs.
- [ ] Backup + rollback plan confirmed (see `infra/DEPLOYMENT_RUNBOOK.md`).
- [ ] Release approved.
