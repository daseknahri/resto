"""Tests for AdminCustomerListView (platform customer directory). No-DB SimpleTestCase."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import AdminCustomerListView


def _admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = True
    return u


def _non_admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    return u


class AdminCustomerListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerListView.as_view()

    def _get(self, user=None, query=""):
        req = self.factory.get("/api/admin/customers/" + query)
        req.user = user or _admin()
        return self.view(req)

    def test_non_admin_returns_403(self):
        self.assertEqual(self._get(user=_non_admin()).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_returns_customer_rows(self):
        c = MagicMock()
        c.id = 1
        c.name = "Ali"
        c.phone = "+212600000000"
        c.phone_verified = True
        c.email = "ali@example.com"
        c.email_verified = False
        c.google_sub = None
        c.wallet_balance = "50.00"
        c.loyalty_points = 10
        c.is_driver = False
        c.created_at = MagicMock()
        c.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"

        with patch("accounts.views.Customer") as mock_cust:
            qs = mock_cust.objects.all.return_value.order_by.return_value
            qs.count.return_value = 1
            qs.__getitem__ = lambda s, k: [c]
            resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 1)
        row = resp.data["results"][0]
        self.assertEqual(row["name"], "Ali")
        self.assertTrue(row["phone_verified"])
        self.assertEqual(row["wallet_balance"], "50.00")
        self.assertEqual(row["loyalty_points"], 10)
