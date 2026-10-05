"""Tests for driver earnings/payout views (auth paths, no DB).

RISK IDENTITY-1: DriverEarningsView now authenticates via CustomerSessionAuthentication
+ IsCustomer; the is_driver gate stays in the view, so its 404 contract is unchanged.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, User
from accounts.throttles import AdminPIIThrottle
from accounts.views import AdminDriverEarningsView, DriverEarningsView
from sales.models import AdminAuditLog


def _admin():
    u = MagicMock(spec=User)
    u.is_platform_admin = True
    return u


def _non_admin():
    u = MagicMock(spec=User)
    u.is_platform_admin = False
    return u


class AdminDriverEarningsAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverEarningsView.as_view()

    def test_get_non_admin_403(self):
        req = self.factory.get("/api/admin/drivers/1/earnings/")
        req.user = _non_admin()
        self.assertEqual(self.view(req, driver_id=1).status_code, status.HTTP_403_FORBIDDEN)

    def test_payout_non_admin_403(self):
        req = self.factory.post("/api/admin/drivers/1/payout/", {"amount": "10"}, format="json")
        req.user = _non_admin()
        self.assertEqual(self.view(req, driver_id=1).status_code, status.HTTP_403_FORBIDDEN)


class AdminDriverEarningsPIIAuditThrottleTests(SimpleTestCase):
    """GET exposes a driver's name/phone/earnings → AdminPIIThrottle + a PII-read audit row.
    The payout POST is a money action: it keeps its own audit and must NOT consume (or be
    blocked by) the PII-read throttle bucket."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
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
        }

    def _get(self):
        req = self.factory.get("/api/admin/drivers/7/earnings/")
        req.user = _admin()
        driver = MagicMock()
        driver.id = 7
        driver.name = "Ali"
        driver.phone = "0612345678"
        with patch("accounts.views.Customer") as mock_cust, \
             patch("accounts.driver_service.driver_earnings_summary", return_value=self._summary()), \
             patch("accounts.models.DeliveryJob") as mock_dj, \
             patch("accounts.models.DriverPayout") as mock_dp:
            mock_cust.objects.get.return_value = driver
            mock_dj.objects.filter.return_value.order_by.return_value = []
            mock_dp.objects.filter.return_value = []
            return self.view(req, driver_id=7)

    def _post(self):
        req = self.factory.post("/api/admin/drivers/7/payout/", {"amount": "10"}, format="json")
        req.user = _admin()
        payout = MagicMock()
        payout.id = 1
        payout.amount = Decimal("10")
        with patch("accounts.views.Customer") as mock_cust, \
             patch("accounts.driver_service.record_driver_payout", return_value=payout), \
             patch("accounts.driver_service.driver_earnings_summary", return_value=self._summary()):
            mock_cust.objects.filter.return_value.exists.return_value = True
            return self.view(req, driver_id=7)

    def test_get_writes_pii_viewed_audit_without_pii(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.mock_log.assert_called_once()
        kwargs = self.mock_log.call_args[1]
        # A driver is a Customer row → reuse the existing PII-viewed action (no new enum member).
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.CUSTOMER_PII_VIEWED)
        self.assertEqual(kwargs["target_repr"], "driver:7")
        self.assertEqual(kwargs["metadata"], {"driver_id": 7, "view": "earnings"})
        self.assertNotIn("0612345678", repr(kwargs))

    def test_get_404_is_not_audited(self):
        """No driver data is returned for a missing driver, so there is nothing to audit."""
        req = self.factory.get("/api/admin/drivers/7/earnings/")
        req.user = _admin()
        with patch("accounts.views.Customer") as mock_cust:
            mock_cust.DoesNotExist = KeyError
            mock_cust.objects.get.side_effect = KeyError
            resp = self.view(req, driver_id=7)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.mock_log.assert_not_called()

    def test_get_is_throttled_but_payout_post_is_not(self):
        """Throttle is scoped to reads: GET consumes the PII bucket, the payout POST never does."""
        with patch("accounts.throttles.AdminPIIThrottle.allow_request", return_value=True) as allow:
            self.assertEqual(self._get().status_code, status.HTTP_200_OK)
            allow.assert_called_once()
            allow.reset_mock()
            self.assertEqual(self._post().status_code, status.HTTP_200_OK)
            allow.assert_not_called()

    def test_get_throttles_scope(self):
        view = AdminDriverEarningsView()
        view.request = SimpleNamespace(method="GET")
        self.assertIsInstance(view.get_throttles()[0], AdminPIIThrottle)
        view.request = SimpleNamespace(method="HEAD")  # HEAD is routed to get()
        self.assertIsInstance(view.get_throttles()[0], AdminPIIThrottle)
        view.request = SimpleNamespace(method="POST")
        self.assertEqual(view.get_throttles(), [])

    def test_payout_post_still_audited_as_payout(self):
        self.assertEqual(self._post().status_code, status.HTTP_200_OK)
        self.mock_log.assert_called_once()
        self.assertEqual(
            self.mock_log.call_args[1]["action"], AdminAuditLog.Actions.DRIVER_PAYOUT_RECORDED
        )


class DriverEarningsAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverEarningsView.as_view()

    def test_no_session_returns_401(self):
        req = self.factory.get("/api/driver/earnings/")
        req.session = {}
        self.assertEqual(self.view(req).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        """A signed-in customer who never applied to drive still gets the 404
        contract — the is_driver gate lives in the view, not a permission class."""
        req = self.factory.get("/api/driver/earnings/")
        req.session = {}
        force_authenticate(req, user=Customer(id=1, is_driver=False))
        self.assertEqual(self.view(req).status_code, status.HTTP_404_NOT_FOUND)
