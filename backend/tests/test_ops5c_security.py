"""OPS-5c Security Follow-up — Contract Tests

Covers the OPS-5c items that had zero test coverage:

  SSRF guard (items 3 / routing.py):
    1. Metadata IP (169.254.169.254) is rejected.
    2. Docker/private RFC-1918 host is accepted.
    3. Bad scheme (file://) is rejected.
    4. Unparseable URL falls back to estimate (returns None / no crash).

  prune_auth_tokens command (item 4):
    5. Dry-run shows counts without deleting.
    6. Delete mode removes consumed/expired tokens.
    7. --days < 1 raises CommandError.

  Proxy-miscount REMOTE_ADDR fallback (items 5 / audit.py):
    8. TRUSTED_PROXY_COUNT > XFF list length falls back to REMOTE_ADDR,
       not XFF[0] (the client-spoofable leftmost entry).

  AnalyticsEventThrottle (tenant, ip) keying (item 7 / menu/throttles.py):
    9. Cache key contains both schema name and IP.
    10. Falls back to IP-only when no tenant schema is set.

  SSRF redirect guard (routing.py):
    11. Both requests.get calls pass allow_redirects=False so a 301/302
        from a compromised OSRM server cannot redirect to the metadata IP.

House style: SimpleTestCase + mocks, no real DB.
"""
from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from tenancy.routing import _is_ssrf_blocked, _validate_osrm_url


# ─────────────────────────────────────────────────────────────────────────────
# SSRF guard — _is_ssrf_blocked / _validate_osrm_url
# ─────────────────────────────────────────────────────────────────────────────

class SSRFBlockedTests(SimpleTestCase):
    """_is_ssrf_blocked covers literal-IP checks only (no DNS resolution)."""

    def test_metadata_ip_is_blocked(self):
        """169.254.169.254 (AWS/GCP/Azure/DO) must be rejected."""
        self.assertTrue(_is_ssrf_blocked("169.254.169.254"))

    def test_ipv6_metadata_alias_is_blocked(self):
        """::ffff:169.254.169.254 IPv4-mapped form must also be rejected."""
        self.assertTrue(_is_ssrf_blocked("::ffff:169.254.169.254"))

    def test_loopback_is_blocked(self):
        """127.0.0.1 (loopback) must be rejected."""
        self.assertTrue(_is_ssrf_blocked("127.0.0.1"))

    def test_ipv6_loopback_is_blocked(self):
        """::1 (IPv6 loopback) must be rejected."""
        self.assertTrue(_is_ssrf_blocked("::1"))

    def test_rfc1918_10_block_is_allowed(self):
        """10.x.x.x docker-internal OSRM is the primary deployment target."""
        self.assertFalse(_is_ssrf_blocked("10.0.0.5"))

    def test_rfc1918_172_block_is_allowed(self):
        self.assertFalse(_is_ssrf_blocked("172.20.0.2"))

    def test_rfc1918_192_168_is_allowed(self):
        self.assertFalse(_is_ssrf_blocked("192.168.1.100"))

    def test_hostname_is_allowed(self):
        """A non-literal hostname (e.g. 'osrm') is passed through without DNS."""
        self.assertFalse(_is_ssrf_blocked("osrm"))


class ValidateOsrmUrlTests(SimpleTestCase):
    """_validate_osrm_url enforces scheme + non-blocked host."""

    def test_http_docker_host_accepted(self):
        """http://osrm:5000 — the canonical docker-internal URL — must pass."""
        result = _validate_osrm_url("http://osrm:5000")
        self.assertEqual(result, "http://osrm:5000")

    def test_http_private_ip_accepted(self):
        """RFC-1918 IP is explicitly allowed (self-hosted VPS scenario)."""
        result = _validate_osrm_url("http://10.0.0.5:5000")
        self.assertEqual(result, "http://10.0.0.5:5000")

    def test_metadata_ip_rejected(self):
        """URL pointing at the cloud-metadata endpoint must return empty string."""
        result = _validate_osrm_url("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(result, "")

    def test_file_scheme_rejected(self):
        """Non-http/https scheme (file://) must be blocked by the SSRF guard."""
        result = _validate_osrm_url("file:///etc/passwd")
        self.assertEqual(result, "")

    def test_gopher_scheme_rejected(self):
        result = _validate_osrm_url("gopher://osrm:5000")
        self.assertEqual(result, "")

    def test_blank_url_returns_empty(self):
        """An empty DELIVERY_OSRM_URL should produce '' (no OSRM configured)."""
        result = _validate_osrm_url("")
        self.assertEqual(result, "")

    def test_garbage_url_falls_back_to_estimate(self):
        """An invalid URL must not crash — returns '' so caller uses factor fallback."""
        result = _validate_osrm_url("not-a-url-at-all\x00")
        self.assertEqual(result, "")


# ─────────────────────────────────────────────────────────────────────────────
# SSRF redirect guard — allow_redirects=False in both requests.get calls
# ─────────────────────────────────────────────────────────────────────────────

class SSRFRedirectGuardTests(SimpleTestCase):
    """Both OSRM requests.get calls must pass allow_redirects=False.

    Without this, a compromised OSRM server can return a 301/302 redirect to
    169.254.169.254 and bypass all the literal-IP checks in _is_ssrf_blocked.
    A legitimate OSRM /route/v1/ endpoint never needs to redirect.
    """

    def _ok_response(self, meters=5000.0):
        resp = Mock()
        resp.ok = True
        resp.json.return_value = {"code": "Ok", "routes": [{"distance": meters}]}
        return resp

    def _ok_route_response(self):
        resp = Mock()
        resp.ok = True
        resp.json.return_value = {
            "code": "Ok",
            "routes": [{
                "distance": 5000.0,
                "duration": 600.0,
                "geometry": {"coordinates": [[-7.5898, 33.5731], [-6.8416, 34.0209]]},
            }],
        }
        return resp

    def test_osrm_distance_km_passes_allow_redirects_false(self):
        """_osrm_distance_km must call requests.get with allow_redirects=False."""
        from tenancy.routing import _osrm_distance_km
        from django.core.cache import cache
        cache.clear()
        with patch("requests.get", return_value=self._ok_response()) as mock_get:
            _osrm_distance_km("http://osrm:5000", 33.57, -7.58, 34.02, -6.84)
        _, call_kwargs = mock_get.call_args
        self.assertFalse(
            call_kwargs.get("allow_redirects", True),
            "allow_redirects must be False to prevent redirect-to-metadata attacks",
        )

    def test_osrm_route_passes_allow_redirects_false(self):
        """_osrm_route must also call requests.get with allow_redirects=False."""
        from tenancy.routing import _osrm_route
        from django.core.cache import cache
        cache.clear()
        with patch("requests.get", return_value=self._ok_route_response()) as mock_get:
            _osrm_route("http://osrm:5000", 33.57, -7.58, 34.02, -6.84)
        _, call_kwargs = mock_get.call_args
        self.assertFalse(
            call_kwargs.get("allow_redirects", True),
            "allow_redirects must be False to prevent redirect-to-metadata attacks",
        )


# ─────────────────────────────────────────────────────────────────────────────
# prune_auth_tokens command (OPS-5c item 4)
# ─────────────────────────────────────────────────────────────────────────────

def _make_union_qs(count=0):
    """Build a mock queryset whose | operator returns itself (so union is a no-op).

    The prune_auth_tokens command builds:
        qs = Model.objects.filter(...).filter(...) | Model.objects.filter(...)
    Both filter() chains and the union result must support .count() and .delete().
    Using a single qs object returned from every filter() call and returned from
    __or__ keeps the mock simple.
    """
    qs = MagicMock()
    qs.count.return_value = count
    qs.filter.return_value = qs   # chained .filter(...).filter(...) stays on qs
    qs.__or__ = MagicMock(return_value=qs)  # qs | qs → qs
    return qs


class PruneAuthTokensCommandTests(SimpleTestCase):
    """accounts/management/commands/prune_auth_tokens.py

    The command imports models lazily inside handle():
        from accounts.models import PasswordResetToken
        from sales.models import ActivationToken
    We patch the model classes at their canonical module locations so the lazy
    import picks up the mock, then call Command().handle() directly.
    """

    def _cmd(self):
        from accounts.management.commands.prune_auth_tokens import Command
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda x: x
        return cmd

    def test_rejects_zero_days(self):
        """--days must be >= 1; 0 raises CommandError."""
        with self.assertRaises(CommandError):
            self._cmd().handle(days=0, dry_run=False)

    @patch("accounts.models.PasswordResetToken")
    @patch("sales.models.ActivationToken")
    def test_dry_run_does_not_delete(self, mock_at, mock_prt):
        """Dry-run must call .count() but NOT .delete() on either queryset."""
        prt_qs = _make_union_qs(count=3)
        mock_prt.objects.filter.return_value = prt_qs

        at_qs = _make_union_qs(count=7)
        mock_at.objects.filter.return_value = at_qs

        self._cmd().handle(days=30, dry_run=True)

        prt_qs.delete.assert_not_called()
        at_qs.delete.assert_not_called()

    @patch("accounts.models.PasswordResetToken")
    @patch("sales.models.ActivationToken")
    def test_delete_mode_deletes_both_tables(self, mock_at, mock_prt):
        """Without dry_run, non-zero counts trigger .delete() on both tables."""
        prt_qs = _make_union_qs(count=2)
        mock_prt.objects.filter.return_value = prt_qs

        at_qs = _make_union_qs(count=5)
        mock_at.objects.filter.return_value = at_qs

        self._cmd().handle(days=30, dry_run=False)

        prt_qs.delete.assert_called_once()
        at_qs.delete.assert_called_once()

    @patch("accounts.models.PasswordResetToken")
    @patch("sales.models.ActivationToken")
    def test_zero_count_skips_delete(self, mock_at, mock_prt):
        """When count is 0, .delete() must not be called (no-op for empty tables)."""
        prt_qs = _make_union_qs(count=0)
        mock_prt.objects.filter.return_value = prt_qs

        at_qs = _make_union_qs(count=0)
        mock_at.objects.filter.return_value = at_qs

        self._cmd().handle(days=30, dry_run=False)

        prt_qs.delete.assert_not_called()
        at_qs.delete.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Proxy-miscount REMOTE_ADDR fallback (OPS-5c item 5)
# ─────────────────────────────────────────────────────────────────────────────

class ProxyMiscountFallbackTests(SimpleTestCase):
    """get_request_ip must fall back to REMOTE_ADDR (not XFF[0]) when
    TRUSTED_PROXY_COUNT exceeds the number of XFF entries.

    The old XFF[0] fallback was deleted in OPS-5c; this test proves the new
    REMOTE_ADDR path is exercised.  A client can forge XFF[0] but cannot forge
    REMOTE_ADDR (which is set by the TCP layer).
    """

    def setUp(self):
        from sales.audit import get_request_ip
        self.get_ip = get_request_ip

    def _req(self, xff=None, remote_addr="10.0.0.1"):
        meta = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        return SimpleNamespace(META=meta)

    def test_miscount_falls_back_to_remote_addr_not_xff0(self):
        """TRUSTED_PROXY_COUNT=3 with only 2 XFF entries: idx = 2-3 = -1 < 0
        → must return REMOTE_ADDR, not XFF[0] ('SPOOFED')."""
        req = self._req(xff="SPOOFED, 10.0.0.2", remote_addr="10.0.0.1")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 3
            ip = self.get_ip(req)
        # Must NOT return the spoofable leftmost entry
        self.assertNotEqual(ip, "SPOOFED")
        # Must return REMOTE_ADDR instead
        self.assertEqual(ip, "10.0.0.1")

    def test_exact_count_matches_xff_length_returns_first_entry(self):
        """TRUSTED_PROXY_COUNT == len(XFF): idx = 0 → return the first (real client) entry."""
        req = self._req(xff="1.2.3.4, 10.0.0.2", remote_addr="10.0.0.99")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 2
            ip = self.get_ip(req)
        self.assertEqual(ip, "1.2.3.4")

    def test_count_exceeds_xff_returns_remote_addr(self):
        """Count of 5 with only 1 XFF entry: idx = 1-5 = -4 → REMOTE_ADDR."""
        req = self._req(xff="ATTACKER_INJECTED", remote_addr="172.16.0.1")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 5
            ip = self.get_ip(req)
        self.assertNotEqual(ip, "ATTACKER_INJECTED")
        self.assertEqual(ip, "172.16.0.1")


# ─────────────────────────────────────────────────────────────────────────────
# AnalyticsEventThrottle (tenant, ip) keying (OPS-5c item 7)
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsEventThrottleTests(SimpleTestCase):
    """AnalyticsEventThrottle must key on (schema, ip), not just ip.

    A pure IP key collapses all tenants behind a shared-office NAT or CDN into
    one 600/hour bucket so a busy restaurant can 429 another restaurant's analytics.
    Keying on (schema, ip) gives each tenant an independent bucket.
    """

    def _throttle(self):
        from menu.throttles import AnalyticsEventThrottle
        t = AnalyticsEventThrottle()
        t.scope = "analytics_events_tenant"
        t.rate = "600/hour"
        t.num_requests, t.duration = 600, 3600
        return t

    def _request(self, remote_addr="1.2.3.4"):
        req = MagicMock()
        req.META = {"REMOTE_ADDR": remote_addr, "HTTP_X_FORWARDED_FOR": ""}
        return req

    def test_cache_key_contains_schema_and_ip(self):
        """Key must embed the tenant schema_name so each tenant gets its own bucket."""
        throttle = self._throttle()
        req = self._request(remote_addr="1.2.3.4")
        view = MagicMock()
        tenant = SimpleNamespace(schema_name="bistro_demo")
        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = tenant
            key = throttle.get_cache_key(req, view)
        self.assertIn("bistro_demo", key)
        self.assertIn("1.2.3.4", key)

    def test_different_tenants_same_ip_get_different_keys(self):
        """Two restaurants behind the same NAT must have independent keys."""
        throttle = self._throttle()
        req = self._request(remote_addr="1.2.3.4")
        view = MagicMock()

        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = SimpleNamespace(schema_name="restaurant_a")
            key_a = throttle.get_cache_key(req, view)

        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = SimpleNamespace(schema_name="restaurant_b")
            key_b = throttle.get_cache_key(req, view)

        self.assertNotEqual(key_a, key_b)

    def test_fallback_to_ip_when_no_schema(self):
        """Without a tenant on the connection, key must still work (IP-only fallback)."""
        throttle = self._throttle()
        req = self._request(remote_addr="9.8.7.6")
        view = MagicMock()
        with patch("menu.throttles.connection") as mock_conn:
            mock_conn.tenant = None
            key = throttle.get_cache_key(req, view)
        # Must not crash; should still produce a usable cache key
        self.assertIsNotNone(key)
        self.assertIn("9.8.7.6", key)

    def test_scope_is_analytics_events_tenant(self):
        """Scope must match the DEFAULT_THROTTLE_RATES key in config/rest_framework.py."""
        from menu.throttles import AnalyticsEventThrottle
        self.assertEqual(AnalyticsEventThrottle.scope, "analytics_events_tenant")
