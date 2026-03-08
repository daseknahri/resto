# Specific Phases to Follow (Execution Checklist)

## Phase 0: Setup and Standards (Day 1-2)
- [ ] Create mono-repo structure (`backend/`, `frontend/`, `infra/`)
- [ ] Configure `.env` strategy for dev/prod
- [ ] Add CI checks (lint + tests)
- [ ] Define coding and naming conventions

Exit Criteria:
- [ ] Local dev starts with one command for backend and frontend
- [ ] Base CI pipeline passes

## Phase 1: Multi-Tenant Core (Week 1)
- [ ] Add tenant model and subdomain routing
- [ ] Add user roles and permission matrix
- [ ] Add plan + feature flag tables
- [ ] Add tenant middleware and API scoping

Exit Criteria:
- [ ] Tenant A cannot access Tenant B data
- [ ] Feature flags readable in API and UI

## Phase 2: Menu Management CMS (Week 2)
- [ ] Category CRUD
- [ ] Dish CRUD with image, price, description
- [ ] Dish options/add-ons model
- [ ] Publish/unpublish toggle

Exit Criteria:
- [ ] Restaurant owner can create and publish full menu

## Phase 3: Customer Mobile Experience (Week 3)
- [ ] Home screen with logo/social/map/reservation/menu
- [ ] Category visual cards
- [ ] Dish list and detail screens
- [ ] Fast mobile navigation and loading

Exit Criteria:
- [ ] Mobile Lighthouse performance acceptable on real device

## Phase 4: Starter Cart (Week 4)
- [ ] Cart state in Pinia
- [ ] Add/remove/update quantity
- [ ] Notes per item
- [ ] Total summary
- [ ] Disable checkout for Starter and show contact CTA

Exit Criteria:
- [ ] User can complete selection flow without errors
- [ ] No order-submit endpoint exposed for Starter

## Phase 5: Super-Admin Sales Console (Week 5)
- [ ] Lead model and pipeline stages
- [ ] Deal page with `Confirm Sale` action
- [ ] Provisioning service (tenant + owner creation)
- [ ] Activation token and onboarding link generation
- [ ] Message template for credentials + tenant URL

Exit Criteria:
- [ ] Super-admin can convert paid lead to live tenant in minutes

## Phase 6: Marketing Landing and Lead Capture (Week 6)
- [ ] Landing page with value proposition and demo
- [ ] Pricing section (Starter active)
- [ ] Lead capture form -> CRM table
- [ ] CTA buttons for WhatsApp/contact/demo

Exit Criteria:
- [ ] New lead appears in admin immediately after submission

## Phase 7: Deployment and Operations (Week 7)
- [ ] Docker Compose production stack
- [ ] Nginx reverse proxy and SSL
- [ ] PostgreSQL backup schedule
- [ ] Centralized logs and alerting
- [ ] Error monitoring integration

Exit Criteria:
- [ ] Blue/green or safe deploy process documented
- [ ] Restore test from backup succeeds

## Phase 8: Launch and Early Sales (Week 8)
- [ ] Test tenant isolation and onboarding flow end-to-end
- [ ] Onboard first pilot restaurants
- [ ] Collect onboarding friction and usage analytics
- [ ] Publish iteration backlog

Exit Criteria:
- [ ] First paying restaurants are live
- [ ] Next sprint priorities based on real usage data

## Next Milestones (Post-Launch)
- [ ] Enable Growth plan: WhatsApp order submit
- [ ] Add billing and subscription lifecycle
- [ ] Add analytics dashboard for tenants
- [ ] Add premium plan capabilities
