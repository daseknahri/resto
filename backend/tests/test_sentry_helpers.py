"""
Unit tests for config/sentry.py:

  _bool_env(name, default=False)
    Reads an environment variable and coerces it to bool.

  _float_env(name, default=0.0)
    Reads an environment variable and coerces it to a non-negative float.

  init_sentry()
    Initialises Sentry SDK when DJANGO_SENTRY_DSN is set.
    No-op when DSN is absent or blank.
    Resolves environment and release from env vars with defined fallbacks.

All tests are unit-level (SimpleTestCase — no real Sentry connection).
"""
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase

from config.sentry import _bool_env, _float_env, init_sentry


# ══════════════════════════════════════════════════════════════════════════════
# _bool_env
# ══════════════════════════════════════════════════════════════════════════════

class SentryBoolEnvTests(SimpleTestCase):
    """_bool_env reads an env var and coerces to bool."""

    def test_returns_false_default_when_var_absent(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("_TEST_SENTRY_BOOL", None)
            self.assertFalse(_bool_env("_TEST_SENTRY_BOOL"))

    def test_returns_true_default_when_var_absent_and_default_true(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("_TEST_SENTRY_BOOL", None)
            self.assertTrue(_bool_env("_TEST_SENTRY_BOOL", default=True))

    def test_truthy_values(self):
        for val in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            with patch.dict("os.environ", {"_TSB": val}):
                self.assertTrue(_bool_env("_TSB"), f"Expected True for {val!r}")

    def test_falsy_values(self):
        for val in ("0", "false", "no", "off", "random", "2"):
            with patch.dict("os.environ", {"_TSB": val}):
                self.assertFalse(_bool_env("_TSB"), f"Expected False for {val!r}")

    def test_whitespace_stripped_before_comparison(self):
        with patch.dict("os.environ", {"_TSB": "  true  "}):
            self.assertTrue(_bool_env("_TSB"))

    def test_empty_string_treated_as_missing_returns_default(self):
        # os.getenv returns "" (not None) for an explicitly-set-empty var;
        # "".strip().lower() not in truthy set → returns False (the default)
        with patch.dict("os.environ", {"_TSB": ""}):
            self.assertFalse(_bool_env("_TSB"))


# ══════════════════════════════════════════════════════════════════════════════
# _float_env
# ══════════════════════════════════════════════════════════════════════════════

class SentryFloatEnvTests(SimpleTestCase):
    """_float_env reads an env var and coerces to a non-negative float."""

    def test_returns_default_when_var_absent(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("_TEST_SENTRY_FLOAT", None)
            self.assertEqual(_float_env("_TEST_SENTRY_FLOAT"), 0.0)

    def test_custom_default_returned_when_var_absent(self):
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("_TEST_SENTRY_FLOAT", None)
            self.assertEqual(_float_env("_TEST_SENTRY_FLOAT", default=1.5), 1.5)

    def test_returns_default_when_var_is_empty_string(self):
        with patch.dict("os.environ", {"_TSF": ""}):
            self.assertEqual(_float_env("_TSF", default=0.5), 0.5)

    def test_returns_default_when_var_is_whitespace_only(self):
        with patch.dict("os.environ", {"_TSF": "   "}):
            self.assertEqual(_float_env("_TSF", default=2.0), 2.0)

    def test_valid_float_value_returned(self):
        with patch.dict("os.environ", {"_TSF": "0.5"}):
            self.assertAlmostEqual(_float_env("_TSF"), 0.5)

    def test_integer_string_accepted_as_float(self):
        with patch.dict("os.environ", {"_TSF": "1"}):
            self.assertAlmostEqual(_float_env("_TSF"), 1.0)

    def test_non_numeric_returns_default(self):
        with patch.dict("os.environ", {"_TSF": "bad"}):
            self.assertEqual(_float_env("_TSF", default=3.0), 3.0)

    def test_negative_value_returns_default(self):
        with patch.dict("os.environ", {"_TSF": "-1.0"}):
            self.assertEqual(_float_env("_TSF", default=5.0), 5.0)

    def test_zero_is_valid(self):
        with patch.dict("os.environ", {"_TSF": "0.0"}):
            self.assertAlmostEqual(_float_env("_TSF", default=1.0), 0.0)

    def test_whitespace_padded_float_accepted(self):
        with patch.dict("os.environ", {"_TSF": "  0.25  "}):
            # strip is applied before float() conversion
            self.assertAlmostEqual(_float_env("_TSF"), 0.25)


# ══════════════════════════════════════════════════════════════════════════════
# init_sentry
# ══════════════════════════════════════════════════════════════════════════════

class InitSentryTests(SimpleTestCase):
    """init_sentry() initialises the Sentry SDK or returns early if no DSN."""

    def _run(self, env):
        """Call init_sentry() with mocked sentry_sdk under the given env vars."""
        sentry_init_mock = MagicMock()
        django_integration_mock = MagicMock()
        # Patch sentry_sdk inside the module under test
        sentry_sdk_mock = MagicMock()
        sentry_sdk_mock.init = sentry_init_mock

        with patch.dict("os.environ", env, clear=False):
            with (
                patch.dict(
                    "os.environ",
                    # Remove keys that are NOT in env to avoid stale values
                    {
                        k: "" for k in [
                            "DJANGO_SENTRY_DSN",
                            "DJANGO_SENTRY_RELEASE",
                            "DJANGO_SENTRY_ENVIRONMENT",
                            "APP_ENV",
                            "DJANGO_SENTRY_TRACES_SAMPLE_RATE",
                            "DJANGO_SENTRY_SEND_PII",
                        ]
                        if k not in env
                    },
                    clear=False,
                ),
                patch("config.sentry.sentry_init", sentry_init_mock, create=True),  # create-true-ok: sentry_init is imported lazily inside init_sentry (from sentry_sdk import init as sentry_init), not at config.sentry module scope; create=True is required to patch the name.
                patch(
                    "config.sentry.DjangoIntegration",
                    django_integration_mock,
                    create=True,  # create-true-ok: DjangoIntegration is imported lazily inside init_sentry (from sentry_sdk.integrations.django import DjangoIntegration), not at config.sentry module scope; create=True is required to patch the name.
                ),
            ):
                # Patch the local import inside init_sentry
                import sys
                fake_sentry_sdk = MagicMock()
                fake_sentry_sdk.init = sentry_init_mock
                fake_di_module = MagicMock()
                fake_di_module.DjangoIntegration = django_integration_mock
                with (
                    patch.dict(
                        sys.modules,
                        {
                            "sentry_sdk": fake_sentry_sdk,
                            "sentry_sdk.integrations.django": fake_di_module,
                        },
                    )
                ):
                    init_sentry()

        return sentry_init_mock, django_integration_mock

    # ── no DSN → skip ─────────────────────────────────────────────────────────

    def test_empty_dsn_skips_init(self):
        sentry_init_mock, _ = self._run({"DJANGO_SENTRY_DSN": ""})
        sentry_init_mock.assert_not_called()

    def test_whitespace_dsn_skips_init(self):
        sentry_init_mock, _ = self._run({"DJANGO_SENTRY_DSN": "   "})
        sentry_init_mock.assert_not_called()

    def test_absent_dsn_skips_init(self):
        env = {}
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("DJANGO_SENTRY_DSN", None)
            # Call init_sentry with no DSN present
            import sys
            sentry_init_mock = MagicMock()
            fake_sentry_sdk = MagicMock()
            fake_sentry_sdk.init = sentry_init_mock
            with patch.dict(sys.modules, {"sentry_sdk": fake_sentry_sdk}):
                init_sentry()
        sentry_init_mock.assert_not_called()

    # ── with DSN → sentry_init called ─────────────────────────────────────────

    def test_valid_dsn_calls_sentry_init(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
        })
        sentry_init_mock.assert_called_once()

    def test_dsn_passed_to_sentry_init(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertEqual(kwargs["dsn"], "https://key@sentry.io/123")

    # ── environment resolution ─────────────────────────────────────────────────

    def test_environment_from_django_sentry_environment(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
            "DJANGO_SENTRY_ENVIRONMENT": "staging",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertEqual(kwargs["environment"], "staging")

    def test_environment_falls_back_to_app_env(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
            "DJANGO_SENTRY_ENVIRONMENT": "",
            "APP_ENV": "sandbox",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertEqual(kwargs["environment"], "sandbox")

    def test_environment_defaults_to_production_when_both_absent(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
            "DJANGO_SENTRY_ENVIRONMENT": "",
            "APP_ENV": "",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertEqual(kwargs["environment"], "production")

    # ── release resolution ─────────────────────────────────────────────────────

    def test_release_is_none_when_not_set(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
            "DJANGO_SENTRY_RELEASE": "",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertIsNone(kwargs["release"])

    def test_release_passed_when_set(self):
        sentry_init_mock, _ = self._run({
            "DJANGO_SENTRY_DSN": "https://key@sentry.io/123",
            "DJANGO_SENTRY_RELEASE": "v2.3.0",
        })
        kwargs = sentry_init_mock.call_args[1]
        self.assertEqual(kwargs["release"], "v2.3.0")
