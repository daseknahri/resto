"""
C6 — Customer self-serve data export and PII erasure REST endpoints.

Tests:
  CustomerDataExportView   GET /api/customer/my-data/
  CustomerErasureRequestView POST /api/customer/request-erasure/

House style: SimpleTestCase + MagicMock (no real DB).
"""
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerDataExportView, CustomerErasureRequestView


class DataExportAuthTests(SimpleTestCase):
    """Unauthenticated requests must be rejected."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerDataExportView.as_view()

    def test_no_session_returns_401(self):
        req = self.factory.get("/api/customer/my-data/")
        req.session = {}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_customer_returns_404(self):
        req = self.factory.get("/api/customer/my-data/")
        req.session = {"customer_id": 999}
        with patch("accounts.views.Customer.objects.get", side_effect=Exception("DoesNotExist")):
            # We need the DoesNotExist branch — use the real exception class.
            from accounts.models import Customer as RealCustomer
            with patch("accounts.views.Customer.objects.get",
                       side_effect=RealCustomer.DoesNotExist):
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class DataExportPayloadTests(SimpleTestCase):
    """Authenticated customer receives a well-formed JSON payload."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerDataExportView.as_view()

    def _make_customer(self, cid=1):
        c = MagicMock()
        c.pk = cid
        c.name = "Alice"
        c.email = "alice@example.com"
        c.phone = "+212600000001"
        c.locale = "en"
        c.birthday = None
        c.created_at.isoformat.return_value = "2025-01-01T00:00:00+00:00"
        c.wallet_balance = Decimal("50.00")
        c.loyalty_points = 200
        c.lifetime_loyalty_points = 500
        return c

    @patch("accounts.views.CustomerOrderRef")
    @patch("accounts.views.SavedAddress")
    @patch("accounts.views.WalletTransaction")
    @patch("accounts.views.Customer.objects.get")
    def test_export_returns_200_with_profile(
        self, mock_get, MockWT, MockSA, MockOR
    ):
        customer = self._make_customer()
        mock_get.return_value = customer

        MockWT.objects.filter.return_value.order_by.return_value.values.__getitem__.return_value = []
        MockWT.objects.filter.return_value.order_by.return_value.values.return_value.__getitem__ = (
            lambda self, s: []
        )

        # Simplify: mock the entire chain
        MockWT.objects.filter.return_value.order_by.return_value\
            .__getitem__ = lambda self, s: []
        wt_qs = MagicMock()
        wt_qs.__iter__ = lambda self: iter([])
        wt_qs.__len__ = lambda self: 0
        MockWT.objects.filter.return_value.order_by.return_value.values.return_value = wt_qs
        # Actually just patch the whole values() call to return []
        MockWT.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockOR.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockSA.objects.filter.return_value.values = MagicMock(return_value=[])

        req = self.factory.get("/api/customer/my-data/")
        req.session = {"customer_id": 1}
        resp = self.view(req)

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
    @patch("accounts.views.Customer.objects.get")
    def test_export_sets_content_disposition(
        self, mock_get, MockWT, MockSA, MockOR
    ):
        mock_get.return_value = self._make_customer()
        MockWT.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockOR.objects.filter.return_value.order_by.return_value.values = MagicMock(return_value=[])
        MockSA.objects.filter.return_value.values = MagicMock(return_value=[])

        req = self.factory.get("/api/customer/my-data/")
        req.session = {"customer_id": 1}
        resp = self.view(req)
        resp.accepted_renderer = MagicMock()
        resp.accepted_media_type = "application/json"
        resp.renderer_context = {}
        resp.render()
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("kepoli-data-export.json", resp["Content-Disposition"])


class ErasureAuthTests(SimpleTestCase):
    """Unauthenticated/missing customer erasure requests."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerErasureRequestView.as_view()

    def test_no_session_returns_401(self):
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_customer_returns_404(self):
        from accounts.models import Customer as RealCustomer
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {"customer_id": 999}
        with patch("accounts.views.Customer.objects.get",
                   side_effect=RealCustomer.DoesNotExist):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ErasureGuardTests(SimpleTestCase):
    """Guard-rail failures return 409 with error list."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerErasureRequestView.as_view()

    def _req(self, cid=42):
        req = self.factory.post("/api/customer/request-erasure/")
        req.session = {"customer_id": cid}
        return req

    @patch("accounts.views.Customer.objects.get")
    def test_guard_failures_return_409(self, mock_get):
        mock_get.return_value = MagicMock()
        # Patch the actual import path used by the view
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=["Customer has open orders: T1/ORD-001 (active)"],
        ):
            resp = self.view(self._req())
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("errors", resp.data)
        self.assertEqual(len(resp.data["errors"]), 1)

    @patch("accounts.views.Customer.objects.get")
    def test_guard_clear_calls_management_command(self, mock_get):
        mock_get.return_value = MagicMock()
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=[],
        ), patch("accounts.views.call_command") as mock_cmd:
            req = self._req()
            session = MagicMock()
            session.get.return_value = 42
            req.session = session
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

    @patch("accounts.views.Customer.objects.get")
    def test_session_flushed_on_success(self, mock_get):
        mock_get.return_value = MagicMock()
        with patch(
            "accounts.management.commands.erase_customer._check_guard_rails",
            return_value=[],
        ), patch("accounts.views.call_command"):
            req = self.factory.post("/api/customer/request-erasure/")
            flush_called = []
            session = MagicMock()
            session.get.return_value = 99
            session.flush = lambda: flush_called.append(True)
            req.session = session
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(flush_called, "session.flush() was not called")
