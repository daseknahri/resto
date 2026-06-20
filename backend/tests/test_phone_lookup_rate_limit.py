"""
Unit tests for CustomerOrdersByPhoneView._is_rate_limited in menu/views.py.

The method:
  1. Extracts client IP from X-Forwarded-For or REMOTE_ADDR
  2. Checks a per-IP counter in Django's cache
  3. Returns True if hits >= _RATE_LIMIT (10), False otherwise
  4. Increments the counter on each non-blocked call

All tests are unit-level (SimpleTestCase — cache is mocked via patch).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.views import CustomerOrdersByPhoneView


# ── helpers ───────────────────────────────────────────────────────────────────

def _view():
    return CustomerOrdersByPhoneView()


def _request(ip=None, forwarded_for=None):
    meta = {}
    if forwarded_for:
        meta["HTTP_X_FORWARDED_FOR"] = forwarded_for
    if ip:
        meta["REMOTE_ADDR"] = ip
    return SimpleNamespace(META=meta)


def _patched_cache(get_return=0):
    """Return (cache_mock, patch_context_manager)."""
    from unittest.mock import MagicMock
    cache_mock = MagicMock()
    cache_mock.get.return_value = get_return
    return cache_mock


# ══════════════════════════════════════════════════════════════════════════════
# IP extraction
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitIpExtractionTests(SimpleTestCase):
    """The rate-limit key is built from the extracted client IP."""

    def test_uses_first_forwarded_ip(self):
        req = _request(forwarded_for="203.0.113.1, 10.0.0.1")
        cache_mock = _patched_cache(get_return=0)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        # The cache key should use the first forwarded IP
        get_call_key = cache_mock.get.call_args[0][0]
        self.assertIn("203.0.113.1", get_call_key)

    def test_falls_back_to_remote_addr(self):
        req = _request(ip="192.168.0.1")
        cache_mock = _patched_cache(get_return=0)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        get_call_key = cache_mock.get.call_args[0][0]
        self.assertIn("192.168.0.1", get_call_key)

    def test_uses_unknown_when_no_ip(self):
        req = _request()  # neither forwarded-for nor remote-addr
        cache_mock = _patched_cache(get_return=0)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        get_call_key = cache_mock.get.call_args[0][0]
        self.assertIn("unknown", get_call_key)

    def test_strips_whitespace_from_forwarded_ip(self):
        req = _request(forwarded_for="  10.1.2.3  , 10.0.0.1")
        cache_mock = _patched_cache(get_return=0)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        get_call_key = cache_mock.get.call_args[0][0]
        self.assertIn("10.1.2.3", get_call_key)


# ══════════════════════════════════════════════════════════════════════════════
# Rate-limit decision
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitDecisionTests(SimpleTestCase):
    """Returns True when at/over the limit, False otherwise."""

    def test_below_limit_returns_false(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=0)   # 0 hits so far
        with patch("menu.views.cache", cache_mock):
            result = _view()._is_rate_limited(req)
        self.assertFalse(result)

    def test_at_limit_returns_true(self):
        req = _request(ip="10.0.0.1")
        # _RATE_LIMIT is 10; 10 hits means rate-limited
        cache_mock = _patched_cache(get_return=10)
        with patch("menu.views.cache", cache_mock):
            result = _view()._is_rate_limited(req)
        self.assertTrue(result)

    def test_over_limit_returns_true(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=99)
        with patch("menu.views.cache", cache_mock):
            result = _view()._is_rate_limited(req)
        self.assertTrue(result)

    def test_one_below_limit_returns_false(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=9)  # 9 < 10
        with patch("menu.views.cache", cache_mock):
            result = _view()._is_rate_limited(req)
        self.assertFalse(result)


# ══════════════════════════════════════════════════════════════════════════════
# Counter increment
# ══════════════════════════════════════════════════════════════════════════════

class RateLimitCounterTests(SimpleTestCase):
    """When not rate-limited, the cache counter is incremented."""

    def test_counter_incremented_when_not_rate_limited(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=3)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        cache_mock.set.assert_called_once()
        set_args = cache_mock.set.call_args[0]
        self.assertEqual(set_args[1], 4)   # hits + 1 = 4

    def test_counter_not_incremented_when_rate_limited(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=10)   # at limit
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        cache_mock.set.assert_not_called()

    def test_cache_window_passed_to_set(self):
        req = _request(ip="10.0.0.1")
        cache_mock = _patched_cache(get_return=0)
        with patch("menu.views.cache", cache_mock):
            _view()._is_rate_limited(req)
        set_args = cache_mock.set.call_args[0]
        # Third positional arg is the timeout (_RATE_WINDOW = 60)
        self.assertEqual(set_args[2], 60)
