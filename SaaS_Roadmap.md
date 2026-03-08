# Restaurant SaaS Roadmap (Launch Fast, Scale Later)

## 1) Product Goal
Build a mobile-first online menu SaaS for restaurants using a strong Starter tier first, then unlock advanced tiers later without refactoring.

## 2) Subscription Strategy

### Starter (Sell Now)
- Public branded menu
- Category and dish browsing
- Cart as "selection basket" (no checkout submit)
- CTA to call/WhatsApp manually

### Growth (Prepare, Hide)
- Starter + place order via WhatsApp deep link (`wa.me`)
- Order saved in DB before redirect

### Pro (Future)
- Growth + analytics, multi-branch, custom domain, advanced integrations

## 3) Recommended Stack
- Backend: Django + DRF + PostgreSQL
- Multi-tenancy: `django-tenants` (subdomain model)
- Frontend: Vue 3 + Pinia + Tailwind CSS
- Infra: Nginx + Gunicorn + Docker Compose
- Optional async: Redis + Celery

## 4) Architecture Principles
- Tenant isolation from day 1
- Feature flags by plan (`can_checkout`, `can_whatsapp_order`, etc.)
- Role-based access: `platform_superadmin`, `tenant_owner`, `tenant_staff`
- Feature gating in both API and UI
- Keep data models for future tiers now, hide unavailable features

## 5) 8-Week Delivery Roadmap

### Week 1: Foundation
- Set up project, tenancy, auth, roles, permissions
- Define plan and feature-flag models
- Deliverable: secure tenant-aware base

### Week 2: Tenant Menu CMS
- CRUD categories, dishes, options, prices, images
- Menu publish/unpublish
- Deliverable: owner can build full menu

### Week 3: Mobile Customer App
- Landing page: logo, social, map/reviews, reservation, menu CTA
- Category cards and dish listing (mobile-first)
- Deliverable: polished browsing UX

### Week 4: Starter Cart (No Checkout)
- Add/remove items, quantity, notes, total
- Block checkout by plan and show contact CTA
- Deliverable: sellable Starter tier

### Week 5: Super-Admin Sales Console
- Leads, deals, tenants, subscriptions, provisioning statuses
- `Confirm Sale` action to provision tenant + owner account
- Deliverable: operational sales workflow

### Week 6: Landing Page + Funnel
- Marketing page on main domain
- Pricing: Starter live, Growth/Pro marked "Coming Soon"
- Lead form connected to admin CRM
- Deliverable: ready to acquire customers

### Week 7: Production Deployment
- Deploy Docker stack on Hostinger VPS
- HTTPS, backups, logging, monitoring
- Subdomain routing for tenants
- Deliverable: stable production environment

### Week 8: QA + Launch
- Multi-tenant security and mobile UX validation
- Onboard first 5-10 restaurants
- Deliverable: revenue-ready baseline SaaS

## 6) Super-Admin Confirm-Sale Flow
1. Mark deal as `paid`
2. Auto-provision tenant (`slug.yourdomain.com`)
3. Create owner account + activation token
4. Send onboarding message with URL and secure activation link
5. Owner logs in and completes setup wizard
6. Owner publishes menu

## 7) Messaging Policy
- Do not send plain passwords
- Send one-time activation link (short expiry)
- Keep onboarding message short and actionable

## 8) Build Now vs Later

### Build Now
- Starter plan
- Tenant onboarding wizard
- Super-admin sales console
- Public landing page
- Production deployment and backups

### Prepare Now (Hidden)
- Order tables and statuses
- WhatsApp message formatter
- Checkout endpoints behind feature flags

### Build Later
- WhatsApp order submit
- Subscription billing automation
- Advanced analytics and premium capabilities

## 9) KPI Dashboard (Day 1)
- Lead -> Paid conversion
- Paid -> Live activation time
- Onboarding completion rate
- Active tenant count
- 30/60-day retention
- Average setup time per client
