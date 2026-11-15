"""Run 8 G3a — A2-02: rejected drivers list + re-approve path.

Reject used to be one-way on the AdminDrivers screen: the list only showed
is_driver=True rows and approve looked the driver up with is_driver=True, so a
rejected driver 404d on approve. Now GET /api/admin/drivers/?rejected=1 lists
rejected drivers (is_driver=False + rejection stamp, with reason/at in the rows)
and approve re-approves one (restores is_driver, clears the rejection trace).
A customer who was never a driver still 404s on approve, and reject still
requires an active driver.

Unit-level (SimpleTestCase + mocks — no real DB), following test_driver_views.py.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, User
from accounts.views import AdminDriverApprovalView, AdminDriverListView


@contextmanager
def _noop_atomic(*args, **kwargs):
    yield


def _admin_req(factory, path):
    admin = MagicMock(spec=User)
    admin.is_platform_admin = True
    admin.is_authenticated = True
    req = factory.post(path)
    force_authenticate(req, user=admin)
    return req


def _make_driver(**overrides):
    c = Customer(
        id=overrides.get("id", 5),
        is_driver=overrides.get("is_driver", True),
        driver_approved=overrides.get("driver_approved", True),
        is_driver_online=False,
        driver_vehicle="",
    )
    c.save = MagicMock()
    c.driver_rejected_at = overrides.get("driver_rejected_at")
    c.driver_rejection_reason = overrides.get("driver_rejection_reason", "")
    return c


class AdminDriverReapproveTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverApprovalView.as_view()
        _p = patch("django.db.transaction.atomic", _noop_atomic)
        _p.start()
        self.addCleanup(_p.stop)

    @patch("accounts.models.Customer.objects")
    def test_reapprove_restores_rejected_driver(self, mock_objs):
        rejected = _make_driver(
            is_driver=False,
            driver_approved=False,
            driver_rejected_at=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            driver_rejection_reason="bad docs",
        )
        mock_objs.get.return_value = rejected
        with patch("accounts.views.log_admin_action"):
            resp = self.view(_admin_req(self.factory, "/api/admin/drivers/5/approve/"), driver_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(rejected.is_driver)
        self.assertTrue(rejected.driver_approved)
        self.assertIsNone(rejected.driver_rejected_at)
        self.assertEqual(rejected.driver_rejection_reason, "")
        self.assertTrue(resp.data["is_driver"])
        self.assertTrue(resp.data["approved"])

    @patch("accounts.models.Customer.objects")
    def test_approve_never_driver_returns_404(self, mock_objs):
        mock_objs.get.return_value = _make_driver(is_driver=False, driver_rejected_at=None)
        with patch("accounts.views.log_admin_action"):
            resp = self.view(_admin_req(self.factory, "/api/admin/drivers/5/approve/"), driver_id=5)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_reject_non_driver_returns_404(self, mock_objs):
        mock_objs.get.return_value = _make_driver(is_driver=False, driver_rejected_at=None)
        with patch("accounts.views.log_admin_action"):
            resp = self.view(_admin_req(self.factory, "/api/admin/drivers/5/reject/"), driver_id=5)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class AdminDriverRejectedListTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverListView.as_view()

    def _rejected_customer(self):
        c = _make_driver(
            id=9,
            is_driver=False,
            driver_approved=False,
            driver_rejected_at=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            driver_rejection_reason="bad docs",
        )
        c.name = "Karim"
        c.phone = "0611223344"
        c.email = ""
        c.driver_vehicle_type = ""
        c.driver_licence_url = ""
        c.driver_insurance_url = ""
        c.driver_car_approved = False
        c.driver_licence_expiry = None
        c.driver_insurance_expiry = None
        c.driver_lat = None
        c.driver_lng = None
        c.driver_position_updated_at = None
        c.wallet_balance = Decimal("0")
        c.created_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        return c

    @patch("accounts.views.log_admin_action")
    @patch("accounts.models.DriverPayout.objects")
    @patch("accounts.models.DeliveryJob.objects")
    @patch("accounts.models.Customer.objects")
    def test_rejected_filter_lists_rejected_drivers(
        self, mock_cust_objs, mock_job_objs, mock_payout_objs, mock_log
    ):
        rejected = self._rejected_customer()
        mock_cust_objs.filter.return_value.order_by.return_value.__getitem__.return_value = [rejected]
        # Run 8 G3a A2-08: the list is the envelope {results, total, limit, stats}.
        mock_cust_objs.filter.return_value.count.return_value = 1
        mock_job_objs.filter.return_value.count.return_value = 0
        # Batch stats/earnings aggregates return nothing for the rejected row.
        mock_job_objs.filter.return_value.values.return_value.annotate.return_value = []
        mock_payout_objs.filter.return_value.values.return_value.annotate.return_value = []

        req = self.factory.get("/api/admin/drivers/?rejected=1")
        admin = MagicMock(spec=User)
        admin.is_platform_admin = True
        admin.is_authenticated = True
        force_authenticate(req, user=admin)
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cust_objs.filter.assert_called_once_with(
            is_driver=False, driver_rejected_at__isnull=False
        )
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["id"], 9)
        self.assertEqual(resp.data["results"][0]["driver_rejection_reason"], "bad docs")
        self.assertEqual(resp.data["results"][0]["driver_rejected_at"], "2026-11-01T10:00:00+00:00")
        self.assertEqual(resp.data["total"], 1)
        self.assertEqual(resp.data["limit"], 200)
        self.assertEqual(resp.data["stats"]["total"], 1)

    @patch("accounts.views.log_admin_action")
    @patch("accounts.models.DriverPayout.objects")
    @patch("accounts.models.DeliveryJob.objects")
    @patch("accounts.models.Customer.objects")
    def test_default_list_still_filters_active_drivers(
        self, mock_cust_objs, mock_job_objs, mock_payout_objs, mock_log
    ):
        mock_cust_objs.filter.return_value.order_by.return_value.__getitem__.return_value = []
        mock_cust_objs.filter.return_value.count.return_value = 0
        # A2-08 stats: base_qs.filter(is_driver_online=True / driver_approved=False)
        # .count() chains a second .filter() off the mocked queryset.
        mock_cust_objs.filter.return_value.filter.return_value.count.return_value = 0
        mock_job_objs.filter.return_value.count.return_value = 0
        mock_job_objs.filter.return_value.values.return_value.annotate.return_value = []
        mock_payout_objs.filter.return_value.values.return_value.annotate.return_value = []

        req = self.factory.get("/api/admin/drivers/")
        admin = MagicMock(spec=User)
        admin.is_platform_admin = True
        admin.is_authenticated = True
        force_authenticate(req, user=admin)
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_cust_objs.filter.assert_called_once_with(is_driver=True)
        self.assertEqual(resp.data["results"], [])
        self.assertEqual(resp.data["total"], 0)
        self.assertEqual(resp.data["stats"], {"total": 0, "online": 0, "pending": 0, "total_deliveries": 0})
