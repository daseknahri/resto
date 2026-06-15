"""Neutral cache helpers shared across apps — no app-model imports, so any app may
import this without creating a cycle (mirrors tenancy.delivery_pricing as a pure leaf).

Currently houses the single-flight (cache-stampede / thundering-herd) guard reused by
BOTH the public marketplace/directory list endpoints (accounts.views) AND the per-tenant
public menu cache (menu.views) — the two highest-traffic public read paths.
"""
from __future__ import annotations

import time

from django.core.cache import cache


def get_or_build_single_flight(
    cache_key,
    build_fn,
    *,
    ttl,
    lock_ttl=10,
    wait_total=2.0,
    wait_step=0.05,
):
    """Return the cached value for *cache_key*, building it AT MOST ONCE under concurrency.

    On a cache MISS at peak (TTL just lapsed), every concurrent request would otherwise
    run the expensive *build_fn* simultaneously across the worker pool — a thundering herd
    that spikes DB load exactly when the cache should be shielding it. This collapses that:

    - HIT: return the cached value immediately (no lock, no build).
    - MISS + acquire the per-key lock: call *build_fn*, ``cache.set`` the result under
      *cache_key* for *ttl*, release the lock, return the freshly built value.
    - MISS + lock held by someone else: poll *cache_key* for up to ~*wait_total* seconds;
      if the holder populates it, return that value. If the holder is too slow (or died),
      fall back to building it ourselves — never block forever, never return nothing.

    The lock is per cache-key (so distinct keys / filter combos do NOT serialize), atomic
    (``cache.add`` = set-if-absent), and auto-expires after *lock_ttl* if a holder dies
    mid-build. This helper does NOT mutate the payload: it returns whatever *build_fn*
    produced (or the cached copy thereof) verbatim, so the response contract is unchanged.
    """
    hit = cache.get(cache_key)
    if hit is not None:
        return hit

    lock_key = f"{cache_key}:lock"
    # cache.add is atomic: it sets the key only if absent and returns True to the winner.
    if cache.add(lock_key, "1", timeout=lock_ttl):
        try:
            value = build_fn()
            cache.set(cache_key, value, ttl)
            return value
        finally:
            # Release early so the next TTL lapse isn't blocked for the full lock TTL.
            cache.delete(lock_key)

    # We lost the race: another request is building. Briefly poll for its result.
    deadline = time.monotonic() + wait_total
    while time.monotonic() < deadline:
        time.sleep(wait_step)
        hit = cache.get(cache_key)
        if hit is not None:
            return hit
    # Holder too slow (or died): build it ourselves rather than returning nothing.
    value = build_fn()
    cache.set(cache_key, value, ttl)
    return value
