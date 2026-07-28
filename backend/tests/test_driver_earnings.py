"""Tests for driver earnings/payout views (auth paths, no DB).

RISK IDENTITY-1: DriverEarningsView now authenticates via CustomerSessionAuthentication
+ IsCustomer; the is_driver gate stays in the view, so its 404 contract is unchanged.
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, User
from accounts.views import AdminDriverEarningsView, DriverEarningsView


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
