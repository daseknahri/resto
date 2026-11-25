"""POS-UX-42/47 — per-table open-order counts on the /tables/ list (REAL-DB).

Covers the backend half end-to-end inside a real tenant schema:
  * the list payload carries open_orders per table (open = non-terminal
    statuses: scheduled/pending/confirmed/preparing/ready/out_for_delivery);
  * completed/cancelled orders and orders for other tables (or no table)
    do not count;
  * a create response still serializes open_orders: 0 (serializer default).

Provisioning mirrors test_branch_slice.py: the Tenant row is saved with
auto_create_schema=False, then create_schema() builds the schema outside any
transaction. Postgres-only, gated on _dbprobe like the MFA B tests — the
unittest skipUnless guard runs AFTER pytest-django's DB setup, so it errors
locally instead of skipping; the pytest.mark.skipif guard skips first.
"""
import pytest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory

import _dbprobe
from accounts.models import User

_DB_AVAILABLE = _dbprobe.db_available()

SCHEMA = "table_open_orders_test"


def _owner(tenant_id=1, user_id=42):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.id = user_id
    return u


def _tenant_ns(tenant_id=1):
    return SimpleNamespace(id=tenant_id, profile=SimpleNamespace(timezone="UTC"))


class TableLinkOpenOrdersSerializerTests(SimpleTestCase):
    """The serializer field exists and defaults to 0 on a fresh instance."""

    def test_unannotated_instance_serializes_open_orders_zero(self):
        from menu.models import TableLink
        from menu.serializers import TableLinkSerializer

        data = TableLinkSerializer(TableLink(label="T1", slug="t1")).data
        self.assertEqual(data["open_orders"], 0)

    def test_annotated_value_passes_through(self):
        from menu.models import TableLink
        from menu.serializers import TableLinkSerializer

        table = TableLink(label="T1", slug="t1")
        table.open_orders = 3
        self.assertEqual(TableLinkSerializer(table).data["open_orders"], 3)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class TableOpenOrdersTests(TransactionTestCase):
    def _fixture_teardown(self):
        # Same reason as test_branch_slice.py: the stock flush cannot run
        # while this suite's real tenant schema exists (cross-schema FKs).
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tenancy.models import Plan, Tenant

        cls._plan = Plan.objects.create(name="Table open-orders plan", code="table-open-orders")
        tenant = Tenant(
            schema_name=SCHEMA,
            name="Table Open Orders Tenant",
            slug="table-open-orders-test",
            plan=cls._plan,
        )
        tenant.auto_create_schema = False
        tenant.save()
        tenant.create_schema(check_if_exists=True, verbosity=0)
        cls.tenant_row = tenant

    @classmethod
    def tearDownClass(cls):
        try:
            with connection.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
            cls.tenant_row.delete()
            from tenancy.models import Plan

            Plan.objects.filter(code="table-open-orders").delete()
        finally:
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        with schema_context(SCHEMA):
            from menu.models import Branch, Order, TableLink

            Order.objects.all().delete()
            TableLink.objects.all().delete()
            Branch.objects.all().delete()
            Branch.objects.create(
                name="Table Open Orders Tenant", slug="main",
                is_default=True, is_active=True,
            )

    def _make_table(self, label, slug):
        from menu.models import TableLink

        with schema_context(SCHEMA):
            return TableLink.objects.create(label=label, slug=slug, is_active=True, position=0)

    def _make_order(self, number, table_slug="", status_val="pending"):
        from menu.models import Order

        with schema_context(SCHEMA):
            return Order.objects.create(
                order_number=number,
                source=Order.Source.MARKETPLACE,
                status=status_val,
                table_slug=table_slug,
                customer_name="Table Tester",
                total=Decimal("50.00"),
                delivery_fee=Decimal("0.00"),
                commission_amount=Decimal("5.00"),
                commission_rate_applied=Decimal("10.00"),
                currency="MAD",
            )

    def _call_list(self):
        from menu.views import TableLinkViewSet

        view = TableLinkViewSet.as_view({"get": "list"})
        req = self.factory.get("/api/tables/")
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            return view(req)

    def test_list_carries_open_orders_per_table(self):
        self._make_table("Table 1", "t1")
        self._make_table("Table 2", "t2")
        # T1: 2 open (pending + preparing); completed/cancelled do not count.
        self._make_order("TO-OPEN-1", table_slug="t1", status_val="pending")
        self._make_order("TO-OPEN-2", table_slug="t1", status_val="preparing")
        self._make_order("TO-DONE-1", table_slug="t1", status_val="completed")
        self._make_order("TO-CANC-1", table_slug="t1", status_val="cancelled")
        # T2: 1 open (ready); an order for another slug and a slug-less
        # order must not leak into any table's count.
        self._make_order("TO-OPEN-3", table_slug="t2", status_val="ready")
        self._make_order("TO-OTHER-1", table_slug="t9", status_val="pending")
        self._make_order("TO-NOSLUG-1", table_slug="", status_val="pending")

        resp = self._call_list()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        by_slug = {row["slug"]: row for row in resp.data}
        self.assertEqual(by_slug["t1"]["open_orders"], 2)
        self.assertEqual(by_slug["t2"]["open_orders"], 1)

    def test_create_response_serializes_open_orders_zero(self):
        from menu.views import TableLinkViewSet

        view = TableLinkViewSet.as_view({"post": "create"})
        req = self.factory.post("/api/tables/", {"label": "Table 3", "position": 0}, format="json")
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            resp = view(req)
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", None))
        self.assertEqual(resp.data["open_orders"], 0)
