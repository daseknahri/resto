# Restaurant SaaS Platform - Tier Specification

## Overview

This document defines the tier strategy for the restaurant SaaS platform.

The product has three progressive tiers:

1. Basic (`basic`, internal plan code: `starter`)
2. Growth (`growth`)
3. Pro (`pro`)

Current business decision:

- Launch and complete Tier 1 first.
- Tier 1 includes WhatsApp ordering (not menu-only).
- Tiers 2 and 3 remain planned and inactive until Tier 1 is fully stable in production.

---

## Tier 1 - Basic (Launch Tier)

### Positioning

For small restaurants that need fast digital presence and simple order intake through WhatsApp.

### Core Capabilities

- QR code menu access
- Public menu pages (mobile-first)
- Categories, dishes, images, pricing, availability
- Cart experience
- WhatsApp order handoff (pre-formatted message)
- Owner onboarding wizard and publish controls

### Customer Flow

1. Customer scans QR code
2. Menu opens
3. Customer adds dishes to cart
4. Customer sends order via WhatsApp handoff
5. Restaurant receives order message on WhatsApp

### Included in Basic

- No in-app payment checkout
- No internal order lifecycle dashboard
- No kitchen display workflow

### Success Criteria Before Tier 2

- Stable provisioning flow (lead -> tenant -> activation -> onboarding -> publish)
- Reliable WhatsApp handoff API with plan/menu-state enforcement
- Production-ready admin operations for onboarding and support
- Clean owner and customer UX with low support friction

---

## Tier 2 - Growth (Planned, Not Launched)

### Goal

Move from handoff ordering to in-platform operational ordering.

### Planned Capabilities

- Internal order management dashboard
- Order status workflow (new, accepted, preparing, ready, completed)
- Table-aware order tracking
- Kitchen display integration baseline

### Launch Condition

Enabled only after Tier 1 is fully validated in production.

---

## Tier 3 - Pro (Planned, Not Launched)

### Goal

Provide advanced commercial and operational tools for larger restaurants.

### Planned Capabilities

- Checkout and payment integrations
- Advanced analytics and reporting
- Staff and role management extensions
- Multi-branch capabilities

### Launch Condition

Enabled only after Growth is stable and support model is mature.

---

## Technical Entitlements

Entitlements are enforced by plan flags and tenant metadata:

- `can_whatsapp_order`
- `can_checkout`
- `ordering_mode` (`whatsapp` or `checkout` or `menu_only`)

Current expected entitlement states:

- Basic: `can_whatsapp_order=true`, `can_checkout=false`
- Growth: planned (inactive)
- Pro: planned (inactive)

---

## Upgrade Flow (Cash-First)

1. Owner clicks "Purchase tier" in owner workspace.
2. System creates an upgrade request.
3. Admin confirms cash payment.
4. Admin approves request in admin console.
5. Tenant plan is switched and new entitlements apply immediately.

---

## Suggested Pricing (Draft)

- Basic: launch price point
- Growth: premium for operations workflow
- Pro: premium-plus for payments and advanced controls

Final pricing should be validated by region, support load, and sales conversion data.
