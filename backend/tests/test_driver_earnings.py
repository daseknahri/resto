"""Tests for driver earnings/payout views (auth paths, no DB)."""
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
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
