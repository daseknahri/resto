"""OPS-5h — cancel-refund idempotency + request-log secret scrubbing contract tests.

Two adjacent hardening items:

  A. [money] _refund_wallet_for_cancelled_order (menu/views.py) used to mutate
     Customer.wallet_balance DIRECTLY and guard replay by filtering WalletTransaction on
     (customer_id, type=REFUND, reference=order_number, note). order_number is only
     SCHEMA-unique, but WalletTransaction lives in the shared PUBLIC schema where the
     dedupe namespace is GLOBAL — a cross-tenant customer with a colliding order_number
     could have a legit tenant-B refund SILENTLY SKIPPED by matching a tenant-A row.
     The fix routes the refund through wallet_service.credit_wallet with a
     SCHEMA-NAMESPACED idempotency key f"cancelrefund:{schema}:{order.id}", preserving
     type=REFUND + tenant_id + reference + note for the Z-report/refund queries, and
     dropping the manual balance write entirely.

  B. [logging] RequestLoggingMiddleware logged request.get_full_path() — query string
     included — so the driver cash-out ?code= (a bearer credential) and the customer
     ?phone= (PII) leaked into app logs / Sentry breadcrumbs. The new _safe_path helper
     redacts the VALUES of a sensitive-param denylist while keeping benign params.

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

# Live test-DB schema name — the function derives the key from connection.schema_name, so
# the expected key is computed from the same source rather than hard-coded.
SCHEMA = connection.schema_name


# ═════════════════════════════════════════════════════════════════════════════
# A. Cancel-refund routes through credit_wallet with a schema-namespaced key
# ═════════════════════════════════════════════════════════════════════════════

class CancelRefundIdempotencyTests(SimpleTestCase):
    """_refund_wallet_for_cancelled_order calls credit_wallet with a schema-namespaced
    idempotency key + type=REFUND + tenant_id, and no longer writes the balance directly."""

    @staticmethod
    def _order(order_id=10, order_number="ORD-001", customer_id=42, wallet_paid="35.00"):
        o = MagicMock()
        o.id = order_id
        o.order_number = order_number
        o.customer_id = customer_id
        o.wallet_amount_paid = Decimal(wallet_paid)
        return o

    @patch("accounts.wallet_service.credit_wallet")
    def test_routes_through_credit_wallet_with_schema_namespaced_key(self, mock_cw):
        from menu.views import _refund_wallet_for_cancelled_order
        from accounts.models import WalletTransaction

        order = self._order(order_id=10, order_number="ORD-001", customer_id=42,
                            wallet_paid="35.00")
        _refund_wallet_for_cancelled_order(order, tenant_id=7)

        mock_cw.assert_called_once()
        args, kwargs = mock_cw.call_args
        # positional: customer_id, amount
        self.assertEqual(args[0], 42)
        self.assertEqual(args[1], Decimal("35.00"))

        # Schema-namespaced key keyed on the tenant-schema PK (order.id), so a
        # cross-tenant order_number collision can no longer alias another tenant's refund.
        key = kwargs["idempotency_key"]
        self.assertEqual(key, f"cancelrefund:{SCHEMA}:10")
        self.assertIn(SCHEMA, key)

        # Ledger semantics preserved for the Z-report / refund queries.
        self.assertEqual(kwargs["tx_type"], WalletTransaction.Type.REFUND)
        self.assertEqual(kwargs["tenant_id"], 7)
        self.assertEqual(kwargs["reference"], "ORD-001")
        self.assertEqual(kwargs["note"], "Refund for cancelled order")
        # A refund is system-originated, so the verified-phone gate is bypassed.
        self.assertFalse(kwargs["require_verified"])

    @patch("accounts.wallet_service.credit_wallet")
    def test_no_direct_balance_write(self, mock_cw):
        """The refund must NOT mutate Customer.wallet_balance directly anymore — all
        balance movement is delegated to credit_wallet (which locks + snapshots)."""
        from menu.views import _refund_wallet_for_cancelled_order

        order = self._order()
        with patch("accounts.models.Customer.objects") as mock_cust:
            _refund_wallet_for_cancelled_order(order, tenant_id=7)
            # The old code did Customer.objects.select_for_update().get(...).save(...);
            # the new code touches Customer ONLY through credit_wallet, so the view-level
            # Customer manager is never used directly.
            mock_cust.select_for_update.assert_not_called()
            mock_cust.get.assert_not_called()
        mock_cw.assert_called_once()

    @patch("accounts.wallet_service.credit_wallet")
    def test_no_customer_id_is_a_noop(self, mock_cw):
        from menu.views import _refund_wallet_for_cancelled_order
        order = self._order(customer_id=None)
        _refund_wallet_for_cancelled_order(order, tenant_id=7)
        mock_cw.assert_not_called()

    @patch("accounts.wallet_service.credit_wallet")
    def test_zero_wallet_paid_is_a_noop(self, mock_cw):
        from menu.views import _refund_wallet_for_cancelled_order
        order = self._order(wallet_paid="0.00")
        _refund_wallet_for_cancelled_order(order, tenant_id=7)
        mock_cw.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# B. RequestLoggingMiddleware redacts sensitive query params before logging
# ═════════════════════════════════════════════════════════════════════════════

class SafePathRedactionTests(SimpleTestCase):
    """_safe_path redacts the values of denylisted params (code/phone/token/…) while
    keeping the path and benign params intact for debuggability."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _safe_path(self, url):
        from config.middleware import RequestLoggingMiddleware
        req = self.factory.get(url)
        return RequestLoggingMiddleware._safe_path(req)

    def test_redacts_cashout_code(self):
        out = self._safe_path("/api/owner/driver-cashout/?code=123456")
        self.assertIn("code=%2A%2A%2A", out)  # urlencoded "***"
        self.assertNotIn("123456", out)
        self.assertTrue(out.startswith("/api/owner/driver-cashout/"))

    def test_redacts_phone(self):
        out = self._safe_path("/api/orders/lookup/?phone=0612345678")
        self.assertNotIn("0612345678", out)
        self.assertIn("phone=%2A%2A%2A", out)

    def test_redacts_token(self):
        out = self._safe_path("/api/x/?token=supersecret")
        self.assertNotIn("supersecret", out)
        self.assertIn("token=%2A%2A%2A", out)

    def test_keeps_benign_params(self):
        out = self._safe_path("/api/orders/?status=ready&page=2")
        self.assertIn("status=ready", out)
        self.assertIn("page=2", out)

    def test_redacts_only_the_sensitive_param_in_a_mixed_query(self):
        out = self._safe_path("/api/orders/lookup/?phone=0612345678&status=ready")
        self.assertNotIn("0612345678", out)
        self.assertIn("phone=%2A%2A%2A", out)
        self.assertIn("status=ready", out)  # benign param survives

    def test_redaction_is_case_insensitive(self):
        out = self._safe_path("/api/x/?Code=123456")
        self.assertNotIn("123456", out)

    def test_no_query_string_returns_bare_path(self):
        out = self._safe_path("/api/health/")
        self.assertEqual(out, "/api/health/")

    def test_helper_is_used_instead_of_get_full_path(self):
        """Defensive: the middleware logs _safe_path(request), not get_full_path()."""
        from config.middleware import RequestLoggingMiddleware
        import inspect
        src = inspect.getsource(RequestLoggingMiddleware.__call__)
        self.assertIn("self._safe_path(request)", src)
        self.assertNotIn("get_full_path()", src)
