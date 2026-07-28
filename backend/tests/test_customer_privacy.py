"""
C6 — Customer self-serve data export and PII erasure REST endpoints.

Tests:
  CustomerDataExportView   GET /api/customer/my-data/
  CustomerErasureRequestView POST /api/customer/request-erasure/

RISK IDENTITY-1: these views now authenticate via CustomerSessionAuthentication +
IsCustomer, so the signed-in Customer arrives as request.user (previously
hand-rolled via request.session.get("customer_id") + Customer.objects.get(pk=...)).
Here we force-authenticate a real (unsaved) Customer principal, matching the
production auth path (mirrors the rewrite of test_customer_voucher_redeem.py).

House style: SimpleTestCase + MagicMock (no real DB).
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerDataExportView, CustomerErasureRequestView


def _customer(customer_id=1, **kwargs):
    """A real (unsaved) Customer so it passes IsCustomer's principal check
    (is_authenticated + class name). No DB is touched — the view never saves it."""
    return Customer(id=customer_id, **kwargs)


class DataExportAuthTests(SimpleTestCase):
    """Unauthenticated / stale-session requests must be rejected."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerDataExportView.as_view()

    def test_no_session_returns_401(self):
        req = self.factory.get("/api/customer/my-data/")
        req.session = {}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_session_returns_401(self):
        """RISK IDENTITY-1: a stale/forged customer_id now 401s at the auth layer
        (CustomerSessionAuthentication fails closed) instead of the view's own 404 —
        the sanctioned 404-to-401 carve-out."""
        req = self.factory.get("/api/customer/my-data/")
        req.session = {"customer_id": 999}
        with patch("accounts.models.Customer.objects") as mock_objs:
            mock_objs.filter.return_value.first.return_value = None
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class DataExportPayloadTests(SimpleTestCase):
    """Authenticated customer receives a well-formed JSON payload."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerDataExportView.as_view()

    def _make_customer(self, cid=1):
        return _customer(
            cid,
            name="Alice",
            email="alice@example.com",
            phone="+212600000001",
            locale="en",
            birthday=None,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            wallet_balance=Decimal("50.00"),
            loyalty_points=200,
            lifetime_loyalty_points=500,
        )

    def _req(self, customer):
        req = self.factory.get("/api/customer/my-data/")
        req.session = {"customer_id": customer.id}
        force_authenticate(req, user=customer)
        return req

    @patch("accounts.views.CustomerOrderRef")
    @patch("accounts.views.SavedAddress")
    @patch("accounts.views.WalletTransaction")
    def test_export_returns_200_with_profile(self, MockWT, MockSA, MockOR):
        customer = self._make_customer()

        MockWT.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockOR.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockSA.objects.filter.return_value.values = MagicMock(return_value=[])

        resp = self.view(self._req(customer))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("profile", data)
        self.assertIn("wallet", data)
        self.assertIn("orders", data)
        self.assertIn("loyalty", data)
        self.assertEqual(data["profile"]["name"], "Alice")
        self.assertEqual(data["profile"]["email"], "alice@example.com")
        self.assertEqual(data["wallet"]["balance"], "50.00")
        self.assertEqual(data["loyalty"]["points"], 200)

    @patch("accounts.views.CustomerOrderRef")
    @patch("accounts.views.SavedAddress")
    @patch("accounts.views.WalletTransaction")
    def test_export_sets_content_disposition(self, MockWT, MockSA, MockOR):
        customer = self._make_customer()
        MockWT.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockOR.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockSA.objects.filter.return_value.values = MagicMock(return_value=[])

        resp = self.view(self._req(customer))
        resp.accepted_renderer = MagicMock()
        resp.accepted_media_type = "application/json"
        resp.renderer_context = {}
        resp.render()
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("kepoli-data-export.json", resp["Content-Disposition"])


class ErasureAuthTests(SimpleTestCase):
    """Unauthenticated/stale-session erasure requests."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerErasureRequestView.as_view()

    def test_no_session_returns_401(self):
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_session_returns_401(self):
        """RISK IDENTITY-1: sanctioned 404-to-401 carve-out (see DataExportAuthTests)."""
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {"customer_id": 999}
        with patch("accounts.models.Customer.objects") as mock_objs:
            mock_objs.filter.return_value.first.return_value = None
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ErasureGuardTests(SimpleTestCase):
    """Guard-rail failures return 409 with error list."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerErasureRequestView.as_view()

    def _req(self, cid=42):
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {"customer_id": cid}
        force_authenticate(req, user=_customer(cid))
        return req

    def test_guard_failures_return_409(self):
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=["Customer has open orders: T1/ORD-001 (active)"],
        ):
            resp = self.view(self._req())
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("errors", resp.data)
        self.assertEqual(len(resp.data["errors"]), 1)

    def test_guard_clear_calls_management_command(self):
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=[],
        ), patch("accounts.views.call_command") as mock_cmd:
            req = self.factory.post("/api/customer/request-erasure/")
            session = MagicMock()
            session.get.return_value = 42
            req.session = session
            force_authenticate(req, user=_customer(42))
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_cmd.assert_called_once()
        call_args = mock_cmd.call_args
        self.assertEqual(call_args.args[0], "erase_customer")
        self.assertEqual(call_args.args[1], 42)


class ErasureSessionFlushTests(SimpleTestCase):
    """After successful erasure the session must be flushed."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerErasureRequestView.as_view()

    def test_session_flushed_on_success(self):
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=[],
        ), patch("accounts.views.call_command"):
            req = self.factory.post("/api/customer/request-erasure/")
            flush_called = []
            session = MagicMock()
            session.flush = lambda: flush_called.append(True)
            req.session = session
            force_authenticate(req, user=_customer(99))
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(flush_called, "session.flush() was not called")
