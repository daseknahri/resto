"""Run 8 G3b W7 — driver earnings endpoint (A2-26).

A2-26: payouts were returned with no ordering (an arbitrary 20) and the
response carried no cap, so the panel could not note it. The GET now orders
payouts by -created_at and exposes "limit": 20.

Mock-based (no DB), following test_driver_earnings.py: the view is called
through APIRequestFactory with a MagicMock platform-admin user.
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import AdminDriverEarningsView


def _admin():
    u = MagicMock(spec=User)
    u.is_platform_admin = True
    return u


def _payout(pk, amount, created_at):
    p = SimpleNamespace(
        id=pk, amount=Decimal(amount), method="cash",
        reference=f"REF-{pk}", note=f"note {pk}", created_at=created_at,
    )
    return p


class AdminDriverEarningsPayoutOrderTests(SimpleTestCase):
    """A2-26: payouts newest-first + the cap exposed as "limit"."""

    def setUp(self):
        patcher = patch("accounts.views.log_admin_action")
        self.mock_log = patcher.start()
        self.addCleanup(patcher.stop)
        self.factory = APIRequestFactory()
        self.view = AdminDriverEarningsView.as_view()

    @staticmethod
    def _summary():
        return {
            "earned": Decimal("100"), "paid": Decimal("40"),
            "owed": Decimal("60"), "wallet_balance": Decimal("60"),
            "ledger_owed": Decimal("60"), "cashout_total": Decimal("0"),
        }

    def _get(self, payouts):
        req = self.factory.get("/api/admin/drivers/7/earnings/")
        req.user = _admin()
        driver = MagicMock()
        driver.id = 7
        driver.name = "Ali"
        driver.phone = "0612345678"
        with patch("accounts.views.Customer") as mock_cust, \
             patch("accounts.driver_service.driver_earnings_summary",
                   return_value=self._summary()), \
             patch("accounts.models.DeliveryJob") as mock_dj, \
             patch("accounts.models.DriverPayout") as mock_dp:
            mock_cust.objects.get.return_value = driver
            mock_dj.objects.filter.return_value.order_by.return_value = []
            # The DB returns rows in the order the queryset yields them; the
            # view must ASK for -created_at before slicing [:20].
            mock_dp.objects.filter.return_value.order_by.return_value.__getitem__.return_value = payouts
            resp = self.view(req, driver_id=7)
            return resp, mock_dp.objects.filter.return_value.order_by

    def test_payouts_ordered_by_minus_created_at(self):
        oldest = _payout(1, "10", datetime(2026, 1, 1, 10, tzinfo=timezone.utc))
        middle = _payout(2, "20", datetime(2026, 1, 2, 10, tzinfo=timezone.utc))
        newest = _payout(3, "30", datetime(2026, 1, 3, 10, tzinfo=timezone.utc))
        resp, order_by = self._get([newest, middle, oldest])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order_by.assert_called_once_with("-created_at")
        self.assertEqual(
            [p["id"] for p in resp.data["payouts"]], [3, 2, 1],
        )

    def test_payouts_expose_note_reference_and_limit(self):
        resp, _ = self._get([_payout(3, "30", datetime(2026, 1, 3, 10, tzinfo=timezone.utc))])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # A2-26: the panel notes the cap from this value (latest 20 rows).
        self.assertEqual(resp.data["limit"], 20)
        row = resp.data["payouts"][0]
        self.assertEqual(row["reference"], "REF-3")
        self.assertEqual(row["note"], "note 3")
