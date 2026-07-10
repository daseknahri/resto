# ADR-0008: Super-app capability seam (business_type → capabilities, verticals, one wallet)

- **Status:** Accepted — disciplined at the code level; the risk is strategic sequencing
- **Date:** documented 2026-07-10
- **Related risk:** [DATA-3](../RISK_REGISTER.md); strategic (see ARCHITECTURE §11)

## Context
Kepoli started as a restaurant SaaS and is being generalized into a "Kepoli" umbrella super-app
(food + shops + delivery + future courier/ride-hail) under one customer identity and one wallet.
The question was how to add verticals without forking the codebase or letting scope explode.

## Decision
A **capability seam** rather than per-vertical apps:
- `Profile.business_type` → a `capabilities` set that gates features (e.g. dine-in is off for a
  shop). Marketplace listing is filtered by type.
- `VERTICALS_ENABLED` gates whole verticals; non-food ones sit at `coming_soon`.
- **One identity, one global wallet** across every vertical.
- Retail/pharmacy currently ride on the restaurant `Dish` model + a 4-key `attributes` JSON blob
  (`sku, barcode, brand, unit`); a `Dish → Item` rename is deferred.

## Consequences

### Good
- **Unusually disciplined scope management** — the seam is real and enforced, not scattered
  `if business_type == ...` checks. This is *not* scope creep at the code level.
- One wallet + one identity is the right foundation for a genuine super-app.
- Verticals can be dark-launched (`coming_soon`) without shipping half-built surfaces to users.

### Bad / honest tradeoffs
- **`Dish` + a 4-key JSON is not a real multi-vertical catalog** — no variants, tax class, expiry,
  dosage, or controlled-substance fields. It's a restaurant model wearing a shop costume. The first
  serious retail/pharmacy tenant forces either an unqueryable JSON free-for-all or the deferred
  `Dish→Item` migration across 76 migrations. (DATA-3)
- **Strategic sequencing is the real liability** (not code): live security/support surface exists
  for shelved verticals (rides ≈ 1,733 LOC, retail/pharmacy) earning **zero revenue**, while the
  actual revenue levers — multi-branch, inventory, a PSP — are still ahead of them. Breadth was
  built before the depth that wins paying restaurant operators.

## Alternatives considered
- **Per-vertical Django apps / services.** More isolation, far more duplication and coordination;
  overkill before any vertical has a paying customer. The capability seam is the better call *for
  the code*.
- **Depth-first single vertical.** The recommended *product* posture (below), orthogonal to the
  code seam.

## When to revisit
- **Product (now):** go **depth-first on restaurant** — multi-branch, inventory, POS/printer bridge
  are all sellable *today* on the closed-loop wallet with **no PSP**. Hold every non-food vertical
  at `coming_soon` until a **paying partner pulls** one.
- **Catalog (when a paying non-food tenant is real):** design a neutral `Product` + typed
  `product_kind` + per-vertical satellite tables (DATA-3), and do the `Dish→Item` rename then —
  not speculatively.
