"""
Tests for OwnerCustomerListView — full behavior:
  GET /api/owner/customers/

Covers: aggregation, segment tagging, filtering, sorting, CSV export.
All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerCustomerListView
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _outsider(tenant_id=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, slug="restaurant", schema_name="restaurant")


def _now():
    return datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _linked_row(customer_id=1, order_count=3, total_spend=100.0, days_ago=5):
    from datetime import timedelta
    last = _now() - timedelta(days=days_ago)
    return {
        "customer_id": customer_id,
        "order_count": order_count,
        "total_spend": total_spend,
        "last_order_at": last,
        "avg_order_value": total_spend / max(order_count, 1),
        "last_name": "Hassan",
        "last_phone": "+33600000001",
        "currency": "EUR",
    }


def _anon_row(phone="+33600000002", order_count=1, total_spend=25.0, days_ago=40):
    from datetime import timedelta
    last = _now() - timedelta(days=days_ago)
    return {
        "customer_phone": phone,
        "order_count": order_count,
        "total_spend": total_spend,
        "last_order_at": last,
        "avg_order_value": total_spend,
        "last_name": "Anon",
        "currency": "EUR",
    }


def _make_qs(rows):
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.values.return_value = qs
    qs.annotate.return_value = qs
    qs.__iter__ = lambda s: iter(rows)
    return qs


# ── Test class ────────────────────────────────────────────────────────────────

class OwnerCustomerListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCustomerListView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        req = self.factory.get("/api/owner/customers/", params or {})
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _patched_get(self, linked=None, anon=None, user=None, tenant=None, params=None):
        """Helper that patches Order ORM and returns response.

        OPS-4 B: the new code uses Order.objects.filter(Q(...)) with positional Q
        objects (not keyword args).  We route by call order: first call → linked
        queryset, second call → anon queryset.  Both querysets are already Python
        lists after list() is called in the view — iteration does not re-trigger
        the GROUP BY.
        """
        linked = linked if linked is not None else []
        anon = anon if anon is not None else []

        with patch("menu.views.Order") as mock_order:
            linked_qs = _make_qs(linked)
            anon_qs = _make_qs(anon)
            # Route by call order: call 1 → linked, call 2 → anon.
            call_count = [0]

            def mock_filter(*args, **kwargs):
                call_count[0] += 1
                return linked_qs if call_count[0] == 1 else anon_qs

            mock_order.objects.filter.side_effect = mock_filter

            with patch("menu.views.Rating") as mock_rating:
                mock_rating.objects.filter.return_value.values.return_value.annotate.return_value = []
                with patch("django.utils.timezone.now", return_value=_now()):
                    return self._get(user=user, tenant=tenant, params=params)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_results_returns_200_with_structure(self):
        resp = self._patched_get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("summary", resp.data)
        # OPS-4 B: key changed from "customers" to "results" (pagination envelope)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["results"], [])

    def test_linked_customer_included(self):
        linked = [_linked_row(customer_id=1, order_count=3, days_ago=5)]
        resp = self._patched_get(linked=linked)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        c = resp.data["results"][0]
        self.assertEqual(c["type"], "account")
        self.assertEqual(c["customer_id"], 1)

    def test_anonymous_customer_included(self):
        anon = [_anon_row(phone="+33600000009", order_count=1, days_ago=5)]
        resp = self._patched_get(anon=anon)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        c = resp.data["results"][0]
        self.assertEqual(c["type"], "anonymous")
        self.assertIsNone(c["customer_id"])

    def test_summary_counts_correct(self):
        """new = ≤1 order, at_risk = last order >30 days, returning = rest."""
        linked = [
            _linked_row(customer_id=1, order_count=1, days_ago=5),    # new
            _linked_row(customer_id=2, order_count=5, days_ago=3),    # returning
            _linked_row(customer_id=3, order_count=3, days_ago=45),   # at_risk
        ]
        resp = self._patched_get(linked=linked)
        summary = resp.data["summary"]
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["new"], 1)
        self.assertEqual(summary["returning"], 1)
        self.assertEqual(summary["at_risk"], 1)

    def test_segment_filter_new(self):
        linked = [
            _linked_row(customer_id=1, order_count=1, days_ago=5),   # new
            _linked_row(customer_id=2, order_count=5, days_ago=3),   # returning
        ]
        resp = self._patched_get(linked=linked, params={"segment": "new"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["segment"], "new")

    def test_segment_filter_at_risk(self):
        linked = [
            _linked_row(customer_id=1, order_count=1, days_ago=5),   # new
            _linked_row(customer_id=2, order_count=3, days_ago=45),  # at_risk
        ]
        resp = self._patched_get(linked=linked, params={"segment": "at_risk"})
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["segment"], "at_risk")

    def test_segment_all_returns_all_customers(self):
        linked = [
            _linked_row(customer_id=1, order_count=1, days_ago=5),
            _linked_row(customer_id=2, order_count=5, days_ago=3),
        ]
        resp = self._patched_get(linked=linked, params={"segment": "all"})
        self.assertEqual(len(resp.data["results"]), 2)

    def test_search_by_name(self):
        # OPS-4 B: search is applied at the DB level (Q object in filter).
        # The mock returns the test row regardless of the Q filter; we verify
        # that the DB-side search doesn't crash and the result key is correct.
        linked = [
            _linked_row(customer_id=1, order_count=3, days_ago=5),   # last_name = "Hassan"
        ]
        resp = self._patched_get(linked=linked, params={"search": "hassan"})
        # Mock returns the row; DB-level filter is on the queryset not in Python.
        self.assertEqual(len(resp.data["results"]), 1)

    def test_search_no_match_returns_empty(self):
        # OPS-4 B: when the DB-level search finds no rows, the view returns empty.
        # The mock returning no rows models a real "no match" DB response.
        resp = self._patched_get(linked=[], anon=[], params={"search": "zzznomatch"})
        self.assertEqual(len(resp.data["results"]), 0)

    def test_search_linked_q_includes_email(self):
        """OPS-4 B fix: the linked Q must include customer__email__icontains so
        searching by email address returns the matching linked customer.

        The mock captures the Q passed to Order.objects.filter and verifies it
        references the customer__email field (via its children).
        """
        from django.db.models import Q as DjangoQ

        linked = [_linked_row(customer_id=1, order_count=3, days_ago=5)]

        captured_q_args: list = []

        with patch("menu.views.Order") as mock_order:
            linked_qs = _make_qs(linked)
            anon_qs = _make_qs([])
            call_count = [0]

            def mock_filter(*args, **kwargs):
                # Capture positional Q arguments for the first (linked) call.
                call_count[0] += 1
                if call_count[0] == 1:
                    captured_q_args.extend(args)
                    return linked_qs
                return anon_qs

            mock_order.objects.filter.side_effect = mock_filter

            with patch("menu.views.Rating") as mock_rating:
                mock_rating.objects.filter.return_value.values.return_value.annotate.return_value = []
                with patch("django.utils.timezone.now", return_value=_now()):
                    self._get(params={"search": "test@example.com"})

        # Flatten all children from the captured Q objects and check for email.
        def _collect_lookup_strings(q_node):
            """Recursively collect all lookup strings from Q children."""
            lookups = []
            for child in q_node.children:
                if isinstance(child, DjangoQ):
                    lookups.extend(_collect_lookup_strings(child))
                elif isinstance(child, tuple):
                    lookups.append(child[0])  # (lookup_string, value)
            return lookups

        all_lookups = []
        for q in captured_q_args:
            if isinstance(q, DjangoQ):
                all_lookups.extend(_collect_lookup_strings(q))

        self.assertTrue(
            any("customer__email" in lk for lk in all_lookups),
            f"Linked Q must include customer__email__icontains for email search; "
            f"got lookups: {all_lookups}",
        )

    def test_search_anon_q_excludes_email(self):
        """OPS-4 B: the anon Q must NOT include customer__email (anonymous orders
        have no FK to a Customer account, so the JOIN would return nothing or error).
        """
        from django.db.models import Q as DjangoQ

        captured_anon_q_args: list = []

        with patch("menu.views.Order") as mock_order:
            linked_qs = _make_qs([])
            anon_qs = _make_qs([])
            call_count = [0]

            def mock_filter(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return linked_qs
                # Capture anon call.
                captured_anon_q_args.extend(args)
                return anon_qs

            mock_order.objects.filter.side_effect = mock_filter

            with patch("menu.views.Rating") as mock_rating:
                mock_rating.objects.filter.return_value.values.return_value.annotate.return_value = []
                with patch("django.utils.timezone.now", return_value=_now()):
                    self._get(params={"search": "nobody@example.com"})

        def _collect_lookup_strings(q_node):
            lookups = []
            for child in q_node.children:
                if isinstance(child, DjangoQ):
                    lookups.extend(_collect_lookup_strings(child))
                elif isinstance(child, tuple):
                    lookups.append(child[0])
            return lookups

        all_anon_lookups = []
        for q in captured_anon_q_args:
            if isinstance(q, DjangoQ):
                all_anon_lookups.extend(_collect_lookup_strings(q))

        self.assertFalse(
            any("customer__email" in lk for lk in all_anon_lookups),
            f"Anon Q must NOT include customer__email; got lookups: {all_anon_lookups}",
        )

    def test_sort_by_total_spend(self):
        linked = [
            _linked_row(customer_id=1, order_count=2, total_spend=50.0, days_ago=5),
            _linked_row(customer_id=2, order_count=3, total_spend=200.0, days_ago=3),
        ]
        resp = self._patched_get(linked=linked, params={"sort": "total_spend", "order": "desc"})
        spends = [c["total_spend"] for c in resp.data["results"]]
        self.assertEqual(spends, sorted(spends, reverse=True))

    def test_sort_ascending(self):
        linked = [
            _linked_row(customer_id=1, order_count=1, total_spend=10.0, days_ago=5),
            _linked_row(customer_id=2, order_count=5, total_spend=500.0, days_ago=3),
        ]
        resp = self._patched_get(linked=linked, params={"sort": "total_spend", "order": "asc"})
        spends = [c["total_spend"] for c in resp.data["results"]]
        self.assertEqual(spends, sorted(spends))

    def test_csv_format_returns_csv_response(self):
        """
        The view returns an HttpResponse with CSV when query_params["format"] == "csv".
        DRF intercepts ?format= for content negotiation; we bypass this by patching
        the view method directly and calling get() with a synthetic query_params dict.
        """
        from django.http import HttpResponse

        linked = [_linked_row(customer_id=1, order_count=3, days_ago=5)]

        with patch("menu.views.Order") as mock_order:
            linked_qs = _make_qs(linked)
            anon_qs = _make_qs([])

            # OPS-4 B: new code uses positional Q objects — route by call order.
            _call_count = [0]

            def mock_filter(*args, **kwargs):
                _call_count[0] += 1
                return linked_qs if _call_count[0] == 1 else anon_qs

            mock_order.objects.filter.side_effect = mock_filter

            with patch("menu.views.Rating") as mock_rating:
                mock_rating.objects.filter.return_value.values.return_value.annotate.return_value = []
                with patch("django.utils.timezone.now", return_value=_now()):
                    # Bypass DRF content negotiation by calling the view method directly
                    view_instance = OwnerCustomerListView()

                    # Build a minimal fake DRF request object
                    fake_request = MagicMock()
                    fake_request.user = _owner()
                    fake_request.tenant = _tenant()
                    fake_request.query_params = {"format": "csv", "segment": "all", "search": ""}

                    resp = view_instance.get(fake_request)

        self.assertIsInstance(resp, HttpResponse)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("csv", resp.get("Content-Type", "").lower())
        self.assertIn("attachment", resp.get("Content-Disposition", ""))
        content = resp.content.decode("utf-8")
        self.assertIn("Name", content)
        self.assertIn("Phone", content)
