"""
Run 6 follow-on — statement ?branch= preview filter (REAL-DB tests).

The Phase-3 statement snapshot (CommissionStatement) is ACCOUNT-level by
design: it carries no branch scope, because the platform bills the account.
This suite proves the follow-on wiring honours that line:

  * GET ?branch=<id> on an UNISSUED month filters the live preview to that
    branch's orders (the branch seam is the tenant's location/outlet —
    vertical-general: identical for a restaurant, pharmacy or store).
  * GET ?branch=<id> on an ISSUED month serves the frozen account-level
    figures and reports the filter as NOT applied — never silently
    filtering frozen data.
  * POST issue with a branch is refused (400) and freezes nothing.
  * Unknown / malformed branch params fail cleanly (404 / 400).

Scaffolding mirrors test_statement_immutability.py (production
provisioning path, schema_context, mock owner) for the same reasons —
including its PDF calling convention: ?format=pdf through as_view() dies
in DRF content negotiation (no PDF renderer is registered), so the PDF
leg calls the view's get() on an initialized request, exactly like the
immutability suite does.
"""
import os
from datetime import datetime, timezone as _tz
from decimal import Decimal
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import MagicMock

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.commission_statement import get_issued_statement
from menu.models import Branch, CommissionStatement, Order
from menu.views import OwnerCommissionStatementView
from tenancy.models import Plan, Tenant

SCHEMA = "stmt_branch_filter_test"
YEAR, MONTH = 2026, 6


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
    profile = SimpleNamespace(timezone="UTC", service_day_cutover_hour=0)
    return SimpleNamespace(id=tenant_id, profile=profile)


@skipUnless(os.environ.get("PYTEST_REQUIRE_DB") == "1", "requires the DB stage")
class StatementBranchFilterTests(TransactionTestCase):
    def _fixture_teardown(self):
        # See test_statement_immutability.py — the stock TRUNCATE teardown
        # cannot run while this suite's real tenant schema exists.
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._plan = Plan.objects.create(
            name="Statement branch filter plan", code="stmt-branch-filter"
        )
        tenant = Tenant(
            schema_name=SCHEMA,
            name="Statement Branch Test Tenant",
            slug="stmt-branch-filter-test",
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
            Plan.objects.filter(code="stmt-branch-filter").delete()
        finally:
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = OwnerCommissionStatementView.as_view()
        with schema_context(SCHEMA):
            CommissionStatement.objects.all().delete()
            Order.objects.all().delete()
            Branch.objects.all().delete()
            self.main = Branch.objects.create(
                name="Main Outlet", slug="main", is_default=True
            )
            self.annex = Branch.objects.create(name="Annex", slug="annex")

    # ── fixtures ──────────────────────────────────────────────────────────

    def _order(self, number, *, total, commission, branch=None, day=15):
        with schema_context(SCHEMA):
            order = Order.objects.create(
                order_number=number,
                source=Order.Source.MARKETPLACE,
                status="completed",
                customer_name="Diner",
                total=Decimal(total),
                delivery_fee=Decimal("0.00"),
                commission_amount=Decimal(commission),
                commission_rate_applied=Decimal("0.10"),
                currency="MAD",
                branch=branch,
            )
            Order.objects.filter(pk=order.pk).update(
                created_at=datetime(2026, MONTH, day, 12, 0, tzinfo=_tz.utc)
            )
            order.refresh_from_db()
            return order

    def _seed(self):
        # main: revenue 100, commission 10 · annex: revenue 200 + 400,
        # commission 20 + 40 · unbranched: revenue 800, commission 80.
        self._order("ORD-M1", total="100.00", commission="10.00", branch=self.main)
        self._order("ORD-A1", total="200.00", commission="20.00", branch=self.annex)
        self._order("ORD-A2", total="400.00", commission="40.00", branch=self.annex)
        self._order("ORD-U1", total="800.00", commission="80.00", branch=None)

    def _get(self, params=None):
        q = {"year": str(YEAR), "month": str(MONTH)}
        q.update(params or {})
        req = self.factory.get("/api/owner/commission-statement/", q)
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            return self.view(req)

    def _post_issue(self, data=None):
        payload = {"year": YEAR, "month": MONTH}
        payload.update(data or {})
        req = self.factory.post(
            "/api/owner/commission-statement/issue/", payload, format="json"
        )
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            return self.view(req)

    # ── the proof ─────────────────────────────────────────────────────────

    def test_preview_without_branch_is_account_level(self):
        self._seed()
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("branch_filter", resp.data)
        self.assertEqual(resp.data["summary"]["total_revenue"], 1500.0)
        self.assertEqual(resp.data["summary"]["total_commission"], 150.0)
        self.assertEqual(resp.data["summary"]["order_count"], 4)

    def test_preview_with_branch_filters_to_that_branch(self):
        self._seed()
        resp = self._get(params={"branch": str(self.annex.id)})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued"], False)
        bf = resp.data["branch_filter"]
        self.assertEqual(bf["branch_id"], self.annex.id)
        self.assertEqual(bf["branch_slug"], "annex")
        self.assertEqual(bf["applied"], True)
        self.assertEqual(resp.data["summary"]["total_revenue"], 600.0)
        self.assertEqual(resp.data["summary"]["total_commission"], 60.0)
        self.assertEqual(resp.data["summary"]["order_count"], 2)
        numbers = {o["order_number"] for o in resp.data["orders"]}
        self.assertEqual(numbers, {"ORD-A1", "ORD-A2"})

    def test_preview_with_unknown_branch_is_404(self):
        self._seed()
        resp = self._get(params={"branch": "999999"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["detail"], "Branch not found.")

    def test_preview_with_malformed_branch_is_400(self):
        self._seed()
        resp = self._get(params={"branch": "not-a-branch"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_branch_filtered_preview_pdf_renders(self):
        self._seed()
        # House PDF convention (see the module docstring): initialize the
        # request and call get() directly, like the immutability suite.
        pdf_view = OwnerCommissionStatementView()
        pdf_view.format_kwarg = None
        req = self.factory.get(
            "/api/owner/commission-statement/",
            {
                "year": str(YEAR),
                "month": str(MONTH),
                "format": "pdf",
                "branch": str(self.main.id),
            },
        )
        req.user = _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            resp = pdf_view.get(pdf_view.initialize_request(req))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))

    def test_issue_with_branch_is_refused_and_freezes_nothing(self):
        self._seed()
        resp = self._post_issue(data={"branch": self.annex.id})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        with schema_context(SCHEMA):
            self.assertIsNone(get_issued_statement(YEAR, MONTH))

    def test_issued_month_reports_branch_filter_not_applied(self):
        self._seed()
        issued = self._post_issue()
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED)

        resp = self._get(params={"branch": str(self.annex.id)})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued"], True)
        # Frozen figures stay ACCOUNT-level (all four orders).
        self.assertEqual(resp.data["summary"]["total_revenue"], 1500.0)
        self.assertEqual(resp.data["summary"]["total_commission"], 150.0)
        bf = resp.data["branch_filter"]
        self.assertEqual(bf["applied"], False)
        self.assertIn("account level", bf["reason"])
