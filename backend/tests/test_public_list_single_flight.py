"""
R14 — single-flight (cache-stampede guard) for the public list endpoints.

Contract under test (accounts.views._public_list_get_or_build):
  - HIT: the cached payload is returned WITHOUT calling the expensive build fn.
  - MISS, lock acquired: build runs ONCE, the result is cache.set under the key, and the
    lock is released.
  - Concurrent misses: under simulated concurrency the expensive build runs ~once (the
    lock-holder); the other requests serve the value the holder populated.
  - A request that cannot get the lock still returns the correct payload once the
    holder has built it (poll-and-serve), and never blocks indefinitely / returns nothing.
  - Per-(cache-key) lock: different filter combinations do not serialize against each
    other.
  - The helper does NOT mutate the payload (no contract change / no recompute here — the
    callers run _refresh_marketplace_live_fields on whatever it returns).

House style: SimpleTestCase + LocMemCache, no real DB / schema switch.
"""
import threading

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from accounts import views as views_mod
from accounts.views import _PUBLIC_LIST_TTL, _public_list_get_or_build


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class SingleFlightHelperTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_hit_returns_cached_without_building(self):
        cache.set("mp:key", {"restaurants": ["cached"]}, _PUBLIC_LIST_TTL)
        calls = []

        def build():
            calls.append(1)
            return {"restaurants": ["fresh"]}

        out = _public_list_get_or_build("mp:key", build)
        self.assertEqual(out, {"restaurants": ["cached"]})
        self.assertEqual(calls, [], "build fn must NOT run on a cache hit")

    def test_miss_builds_once_caches_and_releases_lock(self):
        calls = []

        def build():
            calls.append(1)
            return {"restaurants": ["built"]}

        out = _public_list_get_or_build("mp:key", build)
        self.assertEqual(out, {"restaurants": ["built"]})
        self.assertEqual(len(calls), 1, "build runs exactly once on a clean miss")
        # Result was cached under the key …
        self.assertEqual(cache.get("mp:key"), {"restaurants": ["built"]})
        # … and the lock was released (delete in finally), so the next miss can re-lock.
        self.assertIsNone(cache.get("mp:key:lock"))

    def test_follower_serves_holder_value_without_building(self):
        """If the per-key lock is already held AND the value is present, the follower
        returns the cached value and never calls its own build fn."""
        # Simulate: holder has taken the lock and already populated the key.
        cache.add("mp:key:lock", "1", timeout=10)
        cache.set("mp:key", {"restaurants": ["holder"]}, _PUBLIC_LIST_TTL)
        calls = []

        def build():
            calls.append(1)
            return {"restaurants": ["should-not-build"]}

        out = _public_list_get_or_build("mp:key", build)
        self.assertEqual(out, {"restaurants": ["holder"]})
        self.assertEqual(calls, [], "follower must serve the holder's value, not rebuild")

    def test_follower_builds_when_holder_too_slow(self):
        """Lock held but value never appears (holder died / too slow) → the follower
        falls back to building itself rather than blocking forever or returning nothing."""
        cache.add("mp:key:lock", "1", timeout=10)  # held, but key stays empty
        calls = []

        def build():
            calls.append(1)
            return {"restaurants": ["fallback"]}

        # Shrink the wait so the test doesn't take 2s.
        with override_settings():
            orig_total = views_mod._PUBLIC_LIST_WAIT_TOTAL
            orig_step = views_mod._PUBLIC_LIST_WAIT_STEP
            views_mod._PUBLIC_LIST_WAIT_TOTAL = 0.15
            views_mod._PUBLIC_LIST_WAIT_STEP = 0.02
            try:
                out = _public_list_get_or_build("mp:key", build)
            finally:
                views_mod._PUBLIC_LIST_WAIT_TOTAL = orig_total
                views_mod._PUBLIC_LIST_WAIT_STEP = orig_step

        self.assertEqual(out, {"restaurants": ["fallback"]})
        self.assertEqual(len(calls), 1, "follower builds itself when holder is too slow")
        self.assertEqual(cache.get("mp:key"), {"restaurants": ["fallback"]})

    def test_per_key_lock_does_not_serialize_distinct_keys(self):
        """A lock held for key A must not block a build for key B (per-key locking)."""
        cache.add("mp:A:lock", "1", timeout=10)  # key A locked + never populated
        calls = []

        def build_b():
            calls.append("b")
            return {"restaurants": ["B"]}

        # Build for a DIFFERENT key proceeds immediately (its own lock is free).
        out = _public_list_get_or_build("mp:B", build_b)
        self.assertEqual(out, {"restaurants": ["B"]})
        self.assertEqual(calls, ["b"])

    def test_concurrent_misses_build_once(self):
        """Under simulated concurrency (many threads, same key, simultaneous miss), the
        expensive build runs ~once and every caller gets the same payload."""
        build_count = []
        build_lock = threading.Lock()
        start = threading.Barrier(8)

        def build():
            with build_lock:
                build_count.append(1)
            # Hold a beat so the followers are still inside their poll window while the
            # holder is "building" — mirrors a real slow rebuild.
            import time
            time.sleep(0.1)
            return {"restaurants": ["once"]}

        results = []
        results_lock = threading.Lock()

        def worker():
            start.wait()
            out = _public_list_get_or_build("mp:hot", build)
            with results_lock:
                results.append(out)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one thread won the lock and ran the expensive build; the rest polled
        # and served its value.
        self.assertEqual(sum(build_count), 1,
                         f"expected a single rebuild under concurrency, got {sum(build_count)}")
        self.assertEqual(len(results), 8)
        for r in results:
            self.assertEqual(r, {"restaurants": ["once"]})

    def test_does_not_mutate_payload(self):
        """The helper returns the payload verbatim (no contract change / no recompute);
        the caller is responsible for _refresh_marketplace_live_fields."""
        payload = {"restaurants": [{"_raw_is_open": True}], "_flash_windows": [1]}

        def build():
            return payload

        out = _public_list_get_or_build("mp:key", build)
        self.assertIs(out, payload)
        # Internal keys are untouched here — stripping happens downstream in the caller.
        self.assertIn("_flash_windows", out)
        self.assertIn("_raw_is_open", out["restaurants"][0])
