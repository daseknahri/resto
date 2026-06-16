"""R19 import-smoke: every app module must import without raising.

WHY THIS EXISTS
---------------
A real production incident once 500'd *every* marketplace order because a view
imported ``Profile`` from the wrong module.  The broken import was swallowed by a
broad ``try/except`` at request time, and CI stayed GREEN because the unit tests
mocked the import surface with ``patch(..., create=True)`` (``create=True``
silently invents a missing attribute, so the mock hid the broken import).

This test is the loud, cheap safety net for that whole bug class: it walks every
importable module under the app packages and asserts each one imports cleanly.
A broken/lazy/relocated import now FAILS at test *collection* time instead of
hiding behind a try/except until a live request hits it.

It is intentionally **non-DB / pure import** (``SimpleTestCase``) so it runs
everywhere — locally without Postgres and in CI alike.

EXCLUSIONS
----------
* ``migrations`` and ``management`` subpackages — they exist for the ORM / CLI
  and are not part of the request-serving import surface; some have heavy or
  ordering-sensitive import side effects.
* ``tests`` subpackages (if any) — not product code.
* ``config.asgi`` / ``config.wsgi`` — they instantiate the ASGI/WSGI
  application at import time (server bootstrap, not importable app logic).
"""

from __future__ import annotations

import importlib
import pkgutil

from django.test import SimpleTestCase

# Top-level app packages whose every module must import cleanly.
APP_PACKAGES = ["accounts", "menu", "tenancy", "sales", "realtime", "config"]

# Module-name segments to skip while walking (migrations/mgmt/tests + bootstrap).
EXCLUDED_SEGMENTS = (".migrations", ".management", ".tests")
EXCLUDED_MODULES = {
    # Instantiate the server application at import time — bootstrap, not app code.
    "config.asgi",
    "config.wsgi",
}

# KNOWN landmines that are NOT live broken imports but cannot be plain-imported.
# Each entry maps module -> the substring its import error MUST contain.  We pin
# the exact failure so this stays a *documented* exception: if the module ever
# starts failing for a DIFFERENT reason (a genuinely new broken import), the
# substring check below fails and this test catches it loudly.
#
# Currently empty: the only former entry, ``tenancy.profile`` (an orphan dead
# duplicate-`Profile`-model module), was deleted.  Add an entry here only when a
# module legitimately cannot be plain-imported and that is intentional.
KNOWN_BROKEN: dict[str, str] = {}


def _walk_app_modules():
    """Yield the dotted names of every importable app module to smoke-test."""
    seen = []
    for pkg_name in APP_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        # Include the package __init__ itself.
        seen.append(pkg_name)
        for mod_info in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            name = mod_info.name
            if any(seg in name for seg in EXCLUDED_SEGMENTS):
                continue
            if name in EXCLUDED_MODULES:
                continue
            seen.append(name)
    return sorted(set(seen))


class ImportSmokeTests(SimpleTestCase):
    """Every app module imports without raising (catches swallowed ImportError)."""

    def test_every_app_module_imports_cleanly(self):
        modules = _walk_app_modules()

        # Sanity floor: if discovery silently collapses to a handful of modules,
        # the safety net is not actually covering the app — fail loudly.
        self.assertGreater(
            len(modules),
            50,
            f"import-smoke only discovered {len(modules)} modules across "
            f"{APP_PACKAGES}; walk_packages likely broke — net is not covering "
            "the app code it is meant to police.",
        )

        failures = []
        for name in modules:
            try:
                importlib.import_module(name)
            except Exception as exc:  # noqa: BLE001 - we want to surface ANY import error
                expected = KNOWN_BROKEN.get(name)
                if expected is not None and expected in str(exc):
                    # Documented landmine, failing for the documented reason. OK.
                    continue
                failures.append(f"{name}: {type(exc).__name__}: {exc}")

        self.assertEqual(
            failures,
            [],
            "The following app modules failed to import. A broken/relocated/"
            "swallowed import is a real bug (it will 500 the first request that "
            "hits the code path) — fix the import, do NOT mock it away:\n  "
            + "\n  ".join(failures),
        )

    def test_known_broken_modules_still_broken_in_the_documented_way(self):
        """Pin the KNOWN_BROKEN landmines.

        If a landmine ever imports cleanly, delete its KNOWN_BROKEN entry (the
        dead module was removed — good).  If it fails for a NEW reason, that is a
        different (possibly real) bug and this test surfaces it.
        """
        for name, expected_substring in KNOWN_BROKEN.items():
            with self.assertRaises(Exception) as ctx:  # noqa: PT011
                importlib.import_module(name)
            self.assertIn(
                expected_substring,
                str(ctx.exception),
                f"{name} no longer fails with '{expected_substring}'. If it now "
                "imports cleanly, remove it from KNOWN_BROKEN. If it fails for a "
                "different reason, investigate — that may be a new real bug.",
            )
