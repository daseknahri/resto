"""DATA-2: deleting a tenant order removes its public CustomerOrderRef mirror.

The mirror is created on Order post_save; before this there was no post_delete, so a
purged order left a phantom in the customer's cross-restaurant history. DB-backed
(TransactionTestCase): the receiver is exercised directly with a stubbed tenant so we
don't need a full tenant schema, while the CustomerOrderRef rows are real public-schema
rows the delete must scope correctly.
"""
import itertools
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone

_phone_seq = itertools.count(600800010)


def _uphone():
    return "+212" + str(next(_phone_seq))


class RemoveOrderFromPublicIndexTests(TransactionTestCase):
    def _customer(self):
        from accounts.models import Customer
        return Customer.objects.create(name="Ref Cust", phone=_uphone(), phone_verified=True)

    def _ref(self, customer, tenant_id, order_number):
        from accounts.models import CustomerOrderRef
        return CustomerOrderRef.objects.create(
            customer=customer, tenant_id=tenant_id, order_number=order_number,
            order_created_at=timezone.now(),
        )

    def test_receiver_registered_for_order_post_delete(self):
        # Catches a wrong sender string (e.g. "menu.Orders") — nothing else listens to
        # Order post_delete, so a live listener means our receiver is wired.
        from django.db.models.signals import post_delete
        from menu.models import Order
        self.assertTrue(post_delete.has_listeners(Order))

    def test_delete_removes_matching_mirror_only(self):
        from accounts.models import CustomerOrderRef
        from menu.signals import remove_order_from_public_index
        cust = self._customer()
        target = self._ref(cust, 777, "ORD-DEL-1")
        keep_other_tenant = self._ref(cust, 888, "ORD-DEL-1")   # same order#, different tenant
        keep_other_order = self._ref(cust, 777, "ORD-KEEP")
        instance = SimpleNamespace(customer_id=cust.id, order_number="ORD-DEL-1")
        with patch("menu.signals.connection") as mock_conn:
            mock_conn.tenant = SimpleNamespace(id=777)
            remove_order_from_public_index(sender=None, instance=instance)
        self.assertFalse(CustomerOrderRef.objects.filter(pk=target.pk).exists())
        self.assertTrue(CustomerOrderRef.objects.filter(pk=keep_other_tenant.pk).exists())
        self.assertTrue(CustomerOrderRef.objects.filter(pk=keep_other_order.pk).exists())

    def test_no_customer_is_a_noop(self):
        from accounts.models import CustomerOrderRef
        from menu.signals import remove_order_from_public_index
        cust = self._customer()
        ref = self._ref(cust, 777, "ORD-DEL-2")
        instance = SimpleNamespace(customer_id=None, order_number="ORD-DEL-2")
        with patch("menu.signals.connection") as mock_conn:
            mock_conn.tenant = SimpleNamespace(id=777)
            remove_order_from_public_index(sender=None, instance=instance)
        self.assertTrue(CustomerOrderRef.objects.filter(pk=ref.pk).exists())  # untouched
