"""
Tests for accounts.views._complete_delivered_order — when a delivery is marked
delivered, the underlying order is closed out (completed + paid).

Unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.views import _complete_delivered_order
from menu.models import Order


def _job(order_number="ORD-1", tenant_id=1):
    return MagicMock(order_number=order_number, tenant_id=tenant_id)


def _patched_order(order):
    """Patch Tenant + schema_context + Order so the helper operates on `order`."""
    T = patch("tenancy.models.Tenant")
    SC = patch("django_tenants.utils.schema_context")
    O = patch("menu.models.Order")
    return T, SC, O


class CompleteDeliveredOrderTests(SimpleTestCase):
    def test_marks_ready_order_completed_and_paid(self):
        order = Order(status=Order.Status.READY, payment_status=Order.PaymentStatus.UNPAID, order_number="ORD-1")
        order.save = MagicMock()
        with patch("tenancy.models.Tenant") as T, \
             patch("django_tenants.utils.schema_context"), \
             patch("menu.models.Order") as O:
            T.objects.filter.return_value.first.return_value = MagicMock(schema_name="t1")
            O.objects.filter.return_value.first.return_value = order
            O.Status = Order.Status
            O.PaymentStatus = Order.PaymentStatus
            _complete_delivered_order(_job())
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertIsNotNone(order.paid_at)
        order.save.assert_called_once()

    def test_idempotent_when_already_completed_and_paid(self):
        order = Order(status=Order.Status.COMPLETED, payment_status=Order.PaymentStatus.PAID, order_number="ORD-2")
        order.save = MagicMock()
        with patch("tenancy.models.Tenant") as T, \
             patch("django_tenants.utils.schema_context"), \
             patch("menu.models.Order") as O:
            T.objects.filter.return_value.first.return_value = MagicMock(schema_name="t1")
            O.objects.filter.return_value.first.return_value = order
            O.Status = Order.Status
            O.PaymentStatus = Order.PaymentStatus
            _complete_delivered_order(_job(order_number="ORD-2"))
        order.save.assert_not_called()  # nothing to change

    # ── D G2: COD cash ledger ───────────────────────────────────────────────

    def _run_completion(self, order, collected):
        """Drive _complete_delivered_order on `order` with the payment ledger mocked
        to `collected`, and the driver-earning credit stubbed out. Returns the job."""
        job = _job(order_number=order.order_number)
        with patch("tenancy.models.Tenant") as T, \
             patch("django_tenants.utils.schema_context"), \
             patch("menu.models.Order") as O, \
             patch("menu.views._order_collected", return_value=collected), \
             patch("accounts.views._credit_driver_earnings") as credit:
            T.objects.filter.return_value.first.return_value = MagicMock(schema_name="t1")
            O.objects.filter.return_value.first.return_value = order
            O.Status = Order.Status
            O.PaymentStatus = Order.PaymentStatus
            _complete_delivered_order(job)
        return job

    def test_cod_order_records_cash_collected(self):
        """D G2: a COD order (UNPAID, nothing collected) records the full total as
        the cash the driver collected on handover."""
        from decimal import Decimal
        order = Order(status=Order.Status.READY, payment_status=Order.PaymentStatus.UNPAID,
                      order_number="ORD-1", total=Decimal("100.00"),
                      wallet_amount_paid=Decimal("0"))
        order.save = MagicMock()
        job = self._run_completion(order, Decimal("0"))
        self.assertEqual(job.cash_collected, Decimal("100.00"))
        job.save.assert_called_once_with(update_fields=["cash_collected"])

    def test_prepaid_order_records_no_cash(self):
        """A prepaid order collects no cash — the field stays 0 and no job write happens."""
        from decimal import Decimal
        order = Order(status=Order.Status.READY, payment_status=Order.PaymentStatus.PAID,
                      order_number="ORD-2", total=Decimal("100.00"),
                      wallet_amount_paid=Decimal("100.00"))
        order.save = MagicMock()
        job = self._run_completion(order, Decimal("100.00"))
        # No ledger write at all for a prepaid order (the field stays at its 0 default).
        job.save.assert_not_called()

    def test_partial_payment_records_remainder(self):
        """A split order (40 already collected) records only the 60 the driver took."""
        from decimal import Decimal
        order = Order(status=Order.Status.READY, payment_status=Order.PaymentStatus.UNPAID,
                      order_number="ORD-3", total=Decimal("100.00"),
                      wallet_amount_paid=Decimal("40.00"))
        order.save = MagicMock()
        job = self._run_completion(order, Decimal("40.00"))
        self.assertEqual(job.cash_collected, Decimal("60.00"))
        job.save.assert_called_once_with(update_fields=["cash_collected"])

    def test_missing_tenant_is_safe(self):
        with patch("tenancy.models.Tenant") as T, \
             patch("django_tenants.utils.schema_context"), \
             patch("menu.models.Order") as O:
            T.objects.filter.return_value.first.return_value = None
            _complete_delivered_order(_job())
            O.objects.filter.assert_not_called()  # bailed out before touching orders
