# ADR-0006: Testing strategy — pytest, mock-first, throwaway Postgres

- **Status:** Accepted — pragmatic, but the mock-first default creates false confidence
- **Date:** documented 2026-07-10
- **Related risk:** [TEST-1](../RISK_REGISTER.md)

## Context
The team develops on Windows with **no local Postgres by default**, wants a fast local loop, and
needs CI to gate merges. django-tenants makes DB tests heavier (schema setup per run).

## Decision
- **pytest** (`pytest.ini` sets `DJANGO_SETTINGS_MODULE=config.settings`). CI runs
  `python -m pytest tests` and installs `requirements-dev.txt` (pytest/pytest-django/pytz/pypdf,
  kept out of the prod image + CVE scan).
- **Mock-first:** most tests are `SimpleTestCase` + `MagicMock` so they run with **no DB**. DB-backed
  tests (`TestCase`/`TransactionTestCase`) are the minority and **self-skip / error** when Postgres
  is absent.
- **Local DB runs** use a **throwaway Postgres cluster** (documented in `CLAUDE.md` /
  `project_resto_local_verify` memory), not the developer's real DB.
- A backend **ruff** gate (`F` rules only) catches undefined-name/unused-import bugs; frontend gates
  are `verify:i18n` / `lint` / `build` / `vitest`.

## Consequences

### Good
- Fast local loop; the bulk of the suite runs without any DB.
- The full suite **does** pass against real Postgres (verified via the throwaway cluster:
  4,681 passed / 0 failed).
- The ruff gate exists because a real class of NameError bugs had shipped (unimported `Q`/`F`).

### Bad / honest tradeoffs (why "questionable")
- **Many mock tests patch the very machinery they claim to protect** — `WalletTransaction.objects`,
  `transaction.atomic`, `select_for_update`. They verify Python control flow, **not** the money or
  isolation invariant. The high pass-count is partly false confidence. (TEST-1)
- **DB tests self-skip.** One CI infra hiccup and the DB tests silently skip → CI goes green with
  **zero DB tests run**, and a real concurrency/isolation regression ships unnoticed. (TEST-1)
- **The Playwright E2E specs exist but aren't wired into CI** — including the cross-subdomain-CSRF
  test, exactly the kind that would catch an AUTHZ-1 regression. (TEST-1)
- **Mock blind spots** documented from real incidents: `save(update_fields=[...])` with a nonexistent
  field passes the mock but 500s in prod; a mock stubbing a queryset that the prod code later calls
  a second `aggregate()` on silently breaks. (See `project_resto_local_verify` memory.)

## Alternatives considered
- **DB-first / factory-based integration tests** for money + isolation paths — slower but they test
  the real invariant. The right target for the highest-value paths.

## When to revisit
Now, as part of hardening (TEST-1): make DB tests **fail, not skip**, when the DB is absent in CI;
wire the E2E suite into CI; add a **test-count floor** so a collection error can't silently drop
tests; convert the top money/isolation mocks into real DB integration tests. Keep mock-first for
pure-logic tests where it's genuinely appropriate.
