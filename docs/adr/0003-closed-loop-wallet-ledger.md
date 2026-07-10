# ADR-0003: Hand-rolled closed-loop wallet with an append-only ledger

- **Status:** Accepted — the best-engineered part of the system; one invariant still missing
- **Date:** documented 2026-07-10
- **Related risk:** [MONEY-1](../RISK_REGISTER.md), [MONEY-2](../RISK_REGISTER.md), [MONEY-3](../RISK_REGISTER.md)

## Context
Kepoli needs to move money between customers, restaurants, and drivers **before** it has a
payment-service-provider (PSP) account. A closed-loop wallet (funds enter via top-up, circulate
internally, exit via payout) lets the whole marketplace run on internal balances today, with
Stripe wired as a dormant seam for later external settlement.

## Decision
Implement money in `accounts/wallet_service.py` as a **closed-loop wallet**:
- **Denormalized balances** (`Customer.wallet_balance`, `Tenant.float_balance`) for fast reads.
- **Append-only journals** (`WalletTransaction`, `TenantFloatTransaction`) — every row immutable,
  `amount` a positive magnitude, direction in `type`, with a `balance_after` snapshot.
- **Idempotency at two layers:** a DB `unique` constraint on `idempotency_key`, **and** a re-check
  of `_find_idempotent(key)` *after* `select_for_update` takes the row lock, so concurrent
  same-key requests replay the first result instead of double-applying or 500-ing.
- **Deadlock-safe** multi-row lock ordering; `Decimal` throughout; MAD single-currency (no FX).

## Consequences

### Good
- The locking + post-lock idempotency re-check is textbook and applied **consistently** across
  credit/debit/transfer/float. This is the hardest thing to get right and it's right.
- Append-only journals with `balance_after` give a full, immutable audit trail.
- Runs the whole marketplace **with no PSP** — the biggest revenue-unblocking property of the
  design (restaurant + delivery are sellable today on internal balances).

### Bad / honest tradeoffs
- **No `balance == sum(ledger)` invariant.** The denormalized balance is what the app spends
  against, and nothing reconciles it to the journal. A stray write or a crash mid-move produces
  silent, permanent, undetected drift (MONEY-1) — the scariest correctness gap in the codebase.
- **The driver-payout "owed" check reads an unlocked aggregate** → double-pay race (MONEY-2).
- **The dormant Stripe webhook would credit session metadata, not the settled `amount_total`**
  (MONEY-3) — must be fixed before the PSP goes live.
- Hand-rolled means the invariants live in code + review discipline, not a library.

## Non-negotiable invariants (never regress)
- The driver cash-out **6-digit code is a live bearer credential — never log it.**
- **Idempotency keys derived from tenant-local ids must be schema-namespaced** — a bare
  tenant-local id collides across schemas in the shared public journal.
- **Every mutation re-checks idempotency under the `select_for_update` lock.**

## Alternatives considered
- **An off-the-shelf double-entry ledger library / Stripe-only.** Rejected for launch: Stripe
  needs an account Kepoli doesn't yet have, and a closed loop is exactly what lets the app earn
  before that. Revisit a formal double-entry model if accounting/tax needs grow.

## When to revisit
Add the `reconcile_wallet_balances` assertion job **now** (MONEY-1 — cheap, highest-value). Lock
the payout path (MONEY-2). Harden the Stripe webhook before enabling the PSP (MONEY-3). Consider a
formal double-entry ledger only if regulatory/accounting requirements demand it.
