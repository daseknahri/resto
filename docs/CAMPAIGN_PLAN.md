# Kepoli hardening campaign — execution plan

> Living tracker for the multi-branch tech-debt campaign that follows the launch-readiness
> work. **Source of truth for risks is [`RISK_REGISTER.md`](RISK_REGISTER.md); this file is the
> *execution* layer** — waves, lanes, collision map, and per-item status. Generated from a
> 28-agent code-verification sweep (2026-07-11) that checked every register item against the
> real code, so several "open" items below are corrected to their true state.

## Operating rules (how this campaign runs safely)

- **One branch per item, off `main`, fully tested, committed — never merged by the campaign.**
  The owner merges each via PR (established flow); we verify it landed on `origin/main` before
  building anything that depends on it.
- **Collision-aware parallelism.** Items whose file sets are **disjoint** run as parallel git
  worktrees. Items that share a hot file (`menu/views.py` 13.4k, `accounts/views.py` 8.7k,
  `config/settings.py`, the 3 url-files, i18n `messages*.js`, `menu/signals.py`) run **one at a
  time** — parallel edits there create merge conflicts the owner would have to resolve.
- **Sonnet workers, Opus orchestration.** Implementation agents are Sonnet; verification of the
  money/auth path is adversarial, not just "tests pass".
- **Three buckets:** `CODE` (an agent fleet implements + tests it), `OWNER` (infra / cloud
  accounts / credentials — agent may draft config + runbook, owner applies), `DECISION` (a
  product/strategy call only the owner can make).

## Code-verified backlog (real status ≠ register in several places)

Legend — Status: real state after grepping code. Bucket: CODE/OWNER/DECISION. Lane: which
merge lane (see waves). `hot` = touches a shared god-file (serialize).

| ID | Real status | Bucket | Risk | Lane | Notes / correction vs register |
|---|---|---|---|---|---|
| **AUTHZ-1** | partial | CODE | low→high | A | Backstop + partial policy layer already exist. Slice 1 (add `IsTenantOwner`) is additive/low-risk. Real completion = **1b** migrate `accounts/views.py` (9 sites) + **1c** migrate `menu/views.py` (50 sites) — both `hot`, sequential, human-review before merge. |
| **IDENTITY-1 sweep** | partial | CODE | med | A | ~55 customer/driver views still read `session["customer_id"]`. `hot` (accounts/views.py). Landmine: multi-role staff gates. |
| **SER-1** | open | CODE | **high** | A | 242 raw `request.data` reads on money endpoints. `hot` (both god-files). Do after auth is unified; slice money endpoints first. |
| **STRUCT-1** | open | CODE | **high** | A | Extract `OrderService` from the ~1,100-line `PlaceOrderView.post`. `hot` (menu/views.py). **Flag for explicit owner go-ahead** — money path. |
| **DATA-1** | partial | CODE | med | A | Residual: global-unique `order_number` (currently per-schema unique). `hot` + migration. |
| **API-1** | open | CODE | low | B-urls | Add `/api/v1/` alias; legacy path stays default. Touches 3 url-files. |
| **API-2** | open | CODE | low | B-urls | Naming/RPC-verb cleanup in the same 3 url-files → sequential with API-1. |
| **SCHEMA-1** | open | CODE | low | **W1** | drf-spectacular; config/CI only, no view edits. |
| **ASYNC-2** | open | CODE | low | B-cfg | `CELERY_TASK_ROUTES` split cron vs notifications. Touches settings.py/celery.py. |
| **ASYNC-1** | partial | CODE | med | B-cfg | Broker-required-in-prod (fail-closed) instead of silent inline executor. Same Celery section → sequential with ASYNC-2. |
| **ASYNC-4** | partial | CODE | low | B-cfg | Residual: DLQ / reject-alert on top of shipped dedupe. |
| **OPS-3** | open | CODE | med | B-cfg | Schema-pinned session backend (naive `cached_db` is broken under django-tenants). settings.py. |
| **DATA-2** | partial | CODE | low | **W1** | **Register overstates.** Re-mirror already works (post_save fires on `update_fields`). Real residual = exclude voided/comped items from `items_snapshot`. |
| **DATA-5** | partial | CODE | low | **W1** | **Register overstates** ("scattered signals" — they're co-located). Real gap = no periodic reconcile command. Additive. |
| **FE-1** | open | CODE | low | C-fe | i18n dual-source consolidation. `hot` (messages*.js). |
| **FE-2** | open | CODE | low | C-fe | Split six 2.5–3.7k-line Vue mega-pages, tab by tab. Each page = own branch. |
| **FE-3** | **mostly done** | CODE | low | C-fe | **Already shipped** in `a84cc7d` (code-split locale catalogs + lazy Sentry). Residual = `main.js` first-paint still awaits active locale + no `localeLoader` test. |
| **DATA-3** | decision | DECISION | high | — | `Dish` + 4-key JSON isn't a real multi-vertical catalog. Contained today (serializer whitelists 4 keys). Needs product call before building. |
| **STRUCT-2** | open | CODE | high | — | Squash `menu` migrations 0001–0057. Migration-order risk; serialize against any item adding a menu migration. |
| **OPS-1** | open | OWNER | high | — | Postgres PITR/replica. Agent can draft compose/WAL config + runbook; owner provisions. |
| **OPS-2** | **mechanism built** | OWNER | low | — | **Register overstates.** Off-box `--remote-copy-cmd` hook + freshness probe already exist; awaiting owner S3 creds + restore drill. |
| **MULTITENANCY-1** | decision | DECISION | med | — | Pick the tenant ceiling (schema-per-tenant vs shared+RLS). ADR update, owner decides. |

**Already ✅ done (do not touch):** MONEY-1/2/3, TEST-1, DATA-4, plus the merged partials'
first slices: AUTHZ-1 backstop, IDENTITY-1 keystone, DATA-1 orphan reconcile, ASYNC-4 dedupe.

## Wave plan

**Wave 1 — parallel, disjoint files, low-risk (in flight 2026-07-11):**
- `fix/authz-1-tenant-owner-permission` — AUTHZ-1 slice 1 (`sales/permissions.py`)
- `fix/schema-1-drf-spectacular` — SCHEMA-1 (`requirements.txt`, `config/*`, `ci.yml`)
- `feat/data-5-reconcile-profile-denorms` — DATA-5 (new command)
- `fix/data-2-mirror-item-filter` — DATA-2 (`menu/signals.py`)
- `chore/campaign-plan-register-truthup` — this doc + register accuracy fixes (docs only)

**Wave 2 — config/url lanes (serialize within each lane):**
- Lane B-cfg (settings/celery): ASYNC-2 → ASYNC-1 → OPS-3 → ASYNC-4 residual
- Lane B-urls (url-files): API-1 → API-2
- Lane C-fe (frontend): FE-2 (page by page, parallel across *different* pages) + FE-1 + FE-3 residual

**Lane A — the god-file auth/structure stack (STRICTLY sequential, human-reviewed):**
AUTHZ-1b (accounts) → AUTHZ-1c (menu) → IDENTITY-1 sweep → SER-1 (money endpoints) →
STRUCT-1 (`OrderService`, owner go-ahead first). Each merged before the next starts.

**Owner track (surfaced, not auto-done):** OPS-1 (PITR), OPS-2 (S3 creds + restore drill),
MULTITENANCY-1 (ceiling decision), DATA-3 (catalog decision).

## Status log

- 2026-07-11 — 28-agent verification sweep complete; Wave 1 launched (4 code worktrees + this doc).
