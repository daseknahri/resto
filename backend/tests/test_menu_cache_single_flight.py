"""
R14b FIX3 — single-flight (cache-stampede guard) for the per-tenant public MENU cache,
the hottest public endpoint (every QR scan). Plus a source-level guard for FIX2 (the
"driver arrived" push re-routed through the bounded enqueue pool).

Contract under test:
  - tenancy.cache_utils.get_or_build_single_flight (the generic helper now shared by BOTH
    the public marketplace/directory lists AND the menu cache):
      * HIT  → cached value returned WITHOUT calling build_fn.
      * MISS → build runs once, result cached under the key, lock released.
      * concurrent misses → build runs ~once; everyone gets the same payload.
      * lock held but value never appears → follower builds itself (never blocks forever,
        never returns nothing).
  - PublishAccessMixin.list: a cache hit returns the EXACT cached response.data without
    rebuilding; concurrent misses rebuild once and every caller gets the identical payload.

House style: SimpleTestCase + LocMemCache, no real DB / schema switch.
"""
import threading
import time

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from tenancy.cache_utils import get_or_build_single_flight


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class GenericSingleFlightTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_hit_returns_cached_without_building(self):
        cache.set("menu:k", {"dishes": ["cached"]}, 60)
        calls = []

        def build():
            calls.append(1)
            return {"dishes": ["fresh"]}

        out = get_or_build_single_flight("menu:k", build, ttl=60)
        self.assertEqual(out, {"dishes": ["cached"]})
        self.assertEqual(calls, [], "build fn must NOT run on a cache hit")

    def test_miss_builds_once_caches_and_releases_lock(self):
        calls = []

        def build():
            calls.append(1)
            return {"dishes": ["built"]}

        out = get_or_build_single_flight("menu:k", build, ttl=60)
        self.assertEqual(out, {"dishes": ["built"]})
        self.assertEqual(len(calls), 1, "build runs exactly once on a clean miss")
        self.assertEqual(cache.get("menu:k"), {"dishes": ["built"]})
        self.assertIsNone(cache.get("menu:k:lock"), "lock released in finally")

    def test_follower_serves_holder_value_without_building(self):
        cache.add("menu:k:lock", "1", timeout=10)
        cache.set("menu:k", {"dishes": ["holder"]}, 60)
        calls = []

        def build():
            calls.append(1)
            return {"dishes": ["should-not-build"]}

        out = get_or_build_single_flight("menu:k", build, ttl=60)
        self.assertEqual(out, {"dishes": ["holder"]})
        self.assertEqual(calls, [], "follower serves the holder's value, not rebuild")

    def test_follower_builds_when_holder_too_slow(self):
        cache.add("menu:k:lock", "1", timeout=10)  # held, but key stays empty
        calls = []

        def build():
            calls.append(1)
            return {"dishes": ["fallback"]}

        out = get_or_build_single_flight(
            "menu:k", build, ttl=60, wait_total=0.15, wait_step=0.02
        )
        self.assertEqual(out, {"dishes": ["fallback"]})
        self.assertEqual(len(calls), 1, "follower builds when holder is too slow")
        self.assertEqual(cache.get("menu:k"), {"dishes": ["fallback"]})

    def test_per_key_lock_does_not_serialize_distinct_keys(self):
        cache.add("menu:A:lock", "1", timeout=10)  # key A locked + never populated
        calls = []

        def build_b():
            calls.append("b")
            return {"dishes": ["B"]}

        out = get_or_build_single_flight("menu:B", build_b, ttl=60)
        self.assertEqual(out, {"dishes": ["B"]})
        self.assertEqual(calls, ["b"])

    def test_concurrent_misses_build_once(self):
        build_count = []
        build_lock = threading.Lock()
        start = threading.Barrier(8)

        def build():
            with build_lock:
                build_count.append(1)
            time.sleep(0.1)  # hold so followers are still polling while we "build"
            return {"dishes": ["once"]}

        results = []
        results_lock = threading.Lock()

        def worker():
            start.wait()
            out = get_or_build_single_flight("menu:hot", build, ttl=60)
            with results_lock:
                results.append(out)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(build_count), 1,
                         f"expected a single rebuild under concurrency, got {sum(build_count)}")
        self.assertEqual(len(results), 8)
        for r in results:
            self.assertEqual(r, {"dishes": ["once"]})

    def test_returns_payload_verbatim(self):
        payload = {"dishes": [{"id": 1, "name": "Tagine"}], "count": 1}

        def build():
            return payload

        out = get_or_build_single_flight("menu:k", build, ttl=60)
        self.assertIs(out, payload)


# ── PublishAccessMixin.list integration (no DB: super().list is stubbed) ──────────

class _FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class MenuListSingleFlightTests(SimpleTestCase):
    """Drive PublishAccessMixin.list through the single-flight path with super().list and
    the request/policy plumbing stubbed — verifies the cached response.data is returned
    verbatim and that concurrent misses rebuild once."""

    def setUp(self):
        cache.clear()

    def _make_view(self, build_data, *, build_counter=None, status_code=200, key="menu:demo:v1"):
        from menu.views import PublishAccessMixin

        # A minimal concrete view: the mixin's list() is exercised, but every collaborator
        # it touches (policy gate, cache-key derivation, the DRF super().list build) is
        # stubbed so the test stays non-DB. _Parent stands in for viewsets.ModelViewSet so
        # super(PublishAccessMixin, self).list inside the override resolves to it.
        class _Parent:
            def list(self_inner, request, *args, **kwargs):
                if build_counter is not None:
                    build_counter.append(1)
                return _FakeResponse(build_data, status_code)

        class _Concrete(PublishAccessMixin, _Parent):
            def _enforce_public_menu_policy(self):
                return None

            def _menu_list_cache_key(self):
                return key

        return _Concrete()

    def test_cache_hit_returns_exact_payload_without_rebuild(self):
        key = "menu:demo:cat:1:abcd"
        cache.set(key, {"results": ["CACHED"]}, 60)
        counter = []
        view = self._make_view({"results": ["FRESH"]}, build_counter=counter, key=key)
        resp = view.list(request=None)
        self.assertEqual(resp.data, {"results": ["CACHED"]})
        self.assertEqual(counter, [], "a cache hit must NOT rebuild")

    def test_miss_builds_once_and_returns_built_payload(self):
        key = "menu:demo:cat:1:wxyz"
        counter = []
        view = self._make_view({"results": ["BUILT"]}, build_counter=counter, key=key)
        resp = view.list(request=None)
        self.assertEqual(resp.data, {"results": ["BUILT"]})
        self.assertEqual(len(counter), 1, "clean miss builds exactly once")
        self.assertEqual(cache.get(key), {"results": ["BUILT"]}, "payload cached verbatim")

    def test_concurrent_menu_misses_rebuild_once(self):
        key = "menu:demo:hot:1:zzzz"
        counter = []
        counter_lock = threading.Lock()
        start = threading.Barrier(8)

        from menu.views import PublishAccessMixin

        class _Parent:
            def list(self_inner, request, *args, **kwargs):
                with counter_lock:
                    counter.append(1)
                time.sleep(0.1)
                return _FakeResponse({"results": ["ONCE"]}, 200)

        class _Concrete(PublishAccessMixin, _Parent):
            def _enforce_public_menu_policy(self):
                return None

            def _menu_list_cache_key(self):
                return key

        results = []
        results_lock = threading.Lock()

        def worker():
            start.wait()
            resp = _Concrete().list(request=None)
            with results_lock:
                results.append(resp.data)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(counter), 1,
                         f"menu rebuild must happen once under concurrency, got {sum(counter)}")
        self.assertEqual(len(results), 8)
        for r in results:
            self.assertEqual(r, {"results": ["ONCE"]})

    def test_non_200_is_not_cached(self):
        key = "menu:demo:err:1:eeee"
        counter = []
        view = self._make_view({"detail": "boom"}, build_counter=counter,
                               status_code=503, key=key)
        resp = view.list(request=None)
        self.assertEqual(resp.data, {"detail": "boom"})
        # The original "only cache 200s" guard is preserved: a non-200 build is evicted.
        self.assertIsNone(cache.get(key), "non-200 responses must not stay cached")


class DriverArrivedDispatchSourceTests(SimpleTestCase):
    """R14b FIX2: the AT_RESTAURANT 'driver arrived' branch dispatches through the bounded
    enqueue pool (accounts.tasks.enqueue + web_push_tenant), not a raw threading.Thread.

    The branch is inline in a DB-heavy view method, so we assert it at the source level —
    a regression guard that the re-route stays in place without needing Postgres."""

    def test_at_restaurant_branch_uses_enqueue_not_raw_thread(self):
        import inspect
        from accounts import views as accounts_views
        src = inspect.getsource(accounts_views)
        # The driver-arrived side-effect is the LAST AT_RESTAURANT usage (the elif after
        # the lock). Take a window after it and assert the dispatch mechanism.
        last = src.rfind("DeliveryJob.Status.AT_RESTAURANT")
        window = src[last:last + 1200]
        self.assertIn("Driver arrived", window, "found the driver-arrived branch")
        self.assertIn("enqueue(", window, "driver-arrived push goes through enqueue()")
        self.assertIn("web_push_tenant", window, "uses the existing web_push_tenant task")
        self.assertNotIn("threading.Thread", window,
                         "driver-arrived push must NOT spawn a raw thread anymore")
        self.assertNotIn("_threading.Thread", window,
                         "driver-arrived push must NOT spawn a raw thread anymore")
