"""Run 8 G3a — A2-01: "Remove driver" must not strand in-flight delivery jobs.

The OWNER-8 re-open cascade (re-open a revoked driver's active DeliveryJobs to
dispatch + re-offer) lived only on the AdminDrivers reject path. It is now a
shared helper (_reopen_driver_delivery_jobs) also called by the AdminCustomers
detail PATCH when is_driver flips True -> False, and the response reports
reopened_deliveries. The reject path itself is covered by a regression test
(the extraction must not change its behavior).

Unit-level (SimpleTestCase + mocks — no real DB), following test_admin_customers.py.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import Customer, User
from accounts.views import AdminCustomerDetailView, AdminDriverApprovalView


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


def _make_customer(**overrides):
    c = Customer(
        id=overrides.get("id", 5),
        is_driver=overrides.get("is_driver", True),
        is_driver_online=overrides.get("is_driver_online", False),
        driver_approved=overrides.get("driver_approved", True),
    )
    c.save = MagicMock()
    return c


class AdminCustomerDetailRemoveDriverTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminCustomerDetailView.as_view()

    def _patch(self, customer_id, data, customer=None):
        req = self.factory.patch(f"/api/admin/customers/{customer_id}/", data, format="json")
        req.user = _admin()
        with patch("accounts.models.Customer.objects") as mock_objs, \
             patch("accounts.views.log_admin_action"):
            mock_objs.get.return_value = customer or _make_customer()
            with patch("accounts.views._reopen_driver_delivery_jobs") as mock_reopen:
                mock_reopen.return_value = [11, 12]
                resp = self.view(req, customer_id=customer_id)
        return resp, mock_reopen

    def test_remove_driver_reopens_inflight_jobs_and_reports_count(self):
        resp, mock_reopen = self._patch(5, {"is_driver": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_driver"])
        mock_reopen.assert_called_once()
        self.assertEqual(resp.data["reopened_deliveries"], 2)

    def test_remove_driver_also_takes_driver_offline(self):
        customer = _make_customer(is_driver_online=True)
        resp, mock_reopen = self._patch(5, {"is_driver": False}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_driver_online"])
        mock_reopen.assert_called_once()

    def test_make_driver_does_not_reopen_jobs(self):
        customer = _make_customer(is_driver=False)
        resp, mock_reopen = self._patch(5, {"is_driver": True}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_driver"])
        mock_reopen.assert_not_called()
        self.assertEqual(resp.data["reopened_deliveries"], 0)

    def test_patch_without_is_driver_does_not_reopen_jobs(self):
        resp, mock_reopen = self._patch(5, {})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_reopen.assert_not_called()


class AdminDriverRejectCascadeRegressionTests(SimpleTestCase):
    """The helper extraction must not change the reject path's behavior."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverApprovalView.as_view()

    def test_reject_still_reopens_jobs_via_helper(self):
        req = self.factory.post("/api/admin/drivers/5/reject/", {"reason": "bad docs"}, format="json")
        req.user = _admin()
        driver = _make_customer()
        with patch("accounts.models.Customer.objects") as mock_objs, \
             patch("accounts.views.log_admin_action"), \
             patch("accounts.views._reopen_driver_delivery_jobs") as mock_reopen:
            mock_objs.get.return_value = driver
            mock_reopen.return_value = [21]
            resp = self.view(req, driver_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_reopen.assert_called_once_with(driver)
        self.assertEqual(resp.data["reopened_deliveries"], 1)
        self.assertFalse(resp.data["is_driver"])
