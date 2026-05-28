"""
Unit tests for miscellaneous management-command helpers and serializer mixins
that have no dedicated test coverage:

  sales.management.commands.prune_admin_audit_logs
    - _default_days

  sales.management.commands.send_reservation_reminders
    - _tenant_name

  sales.serializers.ReservationSlaSerializerMixin
    - get_follow_up_due_at / get_sla_state / get_sla_minutes_overdue
      (delegates to reservation_sla_snapshot; tested here via mocked snapshot)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from sales.management.commands.prune_admin_audit_logs import _default_days
from sales.management.commands.send_reservation_reminders import _tenant_name
from sales.serializers import ReservationSlaSerializerMixin


# ══════════════════════════════════════════════════════════════════════════════
# _default_days
# ══════════════════════════════════════════════════════════════════════════════

class DefaultDaysTests(SimpleTestCase):
    """_default_days reads ADMIN_AUDIT_RETENTION_DAYS from the environment;
    returns 180 as the safe default whenever the env var is absent, blank, or
    not a positive integer."""

    def _patch(self, value):
        return patch.dict("os.environ", {"ADMIN_AUDIT_RETENTION_DAYS": value}, clear=False)

    def _remove(self):
        """Return a context that has no ADMIN_AUDIT_RETENTION_DAYS key at all."""
        import os
        saved = os.environ.pop("ADMIN_AUDIT_RETENTION_DAYS", None)
        return saved

    def test_valid_integer_returned(self):
        with self._patch("90"):
            self.assertEqual(_default_days(), 90)

    def test_large_value_accepted(self):
        with self._patch("365"):
            self.assertEqual(_default_days(), 365)

    def test_zero_falls_back_to_default(self):
        """0 is not positive → returns 180."""
        with self._patch("0"):
            self.assertEqual(_default_days(), 180)

    def test_negative_falls_back_to_default(self):
        with self._patch("-30"):
            self.assertEqual(_default_days(), 180)

    def test_blank_string_falls_back_to_default(self):
        with self._patch(""):
            self.assertEqual(_default_days(), 180)

    def test_whitespace_only_falls_back_to_default(self):
        with self._patch("   "):
            self.assertEqual(_default_days(), 180)

    def test_non_numeric_falls_back_to_default(self):
        with self._patch("forever"):
            self.assertEqual(_default_days(), 180)

    def test_float_string_falls_back_to_default(self):
        """'30.5' is not a plain int string → falls back."""
        with self._patch("30.5"):
            self.assertEqual(_default_days(), 180)

    def test_absent_env_var_returns_default(self):
        """When the env var is not set at all, default of 180 is returned."""
        import os
        saved = os.environ.pop("ADMIN_AUDIT_RETENTION_DAYS", None)
        try:
            self.assertEqual(_default_days(), 180)
        finally:
            if saved is not None:
                os.environ["ADMIN_AUDIT_RETENTION_DAYS"] = saved


# ══════════════════════════════════════════════════════════════════════════════
# _tenant_name
# ══════════════════════════════════════════════════════════════════════════════

class TenantNameTests(SimpleTestCase):
    """_tenant_name returns tenant.name, or tenant.slug if name is empty/falsy."""

    def _tenant(self, name="", slug=""):
        return SimpleNamespace(name=name, slug=slug)

    def test_returns_name_when_set(self):
        t = self._tenant(name="Le Petit Bistro", slug="le-petit-bistro")
        self.assertEqual(_tenant_name(t), "Le Petit Bistro")

    def test_falls_back_to_slug_when_name_is_empty(self):
        t = self._tenant(name="", slug="bistro-demo")
        self.assertEqual(_tenant_name(t), "bistro-demo")

    def test_falls_back_to_slug_when_name_is_none(self):
        t = self._tenant(name=None, slug="my-restaurant")
        self.assertEqual(_tenant_name(t), "my-restaurant")

    def test_name_takes_precedence_over_slug(self):
        t = self._tenant(name="My Place", slug="my-place-slug")
        self.assertNotEqual(_tenant_name(t), "my-place-slug")
        self.assertEqual(_tenant_name(t), "My Place")

    def test_both_empty_returns_empty_string(self):
        t = self._tenant(name="", slug="")
        self.assertEqual(_tenant_name(t), "")


# ══════════════════════════════════════════════════════════════════════════════
# ReservationSlaSerializerMixin — get_follow_up_due_at / get_sla_state /
#                                 get_sla_minutes_overdue
# ══════════════════════════════════════════════════════════════════════════════

class ReservationSlaMixinTests(SimpleTestCase):
    """The three public get_ methods on ReservationSlaSerializerMixin each pluck
    one key from the dict returned by _reservation_sla().  We mock
    _reservation_sla so we can test the delegation in isolation."""

    def _mixin(self, snapshot: dict):
        """Return a mixin instance whose _reservation_sla always returns snapshot."""
        m = ReservationSlaSerializerMixin()
        m.context = {}
        m._reservation_sla = lambda obj: snapshot
        return m

    def _snap(self, **overrides):
        base = {
            "follow_up_due_at": None,
            "sla_state": "not_applicable",
            "sla_minutes_overdue": 0,
        }
        base.update(overrides)
        return base

    # ── get_follow_up_due_at ─────────────────────────────────────────────────
    def test_get_follow_up_due_at_returns_none_when_not_applicable(self):
        m = self._mixin(self._snap(follow_up_due_at=None))
        self.assertIsNone(m.get_follow_up_due_at(None))

    def test_get_follow_up_due_at_returns_datetime(self):
        dt = timezone.now() + timedelta(minutes=30)
        m = self._mixin(self._snap(follow_up_due_at=dt))
        self.assertEqual(m.get_follow_up_due_at(None), dt)

    # ── get_sla_state ────────────────────────────────────────────────────────
    def test_get_sla_state_not_applicable(self):
        m = self._mixin(self._snap(sla_state="not_applicable"))
        self.assertEqual(m.get_sla_state(None), "not_applicable")

    def test_get_sla_state_overdue(self):
        m = self._mixin(self._snap(sla_state="overdue"))
        self.assertEqual(m.get_sla_state(None), "overdue")

    def test_get_sla_state_on_track(self):
        m = self._mixin(self._snap(sla_state="on_track"))
        self.assertEqual(m.get_sla_state(None), "on_track")

    def test_get_sla_state_resolved(self):
        m = self._mixin(self._snap(sla_state="resolved"))
        self.assertEqual(m.get_sla_state(None), "resolved")

    # ── get_sla_minutes_overdue ──────────────────────────────────────────────
    def test_get_sla_minutes_overdue_zero_when_on_track(self):
        m = self._mixin(self._snap(sla_minutes_overdue=0))
        self.assertEqual(m.get_sla_minutes_overdue(None), 0)

    def test_get_sla_minutes_overdue_positive_when_late(self):
        m = self._mixin(self._snap(sla_minutes_overdue=15))
        self.assertEqual(m.get_sla_minutes_overdue(None), 15)

    # ── caching: _reservation_sla_now stored in context ─────────────────────
    def test_context_now_is_cached_across_calls(self):
        """After the first call, context['_reservation_sla_now'] must be set
        so subsequent calls reuse the same 'now' timestamp."""
        calls = []

        def _snap_recording(obj):
            return {
                "follow_up_due_at": None,
                "sla_state": "not_applicable",
                "sla_minutes_overdue": 0,
            }

        m = ReservationSlaSerializerMixin()
        m.context = {}
        # Let the real _reservation_sla run (it will call reservation_sla_snapshot)
        obj = SimpleNamespace(
            source="table_reservation",
            status="new",
            created_at=timezone.now() - timedelta(minutes=5),
        )
        _ = m.get_sla_state(obj)
        self.assertIn("_reservation_sla_now", m.context)
        cached_now = m.context["_reservation_sla_now"]

        # Second call must reuse the same 'now'
        _ = m.get_sla_state(obj)
        self.assertEqual(m.context["_reservation_sla_now"], cached_now)
