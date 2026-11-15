"""Run 8 G3a — A2-03: customer detail GET exposes the ledger total.

The wallet ledger is capped at 50 rows server-side but the response carried no
total, so the UI could not say "latest 50 of N". The detail GET now returns
transactions_total (count over all wallet transactions for the customer).
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import Customer, User
from accounts.views import AdminCustomerDetailView


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


class AdminCustomerDetailLedgerTotalTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerDetailView.as_view()

    @patch("accounts.views.log_admin_action")
    @patch("accounts.models.DeliveryJob.objects")
    @patch("accounts.models.CustomerRating.objects")
    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.Customer.objects")
    def test_get_returns_transactions_total(
        self, mock_cust_objs, mock_tx_objs, mock_rating_objs, mock_job_objs, mock_log
    ):
        c = Customer(id=5, is_driver=False, is_driver_online=False)
        c.name = "Sara"
        c.phone = "0611223344"
        c.phone_verified = True
        c.email = ""
        c.email_verified = False
        c.google_sub = ""
        c.wallet_balance = Decimal("120.00")
        c.loyalty_points = 10
        c.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        mock_cust_objs.get.return_value = c

        tx = MagicMock()
        tx.id = 1
        tx.type = "topup"
        tx.amount = Decimal("50.00")
        tx.balance_after = Decimal("120.00")
        tx.tenant_id = None
        tx.reference = "TOP-1"
        tx.note = ""
        tx.created_at = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
        mock_tx_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [tx]
        mock_tx_objs.filter.return_value.count.return_value = 73
        mock_rating_objs.filter.return_value.aggregate.return_value = {"avg": None, "count": 0}

        req = self.factory.get("/api/admin/customers/5/")
        req.user = _admin()
        resp = self.view(req, customer_id=5)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["transactions_total"], 73)
        self.assertEqual(len(resp.data["transactions"]), 1)
        self.assertEqual(resp.data["transactions"][0]["balance_after"], "120.00")
