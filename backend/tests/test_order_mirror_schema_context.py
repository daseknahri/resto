"""Flywheel fix: the public order-index mirror must fire from schema_context paths too.

`mirror_order_to_public_index` / `remove_order_from_public_index` (menu/signals.py) attribute
a tenant Order to the public `CustomerOrderRef` — the cross-restaurant "My Orders" / "Order
again" history. They need the REAL `Tenant` row's id/name/slug. On the tenant-storefront
request path the middleware puts a real `Tenant` on `connection.tenant`; but a signed-in
customer's MARKETPLACE order (and driver pickup/complete, and the scheduled-order release
cron) saves the Order inside `django_tenants` `schema_context`, which only puts a bare
`FakeTenant(schema_name=...)` (no `.id`) on the connection. Historically the signal saw the
missing id and silently no-oped, so those orders never reached the customer's cross-restaurant
history — the latent flywheel bug.

The fix resolves the real `Tenant` by the active schema name when `connection.tenant` has no
id. These tests pin that behaviour.

Mock-only (SimpleTestCase, no DB): `connection`, `Tenant`, `Profile` and `CustomerOrderRef`
are patched so only tenant-resolution + the update_or_create / delete call is exercised — the
same style as test_order_mirror_delete.py, so they run without a Postgres connection.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone


def _order_instance(order_number="ORD-MKT-1"):
    """A minimal Order stand-in: customer-linked, no line items (items_snapshot → [])."""
    return SimpleNamespace(
        customer_id=42,
        order_number=order_number,
        status="pending",
        fulfillment_type="delivery",
        total=Decimal("75.00"),
        currency="MAD",
        created_at=timezone.now(),
        items=SimpleNamespace(filter=lambda **kw: []),
    )


class MirrorResolvesTenantUnderSchemaContextTests(SimpleTestCase):
    def test_fake_tenant_resolves_by_schema_name_and_mirrors(self):
        """The core regression: a signed-in customer's marketplace order (saved under a
        schema_context, so connection.tenant is a FakeTenant with no id) is mirrored to
        CustomerOrderRef under the resolved (tenant_id, order_number) with the right
        restaurant name/slug."""
        from menu.signals import mirror_order_to_public_index

        instance = _order_instance()
        captured = {}
        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Tenant") as mock_tenant, \
                patch("tenancy.models.Profile") as mock_profile:
            # schema_context path: only a FakeTenant with a schema_name, no .id.
            mock_conn.tenant = SimpleNamespace(schema_name="bistro")
            mock_conn.schema_name = "bistro"
            mock_tenant.objects.filter.return_value.values.return_value.first.return_value = {
                "id": 777, "name": "Bistro", "slug": "bistro",
            }
            mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = None
            mock_ref.objects.update_or_create.side_effect = lambda **kw: captured.update(kw)

            mirror_order_to_public_index(sender=None, instance=instance)

        # Resolved the real Tenant by the active schema name...
        mock_tenant.objects.filter.assert_called_once_with(schema_name="bistro")
        # ...and mirrored the order under it.
        self.assertEqual(captured["tenant_id"], 777)
        self.assertEqual(captured["order_number"], "ORD-MKT-1")
        self.assertEqual(captured["defaults"]["restaurant_name"], "Bistro")
        self.assertEqual(captured["defaults"]["restaurant_slug"], "bistro")
        self.assertEqual(captured["defaults"]["customer_id"], 42)

    def test_real_tenant_on_connection_skips_tenant_lookup(self):
        """Hot path unchanged: when a real Tenant is already on the connection (storefront
        request), the mirror uses it directly and does NOT run the schema→Tenant query."""
        from menu.signals import mirror_order_to_public_index

        instance = _order_instance()
        captured = {}
        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Tenant") as mock_tenant, \
                patch("tenancy.models.Profile") as mock_profile:
            mock_conn.tenant = SimpleNamespace(
                id=777, name="Bistro", slug="bistro", schema_name="bistro",
            )
            mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = None
            mock_ref.objects.update_or_create.side_effect = lambda **kw: captured.update(kw)

            mirror_order_to_public_index(sender=None, instance=instance)

        mock_tenant.objects.filter.assert_not_called()
        self.assertEqual(captured["tenant_id"], 777)
        self.assertEqual(captured["defaults"]["restaurant_name"], "Bistro")
        self.assertEqual(captured["defaults"]["restaurant_slug"], "bistro")

    def test_unknown_schema_does_not_mirror(self):
        """A schema with no matching Tenant row resolves to None → no mirror written."""
        from menu.signals import mirror_order_to_public_index

        instance = _order_instance()
        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Tenant") as mock_tenant, \
                patch("tenancy.models.Profile"):
            mock_conn.tenant = SimpleNamespace(schema_name="ghost")
            mock_conn.schema_name = "ghost"
            mock_tenant.objects.filter.return_value.values.return_value.first.return_value = None

            mirror_order_to_public_index(sender=None, instance=instance)

        mock_ref.objects.update_or_create.assert_not_called()

    def test_public_schema_skips_lookup_and_does_not_mirror(self):
        """On the public schema there is no tenant order to attribute — no Tenant lookup,
        no mirror (avoids a doomed query)."""
        from menu.signals import mirror_order_to_public_index

        instance = _order_instance()
        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Tenant") as mock_tenant, \
                patch("tenancy.models.Profile"), \
                patch("django_tenants.utils.get_public_schema_name", return_value="public"):
            mock_conn.tenant = SimpleNamespace(schema_name="public")
            mock_conn.schema_name = "public"

            mirror_order_to_public_index(sender=None, instance=instance)

        mock_tenant.objects.filter.assert_not_called()
        mock_ref.objects.update_or_create.assert_not_called()


class RemoveMirrorResolvesTenantUnderSchemaContextTests(SimpleTestCase):
    def test_fake_tenant_resolves_by_schema_name_and_deletes(self):
        """The delete twin resolves the tenant the same way, so a hard-delete on a
        schema_context path removes the right CustomerOrderRef instead of orphaning it."""
        from menu.signals import remove_order_from_public_index

        instance = SimpleNamespace(customer_id=42, order_number="ORD-MKT-DEL")
        with patch("menu.signals.connection") as mock_conn, \
                patch("accounts.models.CustomerOrderRef") as mock_ref, \
                patch("tenancy.models.Tenant") as mock_tenant:
            mock_conn.tenant = SimpleNamespace(schema_name="bistro")
            mock_conn.schema_name = "bistro"
            mock_tenant.objects.filter.return_value.values.return_value.first.return_value = {
                "id": 777, "name": "Bistro", "slug": "bistro",
            }

            remove_order_from_public_index(sender=None, instance=instance)

        mock_tenant.objects.filter.assert_called_once_with(schema_name="bistro")
        mock_ref.objects.filter.assert_called_once_with(tenant_id=777, order_number="ORD-MKT-DEL")
        mock_ref.objects.filter.return_value.delete.assert_called_once()
