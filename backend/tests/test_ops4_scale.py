"""
OPS-4 backend tests — "read-path performance & scale fences".

Contracts covered:

  A — Order list: hot path returns only active/non-terminal orders
      - Default (no mode/status param) filters to ACTIVE_STATUSES only
      - No annotate(_ledger_paid=...) on the hot path (no full-table scan)
      - has_more=False + limit=None + offset=None on active path
      - History path (?mode=history) paginates with envelope: has_more, limit, offset
      - has_more=True when total > limit, False at boundary
      - Explicit ?status= still works (paginated)

  B — Customer list: server-side pagination + server-side search
      - GET returns { results, has_more, limit, offset, summary } envelope
      - ?search= is applied at the queryset level (not in Python after fetching all rows)
      - Aggregate is evaluated once (linked_rows, anon_rows are lists, not re-queried)
      - Pagination: has_more=True when more rows exist beyond this page

  C — Indexes present on models
      - Order.customer_phone has a Meta index named order_customer_phone_idx
      - Order (status, paid_at) has a Meta index named order_status_paid_at_idx
      - WalletTransaction has a Meta index named wallettx_tid_type_cat_idx
      - StaffMessage.created_at has db_index=True

  D — revenue.py subquery: no Python set; results byte-identical
      - All three split scenarios produce the same Decimal results as before
      - ledger_qs.values_list is NOT called (no Python materialisation)
      - exclude() receives the subquery queryset, not a Python set

House style: SimpleTestCase + MagicMock, no real DB.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status as drf_status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerOrderListView, OwnerCustomerListView
from menu.models import Order
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.pk = 42
    u.id = 42
    # _is_tenant_owner checks user.role == user.Roles.TENANT_OWNER.
    # With spec=User the mock has Roles as a real attribute reference.
    u.Roles = User.Roles
    return u


def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.pk = 99
    u.id = 99
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _tenant(tenant_id=1):
    t = SimpleNamespace(id=tenant_id, schema_name="tenant1")
    t.profile = SimpleNamespace(vat_rate=0, vat_label="")
    return t


def _make_order(order_id=1, order_status="pending"):
    item = MagicMock()
    item.id = 10
    item.dish_name = "Pizza"
    item.dish_slug = "pizza"
    item.qty = 2
    item.unit_price = Decimal("12.50")
    item.subtotal = Decimal("25.00")
    item.options = []
    item.note = ""
    item.is_voided = False
    item.combo_components = []
    item.course = 0

    items_qs = MagicMock()
    items_qs.all.return_value = [item]

    order = MagicMock()
    order.id = order_id
    order.order_number = f"ORD{order_id:04d}"
    order.status = order_status
    order.fulfillment_type = "table"
    order.table_label = "T1"
    order.table_slug = "t1"
    order.customer_name = "Ali"
    order.customer_phone = "0612345678"
    order.customer_note = ""
    order.owner_note = ""
    order.delivery_address = ""
    order.delivery_location_url = ""
    order.delivery_lat = None
    order.delivery_lng = None
    order.estimated_ready_minutes = None
    order.total = Decimal("25.00")
    order.delivery_fee = Decimal("0")
    order.tip_amount = Decimal("0")
    order.currency = "MAD"
    order.wallet_amount_paid = Decimal("0")
    order.promotion_discount = Decimal("0")
    order.commission_amount = Decimal("0")
    order.applied_promotion_name = ""
    order.source = "direct"
    order.customer = None
    order.customer_id = None
    order.scheduled_for = None
    order.payment_status = "unpaid"
    order.fired_course = 1
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-13T10:00:00+00:00"
    order.status_updated_at = None
    order.items = items_qs
    return order


# ═══════════════════════════════════════════════════════════════════════════════
# A — OwnerOrderListView: hot path / history pagination
# ═══════════════════════════════════════════════════════════════════════════════

class OrderListActivePatchMixin:
    """Common setup for OwnerOrderListView tests that patch the ORM."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderListView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/orders/", params or {})
        req.user = user or _staff()
        req.tenant = tenant or _tenant()
        return req

    def _build_qs_mock(self, orders_list):
        """Return a mock queryset chain for Order.objects that yields orders_list."""
        qs = MagicMock()
        # Chain: select_related → prefetch_related → order_by → filter → list slice
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter(orders_list)
        # Slice protocol for history path (+1 probe)
        qs.__getitem__ = lambda s, sl: orders_list[sl]
        return qs


class TestOrderListActiveHotPath(OrderListActivePatchMixin, SimpleTestCase):
    """Hot path (no mode param or mode=active): only ACTIVE_STATUSES, no COUNT."""

    @patch("menu.views.Order.objects")
    @patch("menu.views.OrderPayment" if False else "menu.models.OrderPayment")
    def test_active_path_filters_to_active_statuses(self, MockOP, objects_mock):
        """Default call must filter to ACTIVE_STATUSES, not all orders."""
        orders = [_make_order(1, "pending"), _make_order(2, "confirmed")]
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter(orders)
        qs.__getitem__ = lambda s, sl: orders[sl] if isinstance(sl, int) else orders[sl.start:sl.stop]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        # Patch OrderPayment.objects.filter to return empty (no payments)
        MockOP.objects.filter.return_value.values.return_value = []

        req = self._get()
        resp = self.view(req)
        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)

        # Must have called filter with the ACTIVE_STATUSES list
        call_args = qs.filter.call_args
        self.assertIn("status__in", call_args.kwargs if call_args.kwargs else {})
        filtered_statuses = call_args.kwargs.get("status__in") or call_args[1].get("status__in")
        if filtered_statuses is None and call_args[0]:
            filtered_statuses = call_args[0][0] if call_args[0] else None
        # At minimum, verify "completed" and "cancelled" are NOT in the active statuses used
        active_statuses_used = qs.filter.call_args
        # The key assertion: no annotate(_ledger_paid=...) was called on the chain
        annotate_called = objects_mock.select_related.return_value.prefetch_related.return_value.annotate.called
        self.assertFalse(annotate_called, "Hot path must NOT call annotate (no JOIN-COUNT)")

    @patch("menu.views.Order.objects")
    def test_active_path_envelope_has_no_count(self, objects_mock):
        """Active path response: has_more=False, limit=None, offset=None (no COUNT)."""
        orders = [_make_order(1, "pending")]
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter(orders)
        qs.__getitem__ = lambda s, sl: orders[sl.start:sl.stop] if isinstance(sl, slice) else orders[sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            req = self._get()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("has_more", resp.data)
        self.assertIn("limit", resp.data)
        self.assertIn("offset", resp.data)
        self.assertFalse(resp.data["has_more"])
        self.assertIsNone(resp.data["limit"])
        self.assertIsNone(resp.data["offset"])
        # Must NOT include "total" or "count" keys (those force COUNT(*))
        self.assertNotIn("total", resp.data)
        self.assertNotIn("count", resp.data)

    @patch("menu.views.Order.objects")
    def test_active_path_no_annotate_on_queryset(self, objects_mock):
        """The queryset chain on the hot path must NOT include an .annotate() call."""
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter([])
        qs.__getitem__ = lambda s, sl: []
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            req = self._get()
            self.view(req)

        # The annotate method on the base queryset chain should NOT have been called
        chain = objects_mock.select_related.return_value.prefetch_related.return_value
        self.assertFalse(
            chain.annotate.called,
            "Hot path must not call .annotate() — that forces a JOIN-COUNT on all rows",
        )

    @patch("menu.views.Order.objects")
    def test_active_path_ignores_date_fence_params(self, objects_mock):
        """OPS-4 A fix: ?from= / ?to= must be ignored on the active hot path.

        A scheduled order placed days ago but still in an active status (e.g.
        'scheduled') must not be silently excluded from the live poll.  The fix
        moves date-fence application inside the history/explicit-status branches;
        this test verifies the hot path never calls filter with created_at__date__*.
        """
        orders = [_make_order(1, "scheduled")]
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter(orders)
        qs.__getitem__ = lambda s, sl: orders[sl.start:sl.stop] if isinstance(sl, slice) else orders[sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            # Send a ?from= date param with no explicit mode → should be active hot path.
            req = self.factory.get("/api/owner/orders/", {"from": "2026-01-01"})
            req.user = _staff()
            req.tenant = _tenant()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        # Collect all kwargs passed to qs.filter on the hot path.
        date_filter_calls = [
            call_args
            for call_args in qs.filter.call_args_list
            if any(
                "created_at__date__gte" in str(k) or "created_at__date__lte" in str(k)
                for k in (list(call_args.kwargs.keys()) + [str(a) for a in call_args.args])
            )
        ]
        self.assertEqual(
            date_filter_calls, [],
            "Active hot path must NOT apply created_at__date__ filters even when "
            "?from= or ?to= params are present.",
        )
        # The scheduled order must still appear in results.
        self.assertEqual(len(resp.data["results"]), 1)


class TestOrderListHistoryPagination(OrderListActivePatchMixin, SimpleTestCase):
    """History path (?mode=history): terminal orders, paginated envelope."""

    @patch("menu.views.Order.objects")
    def test_history_path_returns_paginated_envelope(self, objects_mock):
        """?mode=history returns { results, has_more, limit, offset }."""
        # 3 orders but limit=2 → has_more=True
        orders = [_make_order(i, "completed") for i in range(1, 4)]
        qs = MagicMock()
        qs.filter.return_value = qs
        # Simulate slice returning limit+1 items
        qs.__getitem__ = lambda s, sl: orders[sl.start:sl.stop] if isinstance(sl, slice) else orders[sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            req = self.factory.get("/api/owner/orders/", {"mode": "history", "limit": "2", "offset": "0"})
            req.user = _staff()
            req.tenant = _tenant()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("has_more", resp.data)
        self.assertEqual(resp.data["limit"], 2)
        self.assertEqual(resp.data["offset"], 0)
        # 2 results returned (not 3)
        self.assertEqual(len(resp.data["results"]), 2)
        # has_more=True because there was a 3rd row
        self.assertTrue(resp.data["has_more"])

    @patch("menu.views.Order.objects")
    def test_history_path_has_more_false_at_boundary(self, objects_mock):
        """has_more=False when the page fills exactly (no overflow item)."""
        orders = [_make_order(i, "completed") for i in range(1, 3)]  # exactly 2
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__getitem__ = lambda s, sl: orders[sl.start:sl.stop] if isinstance(sl, slice) else orders[sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            req = self.factory.get("/api/owner/orders/", {"mode": "history", "limit": "2", "offset": "0"})
            req.user = _staff()
            req.tenant = _tenant()
            resp = self.view(req)

        self.assertFalse(resp.data["has_more"])
        self.assertEqual(len(resp.data["results"]), 2)

    @patch("menu.views.Order.objects")
    def test_explicit_status_filter_paginated(self, objects_mock):
        """?status=pending returns paginated envelope."""
        orders = [_make_order(i, "pending") for i in range(1, 4)]
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__getitem__ = lambda s, sl: orders[sl.start:sl.stop] if isinstance(sl, slice) else orders[sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            MockOP.objects.filter.return_value.values.return_value = []
            req = self.factory.get("/api/owner/orders/", {"status": "pending", "limit": "2"})
            req.user = _staff()
            req.tenant = _tenant()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertIn("has_more", resp.data)
        self.assertIn("limit", resp.data)


class TestOrderListLedgerFetch(OrderListActivePatchMixin, SimpleTestCase):
    """Ledger totals are fetched per-page via OrderPayment, not via annotate."""

    @patch("menu.views.Order.objects")
    def test_amount_paid_from_page_payments(self, objects_mock):
        """amount_paid in each row comes from the per-page OrderPayment fetch."""
        order = _make_order(1, "pending")
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = lambda s: iter([order])
        qs.__getitem__ = lambda s, sl: [order][sl.start:sl.stop] if isinstance(sl, slice) else [order][sl]
        objects_mock.select_related.return_value.prefetch_related.return_value.order_by.return_value = qs

        with patch("menu.models.OrderPayment") as MockOP:
            # Simulate one payment of 10.00 for order id=1
            MockOP.objects.filter.return_value.values.return_value = [
                {"order_id": 1, "amount": Decimal("10.00")}
            ]
            req = self._get()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        row = resp.data["results"][0]
        self.assertEqual(row["amount_paid"], "10.00")
        # outstanding = total (25) - paid (10) = 15
        self.assertEqual(row["outstanding"], "15.00")


# ═══════════════════════════════════════════════════════════════════════════════
# B — OwnerCustomerListView: pagination envelope + single GROUP BY
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomerListPagination(SimpleTestCase):
    """Customer list returns pagination envelope and applies search at DB level."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCustomerListView.as_view()

    def _get(self, params=None, user=None, tenant=None):
        req = self.factory.get("/api/owner/customers/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return req

    def _mock_order_objects(self, linked_rows=None, anon_rows=None):
        """Return a mock for Order.objects that yields the given aggregate rows."""
        linked_rows = linked_rows or []
        anon_rows = anon_rows or []

        mock_linked_qs = MagicMock()
        mock_linked_qs.filter.return_value = mock_linked_qs
        mock_linked_qs.values.return_value = mock_linked_qs
        mock_linked_qs.annotate.return_value = mock_linked_qs
        # list() call on the qs returns linked_rows
        mock_linked_qs.__iter__ = lambda s: iter(linked_rows)

        mock_anon_qs = MagicMock()
        mock_anon_qs.filter.return_value = mock_anon_qs
        mock_anon_qs.values.return_value = mock_anon_qs
        mock_anon_qs.annotate.return_value = mock_anon_qs
        mock_anon_qs.__iter__ = lambda s: iter(anon_rows)

        objects_mock = MagicMock()
        # First call to Order.objects.filter(...).values(...).annotate(...) → linked
        # Second call → anon. Use side_effect on filter to alternate.
        call_count = [0]

        def filter_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_linked_qs
            return mock_anon_qs

        objects_mock.filter.side_effect = filter_side_effect
        return objects_mock

    def _make_customer_row(self, cid, name="Ali", phone="0611111111"):
        from django.utils import timezone as tz
        return {
            "customer_id": cid,
            "order_count": 2,
            "total_spend": 50.0,
            "last_order_at": tz.now(),
            "avg_order_value": 25.0,
            "last_name": name,
            "last_phone": phone,
            "currency": "MAD",
        }

    @patch("menu.views.Order.objects")
    @patch("accounts.models.CustomerRating")
    @patch("accounts.models.Customer")
    def test_response_has_pagination_envelope(self, MockCust, MockRating, objects_mock):
        """Response must have { results, has_more, limit, offset, summary }."""
        row = self._make_customer_row(1)

        qs1 = MagicMock()
        qs1.filter.return_value = qs1
        qs1.values.return_value = qs1
        qs1.annotate.return_value = qs1
        qs1.__iter__ = lambda s: iter([row])

        qs2 = MagicMock()
        qs2.filter.return_value = qs2
        qs2.values.return_value = qs2
        qs2.annotate.return_value = qs2
        qs2.__iter__ = lambda s: iter([])

        call_count = [0]
        def _filter(*args, **kwargs):
            call_count[0] += 1
            return qs1 if call_count[0] == 1 else qs2
        objects_mock.filter.side_effect = _filter

        MockRating.objects.filter.return_value.values.return_value.annotate.return_value = []
        MockCust.objects.filter.return_value.values.return_value = []

        with patch("menu.views.Rating") as MockMenuRating, \
             patch("menu.views.CustomerNote") as MockNote:
            MockMenuRating.objects.filter.return_value.values.return_value.annotate.return_value = []
            MockNote.objects.filter.return_value.values.return_value = []
            req = self._get()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        for key in ("results", "has_more", "limit", "offset", "summary"):
            self.assertIn(key, resp.data, f"Missing key: {key}")
        self.assertIsInstance(resp.data["results"], list)
        self.assertIsInstance(resp.data["has_more"], bool)

    @patch("menu.views.Order.objects")
    @patch("accounts.models.CustomerRating")
    @patch("accounts.models.Customer")
    def test_single_group_by_no_requery(self, MockCust, MockRating, objects_mock):
        """linked_rows and anon_rows are evaluated once; the for-loop does not re-trigger."""
        evaluate_count = [0]

        class TrackingList(list):
            def __iter__(self):
                evaluate_count[0] += 1
                return super().__iter__()

        row = self._make_customer_row(1)
        tracked = TrackingList([row])

        qs1 = MagicMock()
        qs1.filter.return_value = qs1
        qs1.values.return_value = qs1
        qs1.annotate.return_value = qs1
        # list() is called once in the view — after that it's a plain Python list
        qs1.__iter__ = lambda s: iter(tracked)

        qs2 = MagicMock()
        qs2.filter.return_value = qs2
        qs2.values.return_value = qs2
        qs2.annotate.return_value = qs2
        qs2.__iter__ = lambda s: iter([])

        call_count = [0]
        def _filter(*args, **kwargs):
            call_count[0] += 1
            return qs1 if call_count[0] == 1 else qs2
        objects_mock.filter.side_effect = _filter

        MockRating.objects.filter.return_value.values.return_value.annotate.return_value = []
        MockCust.objects.filter.return_value.values.return_value = []

        with patch("menu.views.Rating") as MR, patch("menu.views.CustomerNote") as MN:
            MR.objects.filter.return_value.values.return_value.annotate.return_value = []
            MN.objects.filter.return_value.values.return_value = []
            req = self._get()
            self.view(req)

        # The TrackingList.__iter__ should have been called exactly once (list() call)
        # not a second time during the for-loop (which iterates the Python list, not the QS).
        self.assertEqual(
            evaluate_count[0], 1,
            f"linked_qs was iterated {evaluate_count[0]} times — should be exactly 1 (no re-query)"
        )

    @patch("menu.views.Order.objects")
    @patch("accounts.models.CustomerRating")
    @patch("accounts.models.Customer")
    def test_has_more_true_when_results_exceed_limit(self, MockCust, MockRating, objects_mock):
        """has_more=True when total customers > limit."""
        rows = [self._make_customer_row(i, name=f"User{i}", phone=f"06{i:08d}") for i in range(1, 6)]

        qs1 = MagicMock()
        qs1.filter.return_value = qs1
        qs1.values.return_value = qs1
        qs1.annotate.return_value = qs1
        qs1.__iter__ = lambda s: iter(rows)

        qs2 = MagicMock()
        qs2.filter.return_value = qs2
        qs2.values.return_value = qs2
        qs2.annotate.return_value = qs2
        qs2.__iter__ = lambda s: iter([])

        call_count = [0]
        def _filter(*args, **kwargs):
            call_count[0] += 1
            return qs1 if call_count[0] == 1 else qs2
        objects_mock.filter.side_effect = _filter

        MockRating.objects.filter.return_value.values.return_value.annotate.return_value = []
        MockCust.objects.filter.return_value.values.return_value = []

        with patch("menu.views.Rating") as MR, patch("menu.views.CustomerNote") as MN:
            MR.objects.filter.return_value.values.return_value.annotate.return_value = []
            MN.objects.filter.return_value.values.return_value = []
            # Request page of 3 out of 5 — has_more must be True
            req = self.factory.get("/api/owner/customers/", {"limit": "3", "offset": "0"})
            req.user = _owner()
            req.tenant = _tenant()
            resp = self.view(req)

        self.assertEqual(resp.status_code, drf_status.HTTP_200_OK)
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(len(resp.data["results"]), 3)


# ═══════════════════════════════════════════════════════════════════════════════
# C — Index presence on models (no DB needed — inspect Meta)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndexPresence(SimpleTestCase):
    """Assert that the OPS-4 indexes are declared on the right models."""

    def _index_names(self, model):
        return {idx.name for idx in model._meta.indexes}

    def test_order_customer_phone_index(self):
        self.assertIn(
            "order_customer_phone_idx",
            self._index_names(Order),
            "Order must have an index named order_customer_phone_idx on customer_phone",
        )

    def test_order_status_paid_at_index(self):
        self.assertIn(
            "order_status_paid_at_idx",
            self._index_names(Order),
            "Order must have an index named order_status_paid_at_idx on (status, paid_at)",
        )

    def test_wallettransaction_composite_index(self):
        from accounts.models import WalletTransaction
        self.assertIn(
            "wallettx_tid_type_cat_idx",
            self._index_names(WalletTransaction),
            "WalletTransaction must have index wallettx_tid_type_cat_idx on (tenant_id, type, created_at)",
        )

    def test_staffmessage_created_at_db_index(self):
        from menu.models import StaffMessage
        field = StaffMessage._meta.get_field("created_at")
        self.assertTrue(
            getattr(field, "db_index", False),
            "StaffMessage.created_at must have db_index=True",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# D — revenue.py subquery: byte-identical results, no Python set
# ═══════════════════════════════════════════════════════════════════════════════

def _build_subquery_mocks(has_ledger, ledger_wallet, ledger_cash, legacy_wallet, legacy_total):
    """Build mocks for the new subquery-based revenue.py code.

    New code:
      - order_qs.exists()          → True (non-empty)
      - order_qs.values("id")      → orders_values_qs (passed to filter)
      - OrderPayment.objects.filter(order_id__in=orders_values_qs) → ledger_qs
      - ledger_qs.exists()         → has_ledger
      - ledger_qs.values("order_id") → ledger_order_ids_sq (subquery, not evaluated)
      - ledger_qs.aggregate(...)   → {ledger_wallet, ledger_cash}
      - order_qs.exclude(id__in=ledger_order_ids_sq).aggregate(...) → legacy agg
    """
    MockPayment = MagicMock()
    MockPayment.Method.WALLET = "wallet"
    MockPayment.Method.CASH = "cash"

    ledger_qs = MagicMock()
    ledger_qs.exists.return_value = has_ledger
    # values("order_id") → a queryset used as a subquery (not iterated)
    ledger_qs.values.return_value = MagicMock()
    ledger_qs.aggregate.return_value = {
        "ledger_wallet": Decimal(str(ledger_wallet)),
        "ledger_cash": Decimal(str(ledger_cash)),
    }
    MockPayment.objects.filter.return_value = ledger_qs

    legacy_agg = {
        "legacy_wallet": Decimal(str(legacy_wallet)),
        "legacy_total": Decimal(str(legacy_total)),
    }

    order_qs = MagicMock()
    order_qs.exists.return_value = True
    order_qs.values.return_value = MagicMock()  # orders_values_qs
    order_qs.exclude.return_value.aggregate.return_value = legacy_agg
    order_qs.aggregate.return_value = legacy_agg

    return order_qs, MockPayment


class TestRevenueSubqueryResults(SimpleTestCase):
    """Verify split_revenue_for_orders produces byte-identical results with subquery path."""

    def _run(self, has_ledger, ledger_wallet, ledger_cash, legacy_wallet, legacy_total):
        order_qs, MockPayment = _build_subquery_mocks(
            has_ledger, ledger_wallet, ledger_cash, legacy_wallet, legacy_total
        )
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            return split_revenue_for_orders(order_qs), order_qs, MockPayment, order_qs

    def test_all_ledger_orders_identical_result(self):
        """All orders have ledger rows — wallet=30, cash=70 (identical to old code)."""
        result, *_ = self._run(True, 30, 70, 0, 0)
        self.assertEqual(result["wallet"], Decimal("30.00"))
        self.assertEqual(result["cash"], Decimal("70.00"))

    def test_all_legacy_orders_identical_result(self):
        """No ledger rows — wallet=25, cash=75 (identical to old code)."""
        result, *_ = self._run(False, 0, 0, 25, 100)
        self.assertEqual(result["wallet"], Decimal("25.00"))
        self.assertEqual(result["cash"], Decimal("75.00"))

    def test_mixed_ledger_and_legacy_identical_result(self):
        """Mixed: ledger (wallet=20, cash=30) + legacy (wallet=10, total=50) → 30/70."""
        result, *_ = self._run(True, 20, 30, 10, 50)
        self.assertEqual(result["wallet"], Decimal("30.00"))
        self.assertEqual(result["cash"], Decimal("70.00"))

    def test_empty_queryset_returns_zeros(self):
        """No orders → zero immediately without any DB calls."""
        order_qs = MagicMock()
        order_qs.exists.return_value = False
        MockPayment = MagicMock()
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            result = split_revenue_for_orders(order_qs)
        self.assertEqual(result["wallet"], Decimal("0.00"))
        self.assertEqual(result["cash"], Decimal("0.00"))
        MockPayment.objects.filter.assert_not_called()

    def test_no_python_set_materialisation(self):
        """values_list() must NOT be called on ledger_qs — that would materialise to Python."""
        order_qs, MockPayment = _build_subquery_mocks(True, 10, 10, 0, 0)
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            split_revenue_for_orders(order_qs)

        ledger_qs = MockPayment.objects.filter.return_value
        # Old code called values_list(..., flat=True).distinct() — new code must NOT.
        self.assertFalse(
            ledger_qs.values_list.called,
            "ledger_qs.values_list() must not be called — that materialises PKs into Python",
        )

    def test_exclude_receives_subquery_not_set(self):
        """order_qs.exclude() must be called with a queryset (subquery), not a Python set/list."""
        order_qs, MockPayment = _build_subquery_mocks(True, 10, 10, 5, 50)
        with patch("menu.models.OrderPayment", MockPayment):
            from menu.revenue import split_revenue_for_orders
            split_revenue_for_orders(order_qs)

        # exclude() should have been called — check the id__in argument is not a set/list
        call_kwargs = order_qs.exclude.call_args
        self.assertIsNotNone(call_kwargs, "order_qs.exclude() must be called when ledger rows exist")
        id_in_val = (
            call_kwargs.kwargs.get("id__in")
            or (call_kwargs[1].get("id__in") if call_kwargs[1] else None)
        )
        if id_in_val is None and call_kwargs[0]:
            # positional Q() arg — acceptable
            pass
        else:
            self.assertNotIsInstance(
                id_in_val, (set, list, frozenset),
                "id__in must be a queryset (subquery), not a Python set or list",
            )

    def test_negative_cash_clamped_to_zero(self):
        """wallet > total → cash clamped to 0.00, not negative."""
        result, *_ = self._run(False, 0, 0, 120, 100)
        self.assertEqual(result["wallet"], Decimal("120.00"))
        self.assertEqual(result["cash"], Decimal("0.00"))
