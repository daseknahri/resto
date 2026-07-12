"""Schema-pinned DB-backed session store (RISK OPS-3 — see docs/RISK_REGISTER.md).

## The hazard this solves

django-tenants scopes almost every model to the current PostgreSQL *schema* by
rewriting the connection's search_path per request (see
``config.middleware.TenantAwareMainMiddleware``). ``django.contrib.sessions`` is
registered in ``SHARED_APPS`` (config/settings.py), so the ``django_session`` table
exists ONLY in the ``public`` schema — there is no per-tenant copy.

That is a non-issue for the *current* engine, ``django.contrib.sessions.backends.cache``
(config/settings.py, "Session store" section): Redis has no notion of schemas, so it
works identically regardless of which tenant is active. But it also means Redis is a
single point of failure for auth — an eviction (256 MB cap) or restart silently deletes
live sessions and logs users out mid-shift, with no durable fallback. That gap is
RISK OPS-3 in the risk register.

The obvious fix — swap to Django's stock ``cached_db`` backend (Redis read/write-through
cache in front of a durable DB row) — is a trap under django-tenants. By the time
``SessionMiddleware`` saves the session (``process_response``, which runs LATE, after the
view and ``TenantAwareMainMiddleware`` have already pointed the connection at the
*tenant* schema), ``django_session`` is no longer on the search_path. Every authenticated
request would either 500 on session save, or — worse — silently read back "no session"
(``_get_session_from_db`` treats a lookup failure as "session absent", not an error),
which looks like every user being logged out on every request rather than a loud failure.

## The fix

Subclass the stock ``cached_db`` backend and re-point every method that actually touches
the database at the ``public`` schema via ``django_tenants.utils.schema_context("public")``,
which saves the connection's current tenant/schema on ``__enter__`` and restores it on
``__exit__`` — so the rest of the request never notices the detour. Cache reads/writes are
untouched (Redis has no schema concept), so the hot path (cache hit) is exactly as fast as
today's cache-only engine; the DB row is purely the durable fallback that survives a Redis
eviction or restart.

## Why these 5 overrides (checked against the installed Django version, not guessed)

Reading ``django/contrib/sessions/backends/db.py`` and ``cached_db.py`` for the Django
version this was written against (see the version constant asserted in
``tests/test_ops3_session_backend.py``) shows database access is concentrated in exactly
5 places. Two of the "obvious candidates" — ``load()`` and ``create()`` — are deliberately
NOT overridden here, because both reach the database only through ``self.<one of the 5
below>(...)``: ordinary Python dynamic dispatch resolves that call against *this* subclass
first, so the schema is already pinned for the duration of the call by the override below.
Re-wrapping ``load``/``create`` too would only nest a second, redundant ``schema_context``.

  * ``_get_session_from_db`` — the only DB read reachable from ``cached_db.load()``'s
    cache-miss path. ``load()`` itself does no other DB access, so leaving it un-overridden
    still leaves it fully covered — and it means a cache HIT never pays for a schema switch.
  * ``exists`` — ``cached_db.exists()`` short-circuits on a cache hit, otherwise calls
    ``super().exists()`` (a real query). Wrapping the whole method keeps the cache-hit path
    cheap while still pinning the DB fallback. ``base.SessionBase._get_new_session_key()``
    (used by ``create()``) only ever reaches the database through ``self.exists(...)``, so
    it is covered for free too.
  * ``save`` — ``cached_db.save()`` calls ``super().save()`` (the DB write) before caching
    the result. ``create()`` (inherited, unmodified) only ever reaches the database through
    ``self.save(must_create=True)``, so it is already covered.
  * ``delete`` — ``cached_db.delete()`` calls ``super().delete()`` (the DB delete) before
    evicting the cache entry. ``flush()`` and ``base.SessionBase.cycle_key()`` (both
    inherited, unmodified) only ever reach the database through ``self.delete(...)``, so
    they are already covered.
  * ``clear_expired`` — a ``@classmethod`` invoked directly by the ``clearsessions``
    management command (``engine.SessionStore.clear_expired()``), with no instance and no
    other overridden method anywhere in its call path. This is the one method of the 5 that
    *needs* its own override rather than inheriting coverage for free.

## Activation — this change does NOT flip the switch

This module is dormant on its own. ``SESSION_ENGINE`` still points at the cache-only
backend (config/settings.py). Activating it is a deliberate, separate step — see the
commented line next to ``SESSION_ENGINE`` in config/settings.py — and should not happen
until an owner has validated, against a real/staging database:

  1. The ``django_session`` table exists in the ``public`` schema (the sessions migration
     has run there — ``django.contrib.sessions`` is in SHARED_APPS so a normal
     ``migrate_schemas``/``migrate`` already does this, but confirm on the target
     environment before flipping the switch).
  2. Set ``SESSION_ENGINE = "accounts.session_backends"``.
  3. Log in on a tenant subdomain, then evict/flush the session's Redis key (or restart
     Redis) mid-session, and confirm the session survives (no forced logout) with no 500s
     on subsequent requests while a tenant schema is active.
  4. Watch error tracking for at least one full deploy cycle before treating this as
     load-bearing.
"""
from django.contrib.sessions.backends.cached_db import SessionStore as CachedDBSessionStore
from django_tenants.utils import schema_context


class SessionStore(CachedDBSessionStore):
    """``cached_db`` session store pinned to the ``public`` schema for all DB access.

    Safe under django-tenants because ``django.contrib.sessions`` lives in SHARED_APPS
    (``django_session`` exists only in the ``public`` schema) — see the module docstring
    for the full hazard this avoids and the rationale for exactly these 5 overrides.
    NOT currently activated; see the module docstring's "Activation" section.
    """

    def _get_session_from_db(self):
        """DB read behind ``load()``'s cache-miss path. See module docstring."""
        with schema_context("public"):
            return super()._get_session_from_db()

    def exists(self, session_key):
        """Cache membership check, falling back to a DB query. See module docstring."""
        with schema_context("public"):
            return super().exists(session_key)

    def save(self, must_create=False):
        """DB upsert plus cache write. Also covers ``create()``, which only reaches
        the database through this method. See module docstring."""
        with schema_context("public"):
            return super().save(must_create)

    def delete(self, session_key=None):
        """DB delete plus cache eviction. Also covers ``flush()`` and ``cycle_key()``,
        which only reach the database through this method. See module docstring."""
        with schema_context("public"):
            return super().delete(session_key)

    @classmethod
    def clear_expired(cls):
        """Bulk-delete expired rows for the ``clearsessions`` management command — the
        one database access with no instance-method path to inherit coverage from."""
        with schema_context("public"):
            return super().clear_expired()
