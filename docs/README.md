# Kepoli documentation — index

This `docs/` folder is the **canonical, curated documentation** for Kepoli. It exists because
the project accumulated 30+ point-in-time `.md` files at the repo root (launch checklists, QA
runs, phase plans) with **no single authoritative architecture reference**. Start here.

## Read in this order

1. **[`../CLAUDE.md`](../CLAUDE.md)** — the fast on-ramp: how to run/verify, the traps, the
   invariants. Read every session.
2. **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — the canonical system architecture: the two-plane
   tenancy model, data/money flow, request lifecycle, identity/authz, async/realtime, frontend,
   deployment. **The single source of truth for how Kepoli is built and why.**
3. **[`RISK_REGISTER.md`](RISK_REGISTER.md)** — the honest, ranked known-debt from the ground-up
   review, each item with a failure scenario, fix, and effort. **Read before any scaling/onboarding.**
4. **[ADRs](adr/)** — the reasoning + honest consequences behind each load-bearing decision.

## Architecture Decision Records

| ADR | Decision | Verdict |
|---|---|---|
| [0001](adr/0001-schema-per-tenant.md) | Schema-per-tenant multitenancy (django-tenants) | Fine for low-hundreds of tenants; **decide the ceiling** |
| [0002](adr/0002-money-in-public-schema.md) | Money/drivers/directory in the public schema; loose cross-schema refs | Forced by 0001; carries an integrity gap |
| [0003](adr/0003-closed-loop-wallet-ledger.md) | Hand-rolled closed-loop wallet + append-only ledger | Best-engineered part; one missing invariant |
| [0004](adr/0004-dual-identity-and-authz.md) | Dual identity, shared cookie, authz-by-convention | **#1 liability — change planned** |
| [0005](adr/0005-i18n-dual-source.md) | Hand-rolled i18n runtime, dual-source catalog | Known footgun; collapse to one source |
| [0006](adr/0006-testing-strategy.md) | pytest, mock-first, throwaway Postgres | Pragmatic; mock-first = false confidence |
| [0007](adr/0007-single-node-deploy.md) | Single-VPS Coolify, one Postgres/Redis, manual deploy | Great single-node hygiene; **2 critical DR gaps** |
| [0008](adr/0008-superapp-capability-seam.md) | Super-app capability seam (business_type/verticals) | Disciplined; strategic sequencing is the risk |
| [0009](adr/0009-async-realtime.md) | Celery-optional, generic cron task, Channels-as-hints | Thoughtful; fix before volume |

> **Writing a new ADR?** Copy the shape of an existing one: Status · Context · Decision ·
> Consequences (Good / Bad-honest, linking `RISK_REGISTER` ids) · Alternatives · When to revisit.
> Number it sequentially. When a decision changes, add a new ADR that supersedes the old one
> (mark the old one `Superseded by ADR-XXXX`) rather than rewriting history.

---

## The pre-existing root docs (classified)

These remain in the repo. This table tells you which are still authoritative, which are useful
deep-dives, and which are point-in-time snapshots you should read as history, not truth.
**Nothing here is deleted** — where a root doc conflicts with the canonical set above, the
canonical set wins.

### Authoritative deep-dives (keep using)
| Doc | Scope |
|---|---|
| `Tenant_Routing_and_API_Architecture.md` | Routing/subdomain detail — complements ARCHITECTURE §3–4 |
| `frontend/src/styles/UI_SYSTEM.md` | Design-system contract (the QA gate for UI work) |
| `I18N_Content_Model_Strategy.md` | i18n content model — read with [ADR-0005](adr/0005-i18n-dual-source.md) |
| `infra/DEPLOYMENT_RUNBOOK.md`, `infra/README.md` | Ops runbook + infra — read with [ADR-0007](adr/0007-single-node-deploy.md) |
| `infra/COOLIFY_*.md`, `platform/DEPLOY_COOLIFY.md`, `platform/README.md` | Coolify env/DNS/backup/monitoring specifics |
| `SaaS_Roadmap.md`, `restaurant-saas-tiers.md` | Product roadmap + plan tiers |

### Point-in-time snapshots (read as history)
`DAILY_USE_AUDIT.md`, `Pre_Deployment_QA_Checklist.md`, `First_Tenant_Production_QA.md`,
`Launch_Closure_Plan.md`, `Release_Candidate_Freeze.md`, `VPS_Deployment_Readiness_Report.md`,
`Kepoli_Perf_SEO_Hardening_Checklist.md`, `Kepoli_Production_Smoke_Execution.md`,
`Order_Flow_E2E_QA.md`, `Phase_Tasks_With_Tests.md`, `Specific_Phases_Checklist.md` — these
captured the state at a specific milestone. Useful for "what did we verify at launch," but
**not** a current description of the system. For that, use `ARCHITECTURE.md` + `RISK_REGISTER.md`.

> **Cleanup suggestion (needs owner sign-off):** once you're confident the canonical set covers
> everything, consider moving the point-in-time snapshots into a `docs/history/` folder to
> de-clutter the root. Not done automatically — file moves/deletes need explicit direction.
