"""Regression guard for the health endpoint's DB-outage resilience.

Born from the 2026-09-18 production outage: every request 500'd because the
tenant middleware (`TenantAwareMainMiddleware.process_request`) resolves the
tenant with a DB query (`self.get_tenant`) that only catches
``DomainDoesNotExist`` — so a DB *connection* failure propagated as a bare,
opaque 500 *before any view ran*, including `/api/health/`, which is explicitly
built to report ``503 {db: {ok: false}}`` on DB failure.

The fix exempts ``/api/health/`` from the tenant lookup (routes it in the public
schema, where it is registered), so the health view runs and reports the real DB
status instead of the middleware masking it. These tests lock that in and keep
the exemption narrow (health only).
"""

from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from config.middleware import TenantAwareMainMiddleware


class HealthEndpointOutageResilienceTests(SimpleTestCase):
    def setUp(self):
        self.mw = TenantAwareMainMiddleware(get_response=lambda request: None)
        self.rf = RequestFactory()

    def test_health_path_skips_the_tenant_db_lookup(self):
        """/api/health/ must NOT call get_tenant (the DB query), and must route
        public and continue to the view — so it works even when the DB is down."""
        request = self.rf.get("/api/health/")
        with patch.object(TenantAwareMainMiddleware, "get_tenant") as get_tenant, patch.object(
            TenantAwareMainMiddleware, "setup_url_routing"
        ) as setup_routing:
            result = self.mw.process_request(request)

        # The DB-hitting tenant lookup must not run for the health path.
        get_tenant.assert_not_called()
        # Health is routed in the public schema, then the request continues to the view.
        setup_routing.assert_called_once()
        _args, kwargs = setup_routing.call_args
        self.assertIs(kwargs.get("force_public"), True)
        self.assertIsNone(result)

    def test_non_health_path_still_reaches_the_tenant_lookup(self):
        """The exemption is narrow: a normal request still resolves the tenant
        (so this doesn't accidentally skip tenant scoping for other paths)."""
        request = self.rf.get("/api/marketplace/")  # default host "testserver" (allowed in tests)
        sentinel = RuntimeError("get_tenant was reached")
        with patch.object(TenantAwareMainMiddleware, "get_tenant", side_effect=sentinel) as get_tenant:
            with self.assertRaises(RuntimeError):
                self.mw.process_request(request)
        get_tenant.assert_called_once()
