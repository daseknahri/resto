"""DATA-2: deleting a tenant order removes its public CustomerOrderRef mirror.

The mirror is created on Order post_save; before this there was no post_delete, so a
purged order left a phantom in the customer's cross-restaurant history. DB-backed
(TransactionTestCase): the receiver is exercised directly with a stubbed tenant so we
don't need a full tenant schema, while the CustomerOrderRef rows are real public-schema
rows the delete must scope correctly.
"""
import itertools
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TransactionTestCase
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


class MirrorItemsSnapshotExcludesVoidedCompedTests(SimpleTestCase):
    """RISK DATA-2: the public reorder mirror must not resurrect voided/comped items.

    Mock-only (SimpleTestCase, no DB): mirror_order_to_public_index also touches
    Profile (vertical lookup) and CustomerOrderRef (public-schema model), both
    mocked out here so the test exercises only the items_snapshot construction —
    specifically that it queries instance.items via .filter(is_voided=False,
    is_comped=False) rather than .all().
    """

    def test_items_snapshot_contains_only_the_live_item(self):
        from menu.signals import mirror_order_to_public_index

        live_item = SimpleNamespace(
            dish_slug="live-dish", dish_name="Live Dish", qty=2, unit_price=Decimal("10.00"),
        )
        # The real queryset filter is what excludes voided/comped rows; the mock
        # simply asserts the receiver asks for that filter and uses its result.
        mock_items = MagicMock()
        mock_items.filter.return_value = [live_item]

        instance = SimpleNamespace(
            customer_id=42,
            order_number="ORD-SNAP-1",
            status="placed",
            fulfillment_type="pickup",
            total=Decimal("20.00"),
            currency="MAD",
            created_at=timezone.now(),
            items=mock_items,
        )

        captured = {}

        def _fake_update_or_create(**kwargs):
            captured.update(kwargs)

        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Profile") as mock_profile:
            mock_conn.tenant = SimpleNamespace(id=777, name="Bistro", slug="bistro")
            mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = None
            mock_ref.objects.update_or_create.side_effect = _fake_update_or_create
            mirror_order_to_public_index(sender=None, instance=instance)

        mock_items.filter.assert_called_once_with(is_voided=False, is_comped=False)
        mock_items.all.assert_not_called()
        items_snapshot = captured["defaults"]["items_snapshot"]
        self.assertEqual(items_snapshot, [
            {"slug": "live-dish", "name": "Live Dish", "qty": 2, "price": 10.0},
        ])
