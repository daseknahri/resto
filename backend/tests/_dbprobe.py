"""Postgres-availability probe for DB-backed tests (RISK TEST-1).

Why not `django.db.connection.ensure_connection()`: pytest-django installs its
database-access blocker at configure time, so under pytest that call raises
"Database access not allowed ..." during collection EVEN WHEN POSTGRES IS UP.
An import-time guard built on it is therefore always False under pytest — which
is exactly how the MFA DB tests silently skipped in CI (the 24-skipped baseline)
while looking like a local-only convenience. This probe connects with the raw
driver instead, so it answers the real question: is the configured Postgres
server reachable with our credentials?

Not named test_*.py, so pytest never collects it; import it as `import _dbprobe`
(the tests directory is on sys.path because tests/conftest.py exists).
"""
import os


def db_required() -> bool:
    """True when the run must have a DB (CI sets PYTEST_REQUIRE_DB=1)."""
    return os.environ.get("PYTEST_REQUIRE_DB", "").strip().lower() in {"1", "true", "yes"}


def db_available() -> bool:
    """True when the configured default Postgres accepts a real connection.

    Fail-closed: with PYTEST_REQUIRE_DB set, an unreachable DB raises instead of
    returning False, so skip-guards built on this fail loudly rather than skip.
    """
    try:
        import psycopg2
        from django.conf import settings

        cfg = settings.DATABASES["default"]
        conn = psycopg2.connect(
            dbname=cfg.get("NAME") or "postgres",
            user=cfg.get("USER") or "",
            password=cfg.get("PASSWORD") or "",
            host=cfg.get("HOST") or "localhost",
            port=int(cfg.get("PORT") or 5432),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        if db_required():
            raise
        return False
