"""
Phase 3 — statement point-in-time immutability (REAL-DB tests).

Unlike the mock-based statement suites (test_a5followup_billing.py,
test_owner_export_views.py — which remain the no-drift proof for the live
computation), these tests run against a real tenant schema to prove the
freeze end-to-end:

  issue a month → void one order (commission recomputed to a lower value)
  and cancel another → GET (JSON and PDF) still serves the FROZEN totals,
  which now differ from the live computation.

Tenant provisioning mirrors the production path (register, Run 2): the
Tenant row is saved with auto_create_schema=False and the schema is built
by create_schema() OUTSIDE any transaction — the naive
Tenant.objects.create() path hits the MULTITENANCY-1 landmine at HEAD.
The suite is opt-in via the DB stage (PYTEST_REQUIRE_DB=1 + dev PG), like
the rest of the DB-backed runs.
"""
import os
from datetime import datetime, timezone as _tz
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import MagicMock

from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.commission_statement import compute_statement
from menu.models import CommissionStatement, Order
from menu.views import OwnerCommissionStatementView
from tenancy.models import Plan, Tenant

SCHEMA = "stmt_immutability_test"
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
    """Request scaffolding in the house mock style: the view only reads
    request.tenant.id (permission) and request.tenant.profile (timezone
    bucketing). The DB-real tenant lives behind schema_context."""
    profile = SimpleNamespace(timezone="UTC", service_day_cutover_hour=0)
    return SimpleNamespace(id=tenant_id, profile=profile)


@skipUnless(os.environ.get("PYTEST_REQUIRE_DB") == "1", "requires the DB stage")
class StatementImmutabilityTests(TransactionTestCase):
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
        # Production provisioning mechanism: row first (no schema), then the
        # schema build outside any transaction. Tenant requires name + slug
        # + plan (all NOT NULL at HEAD), so a throwaway plan comes first.
        cls._plan = Plan.objects.create(
            name="Statement immutability plan", code="stmt-immutability"
        )
        tenant = Tenant(
            schema_name=SCHEMA,
            name="Statement Test Tenant",
            slug="stmt-immutability-test",
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
            Plan.objects.filter(code="stmt-immutability").delete()
        finally:
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = OwnerCommissionStatementView.as_view()
        with schema_context(SCHEMA):
            CommissionStatement.objects.all().delete()
            Order.objects.all().delete()

    # ── fixtures ──────────────────────────────────────────────────────────

    def _order(self, number, *, total, commission, rate="0.10", currency="MAD",
               status_val="completed", delivery_fee="0.00", day=15):
        with schema_context(SCHEMA):
            order = Order.objects.create(
                order_number=number,
                source=Order.Source.MARKETPLACE,
                status=status_val,
                customer_name="Diner",
                total=Decimal(total),
                delivery_fee=Decimal(delivery_fee),
                commission_amount=Decimal(commission),
                commission_rate_applied=Decimal(rate),
                currency=currency,
            )
            # created_at is placement-stamped; pin it inside the target month.
            Order.objects.filter(pk=order.pk).update(
                created_at=datetime(2026, MONTH, day, 12, 0, tzinfo=_tz.utc)
            )
            order.refresh_from_db()
            return order

    def _get(self, user=None, params=None, fmt_json=True):
        q = {"year": str(YEAR), "month": str(MONTH)}
        if not fmt_json:
            q["format"] = "pdf"
        q.update(params or {})
        req = self.factory.get("/api/owner/commission-statement/", q)
        req.user = user or _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            return self.view(req)

    def _post_issue(self, user=None, data=None):
        payload = {"year": YEAR, "month": MONTH}
        payload.update(data or {})
        req = self.factory.post(
            "/api/owner/commission-statement/issue/", payload, format="json"
        )
        req.user = user or _owner()
        req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            return self.view(req)

    def _two_orders(self):
        # Revenue 100 + 200, commission 10 + 20 → frozen expectation:
        # revenue 300, commission 30, net 270 (delivery fees 0).
        a = self._order("ORD-A", total="100.00", commission="10.00")
        b = self._order("ORD-B", total="200.00", commission="20.00")
        return a, b

    # ── the proof ─────────────────────────────────────────────────────────

    def test_preview_is_provisional_and_live(self):
        self._two_orders()
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued"], False)
        self.assertEqual(resp.data["provisional"], True)
        self.assertEqual(resp.data["summary"]["total_revenue"], 300.0)
        self.assertEqual(resp.data["summary"]["total_commission"], 30.0)
        self.assertEqual(resp.data["summary"]["net_payout"], 270.0)

    def test_issue_then_void_and_cancel_totals_stay_frozen(self):
        a, b = self._two_orders()

        issued = self._post_issue()
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED)
        self.assertEqual(issued.data["issued"], True)
        self.assertEqual(issued.data["revision"], 1)
        self.assertEqual(issued.data["summary"]["total_commission"], 30.0)

        # Post-issue mutations that move the LIVE figures: void recomputes
        # A's commission down to 0; B is cancelled (leaves the billable set).
        with schema_context(SCHEMA):
            a.commission_amount = Decimal("0.00")
            a.save(update_fields=["commission_amount"])
            b.status = Order.Status.CANCELLED
            b.save(update_fields=["status"])
            live = compute_statement(_tenant_ns().profile, YEAR, MONTH)
        self.assertEqual(live["summary"]["total_commission"], 0.0)
        self.assertEqual(live["summary"]["order_count"], 1)

        # GET JSON: still the frozen month.
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["issued"], True)
        self.assertEqual(resp.data["provisional"], False)
        self.assertEqual(resp.data["revision"], 1)
        self.assertEqual(resp.data["summary"]["total_revenue"], 300.0)
        self.assertEqual(resp.data["summary"]["total_commission"], 30.0)
        self.assertEqual(resp.data["summary"]["net_payout"], 270.0)
        self.assertEqual(len(resp.data["orders"]), 2)

        # GET PDF: rendered from the frozen rows — frozen totals in the text.
        # Direct view invocation (the a5 suites' pattern): dispatching
        # through as_view() with ?format=pdf dies in DRF content
        # negotiation (no PDF renderer is registered) before get() runs.
        pdf_view = OwnerCommissionStatementView()
        pdf_view.format_kwarg = None
        pdf_req = self.factory.get(
            "/api/owner/commission-statement/",
            {"year": str(YEAR), "month": str(MONTH), "format": "pdf"},
        )
        pdf_req.user = _owner()
        pdf_req.tenant = _tenant_ns()
        with schema_context(SCHEMA):
            pdf_resp = pdf_view.get(pdf_view.initialize_request(pdf_req))
        self.assertEqual(pdf_resp.status_code, status.HTTP_200_OK)
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_resp.content))
        text = "".join(page.extract_text() for page in reader.pages)
        self.assertIn("MAD 30.00", text)   # frozen commission total
        self.assertIn("MAD 300.00", text)  # frozen revenue total

    def test_double_issue_409_and_reissue_creates_revision_2(self):
        a, _b = self._two_orders()
        first = self._post_issue()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        again = self._post_issue()
        self.assertEqual(again.status_code, status.HTTP_409_CONFLICT)

        no_reason = self._post_issue(data={"reissue": True})
        self.assertEqual(no_reason.status_code, status.HTTP_400_BAD_REQUEST)

        # Change live state so revision 2 differs from revision 1.
        with schema_context(SCHEMA):
            a.commission_amount = Decimal("4.00")
            a.save(update_fields=["commission_amount"])

        second = self._post_issue(data={"reissue": True, "reason": "void corrected"})
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.data["revision"], 2)
        self.assertEqual(second.data["summary"]["total_commission"], 24.0)

        with schema_context(SCHEMA):
            rev1 = CommissionStatement.objects.get(year=YEAR, month=MONTH, revision=1)
            rev2 = CommissionStatement.objects.get(year=YEAR, month=MONTH, revision=2)
        self.assertEqual(rev1.status, CommissionStatement.Status.SUPERSEDED)
        self.assertEqual(rev2.status, CommissionStatement.Status.ISSUED)
        self.assertEqual(rev2.reissue_reason, "void corrected")

        # GET serves the latest issued revision.
        resp = self._get()
        self.assertEqual(resp.data["revision"], 2)
        self.assertEqual(resp.data["summary"]["total_commission"], 24.0)

    def test_mixed_currency_month_freezes_per_currency(self):
        self._order("ORD-MAD", total="100.00", commission="10.00", currency="MAD")
        usd = self._order("ORD-USD", total="50.00", commission="7.50",
                          rate="0.15", currency="USD")
        issued = self._post_issue()
        self.assertEqual(issued.status_code, status.HTTP_201_CREATED)
        by_cur = {b["currency"]: b for b in issued.data["per_currency"]}
        self.assertEqual(by_cur["MAD"]["total_commission"], 10.0)
        self.assertEqual(by_cur["USD"]["total_commission"], 7.5)

        with schema_context(SCHEMA):
            usd.commission_amount = Decimal("0.00")
            usd.save(update_fields=["commission_amount"])

        resp = self._get()
        by_cur = {b["currency"]: b for b in resp.data["per_currency"]}
        self.assertEqual(by_cur["USD"]["total_commission"], 7.5)  # frozen
        self.assertTrue(resp.data["summary"].get("mixed_currency"))

    def test_non_owner_cannot_issue(self):
        self._two_orders()
        outsider = _owner(tenant_id=99)
        resp = self._post_issue(user=outsider)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        with schema_context(SCHEMA):
            self.assertEqual(CommissionStatement.objects.count(), 0)
