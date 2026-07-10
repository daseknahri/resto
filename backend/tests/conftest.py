"""Suite-wide pytest hooks.

RISK TEST-1 (item 1) — DB tests must FAIL, not skip, when the DB is absent in CI.

Some DB-backed tests guard themselves with an import-time "is Postgres reachable?"
probe and skip when it isn't (e.g. test_mfa_totp.py). That is the right behavior
locally (no Postgres on dev machines — see CLAUDE.md), but in CI it is a
false-green machine: if the Postgres service dies or misconfigures, the DB tests
quietly skip and the run can still look healthy.

CI sets PYTEST_REQUIRE_DB=1 (see .github/workflows/ci.yml, "Backend tests" step).
When it is set, this hook asserts Postgres is reachable BEFORE any test runs and
aborts the whole session loudly if it isn't; the per-file guards (via _dbprobe)
also re-raise instead of skipping. Locally the variable is unset and nothing
changes. This complements (not replaces) the passed-floor/skip-ceiling check in
the workflow: that guard catches a shrunken suite after the fact; this one names
the root cause up front.

The probe deliberately uses the raw driver, not django.db.connection — see
_dbprobe.py for why (pytest-django's access blocker made the old in-file probe
always fail under pytest, so the MFA DB tests never actually ran in CI).
"""
import pytest

import _dbprobe


def pytest_sessionstart(session):
    if not _dbprobe.db_required():
        return
    try:
        _dbprobe.db_available()  # raises when required and unreachable
    except Exception as exc:
        raise pytest.UsageError(
            "PYTEST_REQUIRE_DB is set but Postgres is unreachable "
            f"({exc.__class__.__name__}: {exc}). DB-backed tests would self-skip "
            "and the run could pass falsely green — aborting instead."
        )
