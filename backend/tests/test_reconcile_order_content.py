"""RISK DATA-2 residual: reconcile_order_content detects drifted public order-mirror CONTENT.

`CustomerOrderRef` (public schema) mirrors a tenant `Order`'s status/total/items_snapshot via
the `mirror_order_to_public_index` post_save signal (menu/signals.py). Unlike
`reconcile_order_refs` (RISK DATA-1, which detects a mirror whose `Order` no longer exists
at all), this command detects a mirror whose `Order` STILL exists but whose content has
drifted — a stale status, a stale total, a stale items_snapshot.

Mock-based (SimpleTestCase, no DB): the tenant loop, `tenant_context`, `transaction.atomic`,
and the `Order`/`CustomerOrderRef` managers are patched, and the reused
`mirror_order_to_public_index` signal function is called for REAL (unmocked) against those
patched managers, so the actual production recompute logic runs without a database.

`CustomerOrderRef` rows are built as real (unsaved) model instances — constructing a Django
model never touches the database, only `.save()`/queries do — so the command's generic
`_meta`-driven before/after snapshot works exactly as it does in production.
"""
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import timezone

from accounts.models import CustomerOrderRef as RealCustomerOrderRef


def _noop_cm():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class _FakeTenantContext:
    """Stand-in for django_tenants.utils.tenant_context that mirrors its one load-bearing
    effect (setting connection.tenant to the REAL tenant instance) without touching the DB."""

    def __init__(self, tenant):
        self.tenant = tenant

    def __enter__(self):
        from django.db import connection
        self._prev = getattr(connection, "tenant", None)
        connection.tenant = self.tenant
        return self.tenant

    def __exit__(self, *exc):
        from django.db import connection
        connection.tenant = self._prev
        return False


class _FakeRefQuerySet:
    def __init__(self, store, kw):
        self.store = store
        self.kw = kw

    def _matches(self):
        tid = self.kw.get("tenant_id")
        on = self.kw.get("order_number")
        out = []
        for (t, o), row in self.store.rows.items():
            if tid is not None and t != tid:
                continue
            if on is not None and o != on:
                continue
            out.append(row)
        return out

    def first(self):
        rows = self._matches()
        return rows[0] if rows else None

    def values_list(self, field, flat=False):
        tid = self.kw.get("tenant_id")
        return [o for (t, o) in self.store.rows if tid is None or t == tid]

    def update(self, **fields):
        rows = self._matches()
        for row in rows:
            for k, v in fields.items():
                setattr(row, k, v)
        return len(rows)


class _FakeRefStore:
    """In-memory stand-in for CustomerOrderRef.objects, keyed by (tenant_id, order_number)."""

    def __init__(self, rows):
        self.rows = {(r.tenant_id, r.order_number): r for r in rows}
        self.update_or_create_calls = []

    def filter(self, **kw):
        return _FakeRefQuerySet(self, kw)

    def update_or_create(self, defaults=None, **kw):
        defaults = defaults or {}
        key = (kw.get("tenant_id"), kw.get("order_number"))
        row = self.rows.get(key)
        created = False
        if row is None:
            row = RealCustomerOrderRef(tenant_id=kw.get("tenant_id"), order_number=kw.get("order_number"))
            self.rows[key] = row
            created = True
        for k, v in defaults.items():
            setattr(row, k, v)
        self.update_or_create_calls.append(key)
        return row, created


def _make_ref(**overrides):
    defaults = dict(
        id=1,
        tenant_id=1,
        order_number="ORD-1",
        customer_id=9,
        restaurant_name="Bistro",
        restaurant_slug="t1",
        status="pending",
        fulfillment_type="delivery",
        total=Decimal("30.00"),
        currency="MAD",
        order_created_at=timezone.now(),
        items_snapshot=[
            {"slug": "burger", "name": "Burger", "qty": 1, "price": 25.0},
            {"slug": "fries", "name": "Fries", "qty": 1, "price": 5.0},
        ],
        vertical="",
    )
    defaults.update(overrides)
    return RealCustomerOrderRef(**defaults)


def _make_item(slug, name, qty, price):
    item = MagicMock()
    item.dish_slug = slug
    item.dish_name = name
    item.qty = qty
    item.unit_price = price
    return item


def _make_order(order_number, *, customer_id=9, status="pending", total=Decimal("30.00"),
                 currency="MAD", fulfillment_type="delivery", created_at=None, items=None):
    order = MagicMock()
    order.order_number = order_number
    order.customer_id = customer_id
    order.status = status
    order.total = total
    order.currency = currency
    order.fulfillment_type = fulfillment_type
    order.created_at = created_at or timezone.now()
    order.items.filter.return_value = items if items is not None else []
    return order


class ReconcileOrderContentTests(SimpleTestCase):
    def _run(self, refs, orders, tenant, args=()):
        ref_store = _FakeRefStore(refs)
        CustomerOrderRefModel = SimpleNamespace(objects=ref_store)

        order_qs = MagicMock()
        order_qs.prefetch_related.return_value = orders
        OrderModel = MagicMock()
        OrderModel.objects.filter.return_value = order_qs

        TenantModel = MagicMock()
        TenantModel.objects.filter.return_value = [tenant]
        TenantModel.LifecycleStatus = SimpleNamespace(ACTIVE="active")

        out = StringIO()
        with patch("tenancy.models.Tenant", TenantModel), \
             patch("accounts.models.CustomerOrderRef", CustomerOrderRefModel), \
             patch("menu.models.Order", OrderModel), \
             patch(
                 "menu.management.commands.reconcile_order_content.tenant_context",
                 _FakeTenantContext,
             ), \
             patch(
                 "menu.management.commands.reconcile_order_content.transaction"
             ) as fake_txn:
            fake_txn.atomic.return_value = _noop_cm()
            call_command("reconcile_order_content", *args, stdout=out)
        return {"ref_store": ref_store, "out": out.getvalue()}

    def test_in_sync_mirror_left_alone(self):
        """A mirror whose stored content already matches the live order is untouched."""
        now = timezone.now()
        ref = _make_ref(
            status="confirmed",
            total=Decimal("25.00"),
            order_created_at=now,
            items_snapshot=[{"slug": "burger", "name": "Burger", "qty": 1, "price": 25.0}],
        )
        order = _make_order(
            "ORD-1",
            status="confirmed",
            total=Decimal("25.00"),
            created_at=now,
            items=[_make_item("burger", "Burger", 1, Decimal("25.00"))],
        )
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1", name="Bistro")

        ctx = self._run([ref], [order], tenant)

        self.assertIn("drifted=0", ctx["out"])
        self.assertIn("mirrors_checked=1", ctx["out"])
        # The stored mirror still reflects the same (unchanged) content.
        stored = ctx["ref_store"].rows[(1, "ORD-1")]
        self.assertEqual(stored.status, "confirmed")
        self.assertEqual(stored.total, Decimal("25.00"))
        self.assertEqual(
            stored.items_snapshot,
            [{"slug": "burger", "name": "Burger", "qty": 1, "price": 25.0}],
        )

    def test_drifted_mirror_detected_and_left_unfixed_without_flag(self):
        """Detect-only (default): drift is reported but the stored mirror is put back."""
        ref = _make_ref()  # status=pending, total=30.00, [burger, fries]
        order = _make_order(
            "ORD-1",
            status="confirmed",
            total=Decimal("25.00"),
            items=[_make_item("burger", "Burger", 1, Decimal("25.00"))],  # fries voided since
        )
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1", name="Bistro")

        ctx = self._run([ref], [order], tenant)  # no --fix

        self.assertIn("drifted=1", ctx["out"])
        self.assertIn("fixed=0", ctx["out"])
        self.assertIn("t1:ORD-1", ctx["out"])
        # Detect-only: the row is put back exactly as it was, despite the recompute run.
        stored = ctx["ref_store"].rows[(1, "ORD-1")]
        self.assertEqual(stored.status, "pending")
        self.assertEqual(stored.total, Decimal("30.00"))
        self.assertEqual(
            stored.items_snapshot,
            [
                {"slug": "burger", "name": "Burger", "qty": 1, "price": 25.0},
                {"slug": "fries", "name": "Fries", "qty": 1, "price": 5.0},
            ],
        )

    def test_drifted_mirror_fixed_with_flag(self):
        """--fix re-syncs the drifted mirror to the live order's current content."""
        ref = _make_ref()  # status=pending, total=30.00, [burger, fries]
        order = _make_order(
            "ORD-1",
            status="confirmed",
            total=Decimal("25.00"),
            items=[_make_item("burger", "Burger", 1, Decimal("25.00"))],  # fries voided since
        )
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1", name="Bistro")

        ctx = self._run([ref], [order], tenant, args=("--fix",))

        self.assertIn("drifted=1", ctx["out"])
        self.assertIn("fixed=1", ctx["out"])
        # Re-synced: the stored mirror now matches the live order.
        stored = ctx["ref_store"].rows[(1, "ORD-1")]
        self.assertEqual(stored.status, "confirmed")
        self.assertEqual(stored.total, Decimal("25.00"))
        self.assertEqual(
            stored.items_snapshot,
            [{"slug": "burger", "name": "Burger", "qty": 1, "price": 25.0}],
        )

    def test_no_mirror_no_tenant_skipped(self):
        """A tenant with zero CustomerOrderRef rows is skipped before entering its schema."""
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1", name="Bistro")
        ctx = self._run([], [], tenant)
        self.assertIn("tenants_scanned=0", ctx["out"])
        self.assertIn("mirrors_checked=0", ctx["out"])
        self.assertIn("drifted=0", ctx["out"])
