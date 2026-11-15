"""Run 8 G3b W8 — AdminCustomerDetailView suspend + profile edit (A2-31).

No-DB SimpleTestCase, same pattern as tests/test_admin_customers.py: the view
is driven through APIRequestFactory with a mocked Customer model and a patched
log_admin_action (hermetic — no audit row is written here).

Covers:
  A2-31 — PATCH is_suspended suspends / reactivates (online drivers go
           offline on suspend); PATCH name/phone/email edits the profile
           (length + email validation, duplicate-phone 400, phone_digits kept
           in update_fields); list rows expose is_suspended.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    AdminCustomerDetailView,
    AdminCustomerListView,
)


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


class _DoesNotExist(Exception):
    pass


def _customer(**overrides):
    c = MagicMock()
    c.id = 5
    c.pk = 5
    c.name = "Sara"
    c.phone = "0611223344"
    c.email = ""
    c.is_driver = False
    c.is_driver_online = False
    c.is_suspended = False
    c.wallet_balance = "120.00"
    c.loyalty_points = 10
    c.created_at = MagicMock()
    c.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


class AdminCustomerSuspendTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerDetailView.as_view()

    def _patch(self, data, user=None):
        req = self.factory.patch("/api/admin/customers/5/", data, format="json")
        req.user = user or _admin()
        return self.view(req, customer_id=5)

    def _mock_customer(self, mock_cust, customer):
        mock_cust.objects.get.return_value = customer
        mock_cust.objects.filter.return_value.exclude.return_value.exists.return_value = False
        mock_cust.DoesNotExist = _DoesNotExist

    def test_suspend_sets_flag_and_returns_it(self):
        c = _customer()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"is_suspended": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_suspended"])
        self.assertTrue(c.is_suspended)
        c.save.assert_called_once_with(update_fields=["is_suspended", "updated_at"])

    def test_reactivate_clears_flag(self):
        c = _customer(is_suspended=True)
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"is_suspended": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_suspended"])
        self.assertFalse(c.is_suspended)

    def test_suspend_online_driver_takes_them_offline(self):
        c = _customer(is_driver=True, is_driver_online=True)
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"is_suspended": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(c.is_driver_online)
        self.assertIn("is_driver_online", c.save.call_args.kwargs["update_fields"])

    def test_non_admin_403(self):
        self.assertEqual(
            self._patch({"is_suspended": True}, user=_non_admin()).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_missing_customer_404(self):
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            mock_cust.DoesNotExist = _DoesNotExist
            mock_cust.objects.get.side_effect = _DoesNotExist
            resp = self._patch({"is_suspended": True})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class AdminCustomerProfileEditTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerDetailView.as_view()

    def _patch(self, data, user=None):
        req = self.factory.patch("/api/admin/customers/5/", data, format="json")
        req.user = user or _admin()
        return self.view(req, customer_id=5)

    def _mock_customer(self, mock_cust, customer, phone_taken=False):
        mock_cust.objects.get.return_value = customer
        mock_cust.objects.filter.return_value.exclude.return_value.exists.return_value = phone_taken
        mock_cust.DoesNotExist = _DoesNotExist

    def test_profile_edit_updates_name_phone_email(self):
        c = _customer()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"name": "Sara New", "phone": "0699887766", "email": "sara@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Sara New")
        self.assertEqual(resp.data["phone"], "0699887766")
        self.assertEqual(resp.data["email"], "sara@example.com")
        # save() recomputes phone_digits from phone — it must be in update_fields
        # or the digits search index goes stale.
        fields = c.save.call_args.kwargs["update_fields"]
        self.assertEqual(set(fields), {"name", "phone", "email", "updated_at", "phone_digits"})

    def test_profile_edit_invalid_email_400(self):
        c = _customer()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"email": "not-an-email"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        c.save.assert_not_called()

    def test_profile_edit_name_too_long_400(self):
        c = _customer()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c)
            resp = self._patch({"name": "x" * 81})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        c.save.assert_not_called()

    def test_profile_edit_duplicate_phone_400(self):
        c = _customer()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            self._mock_customer(mock_cust, c, phone_taken=True)
            resp = self._patch({"phone": "0600000000"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        c.save.assert_not_called()


class AdminCustomerListSuspendedTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerListView.as_view()

    def test_list_row_includes_is_suspended(self):
        c = _customer(is_suspended=True)
        req = self.factory.get("/api/admin/customers/")
        req.user = _admin()
        with patch("accounts.views.Customer") as mock_cust, patch("accounts.views.log_admin_action"):
            qs = mock_cust.objects.all.return_value.order_by.return_value
            qs.count.return_value = 1
            qs.__getitem__ = lambda s, k: [c]
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["results"][0]["is_suspended"])
