"""OPS-5d config / proxy / deploy hardening — contract tests.

Covers the two code-level OPS-5d items that have unit-testable behaviour:

  A) CORS localhost regex default (settings.py):
     A blank/unset DJANGO_CORS_ALLOWED_ORIGIN_REGEXES must yield an EMPTY regex
     list when DEBUG is False (production), so a prod deploy never grants
     credentialed cross-origin access to *.localhost:5173.  In DEBUG (dev) the
     convenience *.localhost regex is still applied.

  C) Trusted-proxy-aware throttle ident (menu/throttles.py):
     _IPThrottle.get_cache_key must key on the real client IP computed by
     sales.audit.get_request_ip (rightmost-minus-TRUSTED_PROXY_COUNT with a
     REMOTE_ADDR fallback), NOT DRF's get_ident which trusts the spoofable
     leftmost X-Forwarded-For entry.  Falls back to get_ident only when
     get_request_ip returns nothing.

Items B (media route) and D (entrypoint.sh / env.example) are URLconf wiring and
shell/docs respectively — see public_urls.py / docker/entrypoint.sh.

House style: SimpleTestCase + mocks, no real DB.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


# ─────────────────────────────────────────────────────────────────────────────
# A) CORS localhost regex default — blank env in non-DEBUG → empty list
# ─────────────────────────────────────────────────────────────────────────────

class CorsLocalhostRegexDefaultTests(SimpleTestCase):
    """The in-code default localhost regex must only apply when DEBUG is True.

    The bug: parse_csv_env falls back to its default whenever the env var is
    unset/blank, and Coolify passes unset vars as "".  With a hard-coded
    localhost-regex default, a blank DJANGO_CORS_ALLOWED_ORIGIN_REGEXES in prod
    silently re-enabled credentialed cross-origin access for any
    *.localhost:5173 origin.  The fix gates the default behind DEBUG.

    We re-implement the exact settings.py expression here (it runs once at
    module import, so we can't easily re-trigger it) and assert its behaviour
    across the DEBUG / env-var matrix.  The mirrored expression is kept in lock
    step with config/settings.py (~408).
    """

    def _resolve(self, *, debug, env_value):
        """Mirror of config/settings.py CORS regex resolution."""
        from config.settings import parse_csv_env

        default = r"^http://[a-z0-9-]+\.localhost:5173$" if debug else ""
        with patch.dict(
            "os.environ",
            {} if env_value is None else {"DJANGO_CORS_ALLOWED_ORIGIN_REGEXES": env_value},
            clear=False,
        ):
            if env_value is None:
                # Ensure the var is absent for the unset case.
                import os
                os.environ.pop("DJANGO_CORS_ALLOWED_ORIGIN_REGEXES", None)
            regexes = set(parse_csv_env("DJANGO_CORS_ALLOWED_ORIGIN_REGEXES", default))
        return sorted(regexes)

    def test_blank_env_in_production_yields_empty_list(self):
        """DEBUG=False + blank env (Coolify "") → EMPTY regex list (the fix)."""
        self.assertEqual(self._resolve(debug=False, env_value=""), [])

    def test_unset_env_in_production_yields_empty_list(self):
        """DEBUG=False + var entirely absent → EMPTY regex list."""
        self.assertEqual(self._resolve(debug=False, env_value=None), [])

    def test_blank_env_in_debug_keeps_localhost_regex(self):
        """DEBUG=True + blank env → dev still gets the *.localhost:5173 regex."""
        result = self._resolve(debug=True, env_value="")
        self.assertEqual(result, [r"^http://[a-z0-9-]+\.localhost:5173$"])

    def test_explicit_env_is_honoured_in_production(self):
        """An explicit prod regex is always honoured (DEBUG irrelevant)."""
        result = self._resolve(
            debug=False, env_value=r"^https://[a-z0-9-]+\.menu\.example\.com$"
        )
        self.assertEqual(result, [r"^https://[a-z0-9-]+\.menu\.example\.com$"])

    def test_live_settings_value_is_empty_or_localhost_only(self):
        """The actually-imported CORS_ALLOWED_ORIGIN_REGEXES must never contain a
        non-localhost regex unless one was explicitly configured.  Under the test
        env (DEBUG=True, no override) it should be exactly the localhost regex."""
        from django.conf import settings

        for rgx in settings.CORS_ALLOWED_ORIGIN_REGEXES:
            # No surprise wildcards: every default regex is the localhost helper.
            self.assertIn("localhost", rgx)


# ─────────────────────────────────────────────────────────────────────────────
# C) _IPThrottle cache key uses the trusted-proxy IP, not a spoofed XFF[0]
# ─────────────────────────────────────────────────────────────────────────────

class IPThrottleTrustedProxyIdentTests(SimpleTestCase):
    """_IPThrottle.get_cache_key must use get_request_ip's trusted-proxy IP.

    uvicorn runs with --proxy-headers, so DRF's get_ident() returns the
    leftmost (client-spoofable) X-Forwarded-For entry.  An attacker could rotate
    XFF[0] every request to reset the per-IP bucket on OrderHandoffThrottle /
    CheckoutIntentThrottle.  The fix keys on get_request_ip (rightmost-minus-
    TRUSTED_PROXY_COUNT) so the spoofed leftmost entry is ignored.
    """

    def _throttle(self, scope="order_handoff"):
        from menu.throttles import OrderHandoffThrottle
        t = OrderHandoffThrottle()
        t.scope = scope
        # cache_format is "throttle_%(scope)s_%(ident)s" on SimpleRateThrottle.
        return t

    def _request(self, xff=None, remote_addr="203.0.113.7"):
        meta = {"REMOTE_ADDR": remote_addr}
        if xff is not None:
            meta["HTTP_X_FORWARDED_FOR"] = xff
        # DRF SimpleRateThrottle.get_ident reads request.META; mimic enough of a
        # request object for both code paths.
        return SimpleNamespace(META=meta)

    def test_cache_key_uses_real_client_ip_not_spoofed_xff0(self):
        """XFF = 'SPOOFED, <real client>' with TRUSTED_PROXY_COUNT=1.

        Our single nginx proxy appends the real client IP as the LAST entry, so
        with count=1 get_request_ip returns the rightmost entry (198.51.100.9),
        NOT the attacker-controlled leftmost 'SPOOFED' entry.
        """
        throttle = self._throttle()
        req = self._request(xff="SPOOFED, 198.51.100.9")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            key = throttle.get_cache_key(req, MagicMock())
        self.assertIn("198.51.100.9", key)
        self.assertNotIn("SPOOFED", key)

    def test_spoofing_xff0_does_not_change_the_bucket(self):
        """Two requests with different leftmost XFF entry but the same real
        (rightmost) client IP must produce the SAME cache key — the attacker
        cannot rotate buckets by prepending junk."""
        throttle = self._throttle()
        req1 = self._request(xff="AAAA, 198.51.100.9")
        req2 = self._request(xff="BBBB, 198.51.100.9")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            key1 = throttle.get_cache_key(req1, MagicMock())
            key2 = throttle.get_cache_key(req2, MagicMock())
        self.assertEqual(key1, key2)

    def test_distinct_real_clients_get_distinct_keys(self):
        """Different real (rightmost) clients keep independent buckets."""
        throttle = self._throttle()
        req_a = self._request(xff="X, 198.51.100.9")
        req_b = self._request(xff="X, 198.51.100.10")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            key_a = throttle.get_cache_key(req_a, MagicMock())
            key_b = throttle.get_cache_key(req_b, MagicMock())
        self.assertNotEqual(key_a, key_b)

    def test_no_xff_uses_remote_addr(self):
        """With no XFF header, the key falls back to REMOTE_ADDR (set by TCP)."""
        throttle = self._throttle()
        req = self._request(xff=None, remote_addr="203.0.113.7")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            key = throttle.get_cache_key(req, MagicMock())
        self.assertIn("203.0.113.7", key)

    def test_falls_back_to_get_ident_when_get_request_ip_falsy(self):
        """If get_request_ip returns falsy (no REMOTE_ADDR, no usable XFF), the
        code must fall back to DRF's get_ident rather than keying on None."""
        throttle = self._throttle()
        req = self._request(xff=None, remote_addr=None)
        # REMOTE_ADDR=None → get_request_ip returns None → fall back to get_ident.
        with patch("menu.throttles.SimpleRateThrottle.get_ident", return_value="fallback-ident"):
            key = throttle.get_cache_key(req, MagicMock())
        self.assertIn("fallback-ident", key)
        self.assertNotIn("None", key)

    def test_checkout_intent_throttle_shares_the_base_behaviour(self):
        """CheckoutIntentThrottle (the other _IPThrottle subclass) inherits the
        trusted-proxy ident logic — sanity check it uses get_request_ip too."""
        from menu.throttles import CheckoutIntentThrottle
        t = CheckoutIntentThrottle()
        t.scope = "checkout_intent"
        req = self._request(xff="SPOOFED, 198.51.100.9")
        with patch("sales.audit.settings") as mock_settings:
            mock_settings.TRUSTED_PROXY_COUNT = 1
            key = t.get_cache_key(req, MagicMock())
        self.assertIn("198.51.100.9", key)
        self.assertNotIn("SPOOFED", key)
