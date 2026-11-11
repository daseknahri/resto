"""
Phase 3 — multi-branch FIRST SLICE (REAL-DB tests).

Covers the slice end-to-end inside a real tenant schema:

  * the backfill data migration: schema creation gives every tenant a
    default branch, and migrating a pre-branch schema (menu 0077) with
    existing orders/sections forward stamps them to that default —
    and migrating back down removes the branch structures cleanly
    (both-directions proof);
  * resolve_order_branch precedence (picker slug → table's section →
    default);
  * owner branch CRUD incl. the exactly-one-default rule, the plan
    max_branches gate (D5), and PROTECT on delete-with-orders;
  * the owner order list's ?branch= filter.

Provisioning mirrors production (and the statement suite): the Tenant row
is saved with auto_create_schema=False, then create_schema() builds the
schema outside any transaction — the naive path hits MULTITENANCY-1.
Opt-in via the DB stage (PYTEST_REQUIRE_DB=1), like the other DB suites.
"""
import os
from decimal import Decimal
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import MagicMock

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework.test import APIRequestFactory

from accounts.models import User

SCHEMA = "branch_slice_test"
PRE_BRANCH_MENU = ("menu", "0077_order_estimated_ready_at")


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


def _tenant_ns(max_branches=0, tenant_id=1):
    profile = SimpleNamespace(
        timezone="UTC",
        service_day_cutover_hour=0,
        plan=SimpleNamespace(max_branches=max_branches),
    )
    return SimpleNamespace(id=tenant_id, profile=profile)


@skipUnless(os.environ.get("PYTEST_REQUIRE_DB") == "1", "requires the DB stage")
class BranchSliceTests(TransactionTestCase):
    def _fixture_teardown(self):
        # The stock TransactionTestCase teardown flush (TRUNCATE) cannot run
        # while this suite's real tenant schema exists: its tables hold
        # cross-schema FKs to public tables (menu_order -> accounts_customer)
        # and Postgres refuses to truncate a referenced table. The suite
        # cleans up after itself deterministically instead — rows deleted in
        # setUp, schema dropped in tearDownClass. (Cf. the django-tenants +
        # TransactionTestCase truncation note in test_wallet_service.py.)
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tenancy.models import Plan, Tenant

        cls._plan = Plan.objects.create(name="Branch slice plan", code="branch-slice")
        tenant = Tenant(
            schema_name=SCHEMA,
            name="Branch Test Tenant",
            slug="branch-slice-test",
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

            Plan.objects.filter(code="branch-slice").delete()
        finally:
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        with schema_context(SCHEMA):
            from menu.models import Branch, Order, TableLink, TableSection

            Order.objects.all().delete()
            TableLink.objects.all().delete()
            TableSection.objects.all().delete()
            Branch.objects.all().delete()
            Branch.objects.create(
                name="Branch Test Tenant", slug="main",
                is_default=True, is_active=True,
            )

    # ── helpers ───────────────────────────────────────────────────────────

    def _default_branch(self):
        from menu.models import Branch

        with schema_context(SCHEMA):
            return Branch.objects.get(is_default=True)

    def _make_order(self, number, branch=None, status_val="completed"):
        from menu.models import Order

        with schema_context(SCHEMA):
            return Order.objects.create(
                order_number=number,
                source=Order.Source.MARKETPLACE,
                status=status_val,
                customer_name="Branch Tester",
                total=Decimal("100.00"),
                delivery_fee=Decimal("0.00"),
                commission_amount=Decimal("10.00"),
                commission_rate_applied=Decimal("10.00"),
                currency="MAD",
                branch=branch,
            )

    # ── backfill migration ────────────────────────────────────────────────

    def test_default_branch_exists_after_provisioning(self):
        branch = self._default_branch()
        self.assertEqual(branch.slug, "main")
        self.assertEqual(branch.name, "Branch Test Tenant")
        self.assertTrue(branch.is_active)

    def test_backfill_both_directions(self):
        """Migrate the schema back to pre-branch menu 0077, create rows,
        migrate forward again: rows are stamped to the (re-created)
        default branch; the reverse pass itself must not error."""
        from django.db.migrations.executor import MigrationExecutor

        from menu.models import Branch, Order, TableSection

        with schema_context(SCHEMA):
            executor = MigrationExecutor(connection)
            executor.migrate([PRE_BRANCH_MENU])
            old_apps = executor.loader.project_state([PRE_BRANCH_MENU]).apps
            OldOrder = old_apps.get_model("menu", "Order")
            OldSection = old_apps.get_model("menu", "TableSection")
            OldOrder.objects.create(
                order_number="BR-OLD-1",
                source="marketplace",
                status="completed",
                customer_name="Legacy",
                total=Decimal("50.00"),
                commission_amount=Decimal("5.00"),
                commission_rate_applied=Decimal("10.00"),
                currency="MAD",
            )
            OldSection.objects.create(name="Legacy Hall")

            executor.loader.build_graph()
            executor.migrate(executor.loader.graph.leaf_nodes())

            default = Branch.objects.get(is_default=True)
            self.assertEqual(
                Order.objects.get(order_number="BR-OLD-1").branch_id, default.id
            )
            self.assertEqual(
                TableSection.objects.get(name="Legacy Hall").branch_id, default.id
            )

    # ── order stamping resolution ─────────────────────────────────────────

    def test_resolve_order_branch_precedence(self):
        from menu.models import Branch, TableLink, TableSection
        from menu.order_service import resolve_order_branch

        with schema_context(SCHEMA):
            default = Branch.objects.get(is_default=True)
            annex = Branch.objects.create(name="Annex", slug="annex")
            section = TableSection.objects.create(name="Annex Floor", branch=annex)
            TableLink.objects.create(label="A1", slug="a1-table", section=section)

            self.assertEqual(resolve_order_branch().id, default.id)
            self.assertEqual(
                resolve_order_branch(table_slug="a1-table").id, annex.id
            )
            self.assertEqual(
                resolve_order_branch(branch_slug="annex").id, annex.id
            )
            # Explicit slug beats the table's branch.
            TableLink.objects.create(label="M1", slug="m1-table")
            self.assertEqual(
                resolve_order_branch(
                    table_slug="a1-table", branch_slug="main"
                ).id,
                default.id,
            )
            # Unknown slug falls back to default rather than failing.
            self.assertEqual(
                resolve_order_branch(branch_slug="nope").id, default.id
            )

    # ── owner CRUD ────────────────────────────────────────────────────────

    def _call(self, view, method, path, data=None, tenant=None):
        if method == "get":
            req = self.factory.get(path)
        elif method == "post":
            req = self.factory.post(path, data or {}, format="json")
        elif method == "patch":
            req = self.factory.patch(path, data or {}, format="json")
        else:
            req = self.factory.delete(path)
        req.user = _owner()
        req.tenant = tenant or _tenant_ns()
        with schema_context(SCHEMA):
            return view(req, **({"pk": data.pop("_pk")} if data and "_pk" in data else {}))

    def test_owner_branch_crud_and_default_rule(self):
        from menu.models import Branch
        from menu.views import OwnerBranchDetailView, OwnerBranchListCreateView

        list_view = OwnerBranchListCreateView.as_view()
        detail_view = OwnerBranchDetailView.as_view()

        resp = self._call(list_view, "get", "/api/owner/branches/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)  # just the default

        resp = self._call(
            list_view, "post", "/api/owner/branches/",
            {"name": "Annex", "slug": "annex", "phone": "+212600000000"},
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        annex_id = resp.data["id"]

        resp = self._call(
            detail_view, "patch", f"/api/owner/branches/{annex_id}/",
            {"_pk": annex_id, "is_default": True},
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with schema_context(SCHEMA):
            defaults = list(Branch.objects.filter(is_default=True))
            self.assertEqual(len(defaults), 1)
            self.assertEqual(defaults[0].id, annex_id)

        # The (new) default cannot be deleted.
        resp = self._call(
            detail_view, "delete", f"/api/owner/branches/{annex_id}/",
            {"_pk": annex_id},
        )
        self.assertEqual(resp.status_code, 400)

    def test_plan_branch_limit_gate(self):
        from menu.views import OwnerBranchListCreateView

        list_view = OwnerBranchListCreateView.as_view()
        # max_branches=1 and the default branch already occupies it.
        resp = self._call(
            list_view, "post", "/api/owner/branches/",
            {"name": "Second", "slug": "second"},
            tenant=_tenant_ns(max_branches=1),
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_branch_with_orders_is_protected(self):
        from menu.models import Branch
        from menu.views import OwnerBranchDetailView

        with schema_context(SCHEMA):
            annex = Branch.objects.create(name="Annex", slug="annex")
        self._make_order("BR-PROT-1", branch=annex)
        detail_view = OwnerBranchDetailView.as_view()
        resp = self._call(
            detail_view, "delete", f"/api/owner/branches/{annex.id}/",
            {"_pk": annex.id},
        )
        self.assertEqual(resp.status_code, 400)

    # ── reports filter ────────────────────────────────────────────────────

    def test_owner_order_list_branch_filter(self):
        from menu.models import Branch
        from menu.views import OwnerOrderListView

        default = self._default_branch()
        with schema_context(SCHEMA):
            annex = Branch.objects.create(name="Annex", slug="annex")
        self._make_order("BR-LIST-MAIN", branch=default)
        self._make_order("BR-LIST-ANNEX", branch=annex)

        view = OwnerOrderListView.as_view()
        req = self.factory.get(
            "/api/owner/orders/", {"mode": "history", "branch": str(annex.id)}
        )
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            resp = view(req)
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", None))
        numbers = [row["order_number"] for row in resp.data["results"]]
        self.assertEqual(numbers, ["BR-LIST-ANNEX"])
