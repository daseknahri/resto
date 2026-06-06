"""
Unit tests for the reservation slot-capacity guard (LeadViewSet._slot_would_oversell),
which backs the oversell-prevention fix. SimpleTestCase + mocks (no DB).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from sales.views import LeadViewSet


def _tenant():
    return SimpleNamespace(id=1, schema_name="t1")


def _profile(max_covers, slot_minutes=60, tzname=""):
    return SimpleNamespace(
        max_covers_per_slot=max_covers, slot_duration_minutes=slot_minutes, timezone=tzname
    )


class SlotOversellTests(SimpleTestCase):
    def setUp(self):
        self.view = LeadViewSet()
        self.when = timezone.now() + timedelta(days=1)

    def _run(self, profile, used_total, party):
        with patch("django_tenants.utils.schema_context"), \
             patch("tenancy.models.Profile") as P, \
             patch("sales.views.Lead") as L:
            P.objects.filter.return_value.first.return_value = profile
            L.objects.filter.return_value.aggregate.return_value = {"total": used_total}
            return self.view._slot_would_oversell(_tenant(), self.when, party)

    def test_no_capacity_management_allows(self):
        self.assertIsNone(self._run(_profile(0), 0, 4))

    def test_within_capacity_allows(self):
        self.assertIsNone(self._run(_profile(10), 4, 4))  # 4+4 <= 10

    def test_exactly_full_allows(self):
        self.assertIsNone(self._run(_profile(10), 6, 4))  # 6+4 == 10

    def test_oversell_rejected(self):
        out = self._run(_profile(10), 8, 4)  # 8+4 > 10
        self.assertIsNotNone(out)
        self.assertEqual(out["detail"], "fully_booked")
        self.assertEqual(out["used"], 8)
        self.assertEqual(out["max"], 10)

    def test_errors_are_swallowed_and_allow(self):
        # A capacity-check error must never block a booking.
        with patch("tenancy.models.Profile", side_effect=Exception("boom")):
            self.assertIsNone(self.view._slot_would_oversell(_tenant(), self.when, 4))
