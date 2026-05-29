"""
Unit tests for the _default_days() helper in
sales/management/commands/prune_admin_audit_logs.py.

The function reads ADMIN_AUDIT_RETENTION_DAYS from the environment,
validates it is a positive integer, and falls back to 180 for all
invalid / missing / non-positive values.

All tests are unit-level (SimpleTestCase — no real DB).
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from sales.management.commands.prune_admin_audit_logs import _default_days


class DefaultDaysTests(SimpleTestCase):

    def test_returns_180_when_env_var_absent(self):
        import os
        os.environ.pop("ADMIN_AUDIT_RETENTION_DAYS", None)
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop("ADMIN_AUDIT_RETENTION_DAYS", None)
            self.assertEqual(_default_days(), 180)

    def test_returns_configured_integer(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "365"}):
            self.assertEqual(_default_days(), 365)

    def test_returns_configured_small_integer(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "30"}):
            self.assertEqual(_default_days(), 30)

    def test_zero_falls_back_to_180(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "0"}):
            self.assertEqual(_default_days(), 180)

    def test_negative_falls_back_to_180(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "-90"}):
            self.assertEqual(_default_days(), 180)

    def test_non_numeric_string_falls_back_to_180(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "forever"}):
            self.assertEqual(_default_days(), 180)

    def test_empty_string_falls_back_to_180(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": ""}):
            self.assertEqual(_default_days(), 180)

    def test_whitespace_only_falls_back_to_180(self):
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "   "}):
            self.assertEqual(_default_days(), 180)

    def test_float_string_falls_back_to_180(self):
        # int("90.5") raises ValueError → fallback
        with patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": "90.5"}):
            self.assertEqual(_default_days(), 180)
