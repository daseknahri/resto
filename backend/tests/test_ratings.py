"""
Tests for the per-restaurant ratings feature.

  POST /api/orders/<order_number>/rate/   — CustomerOrderRateView
  GET  /api/owner/ratings/               — OwnerRatingListView

All tests are SimpleTestCase (no database).
The Order and Rating ORM calls are mocked.

RISK IDENTITY-1: CustomerOrderRateView now authenticates via
CustomerSessionAuthentication (it stays AllowAny — a non-owner, including an anonymous
caller, must still get the coded 403 rather than a 401), and its ownership gate is the
shared IsOrderOwner predicate reading request.user. Tests force-authenticate a real
(unsaved) Customer principal instead of hand-setting request.session.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, User
from menu.views import CustomerOrderRateView, OwnerRatingListView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _customer(pk=1):
    """A real (unsaved) Customer so it passes IsOrderOwner's principal check
    (is_authenticated + class name). No DB is touched."""
    c = Customer(id=pk)
    c.save = MagicMock()
    return c


def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 1
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tid=1, slug="demo"):
    return SimpleNamespace(id=tid, slug=slug, is_active=True)


def _completed_order(order_number="ORD-001", has_rating=False, customer_id=1):
    """Return a mock Order in 'completed' status owned by `customer_id`."""
    from menu.models import Order
    order = MagicMock()
    order.order_number = order_number
    order.status = Order.Status.COMPLETED
    order.customer_name = "Alice"
    order.customer_id = customer_id
    if has_rating:
        # hasattr(order, 'rating') → True means already rated
        order.rating = MagicMock()
    else:
        # hasattr(order, 'rating') → False means not yet rated
        del order.rating  # MagicMock deletes the attribute
    return order


def _pending_order(order_number="ORD-002", customer_id=1):
    from menu.models import Order
    order = MagicMock()
    order.order_number = order_number
    order.status = Order.Status.PENDING
    order.customer_id = customer_id
    del order.rating
    return order


# ── CustomerOrderRateView tests ────────────────────────────────────────────────

class CustomerOrderRateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderRateView.as_view()

    def _post(self, order_number, body, tenant=None, customer_id=1):
        req = self.factory.post(
            f"/api/orders/{order_number}/rate/",
            body,
            format="json",
        )
        req.tenant = tenant or _tenant()
        req.session = {}
        # OPS-5e: rating requires the signed-in customer to OWN the order; the mock
        # orders are owned by customer_id=1, so default the principal to match.
        # customer_id=None drives the anonymous case.
        if customer_id is not None:
            force_authenticate(req, user=_customer(customer_id))
        return self.view(req, order_number=order_number)

    # ── 404 ───────────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_unknown_order_returns_404(self, mock_orders):
        mock_orders.get.side_effect = __import__("menu.models", fromlist=["Order"]).Order.DoesNotExist
        resp = self._post("BAD-999", {"score": 5})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "order_not_found")

    # ── 400 — wrong order state ───────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_non_completed_order_returns_400(self, mock_orders):
        mock_orders.get.return_value = _pending_order()
        resp = self._post("ORD-002", {"score": 4})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "order_not_completed")

    @patch("menu.views.Order.objects")
    def test_already_rated_order_returns_400(self, mock_orders):
        mock_orders.get.return_value = _completed_order(has_rating=True)
        resp = self._post("ORD-001", {"score": 3})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "already_rated")

    # ── 400 — invalid score ───────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_score_zero_returns_400(self, mock_orders):
        mock_orders.get.return_value = _completed_order()
        resp = self._post("ORD-001", {"score": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    @patch("menu.views.Order.objects")
    def test_score_six_returns_400(self, mock_orders):
        mock_orders.get.return_value = _completed_order()
        resp = self._post("ORD-001", {"score": 6})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    @patch("menu.views.Order.objects")
    def test_non_integer_score_returns_400(self, mock_orders):
        mock_orders.get.return_value = _completed_order()
        resp = self._post("ORD-001", {"score": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    # ── 201 happy path ────────────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    @patch("menu.views.Order.objects")
    def test_valid_rating_returns_201(self, mock_orders, mock_ratings):
        mock_orders.get.return_value = _completed_order()
        rating = MagicMock()
        rating.score = 4
        rating.comment = "Very good!"
        rating.created_at.isoformat.return_value = "2026-01-01T12:00:00+00:00"
        mock_ratings.create.return_value = rating

        with patch("tenancy.api._bust_tenant_meta_cache"):
            resp = self._post("ORD-001", {"score": 4, "comment": "Very good!"})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["score"], 4)
        self.assertEqual(resp.data["comment"], "Very good!")
        mock_ratings.create.assert_called_once()
        _, create_kwargs = mock_ratings.create.call_args
        self.assertEqual(create_kwargs["order"], mock_orders.get.return_value)
        self.assertEqual(create_kwargs["score"], 4)
        self.assertEqual(create_kwargs["comment"], "Very good!")
        # OPS-5e / RISK IDENTITY-1: the linked customer IS the authenticated owner
        # principal (the ownership gate already proved it owns this order), so the
        # view no longer re-fetches it from the session id.
        self.assertEqual(create_kwargs["customer"].id, 1)

    @patch("menu.views.Rating.objects")
    @patch("menu.views.Order.objects")
    def test_comment_is_optional(self, mock_orders, mock_ratings):
        mock_orders.get.return_value = _completed_order()
        rating = MagicMock()
        rating.score = 5
        rating.comment = ""
        rating.created_at.isoformat.return_value = "2026-01-01T12:00:00+00:00"
        mock_ratings.create.return_value = rating

        with patch("tenancy.api._bust_tenant_meta_cache"):
            resp = self._post("ORD-001", {"score": 5})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # comment kwarg passed as empty string
        _, create_kwargs = mock_ratings.create.call_args
        self.assertEqual(create_kwargs["comment"], "")

    @patch("menu.views.Rating.objects")
    @patch("menu.views.Order.objects")
    def test_successful_rating_busts_meta_cache(self, mock_orders, mock_ratings):
        """Creating a rating must evict the TenantMeta cache."""
        mock_orders.get.return_value = _completed_order()
        rating = MagicMock()
        rating.score = 3
        rating.comment = ""
        rating.created_at.isoformat.return_value = "2026-01-01T12:00:00+00:00"
        mock_ratings.create.return_value = rating

        with patch("tenancy.api._bust_tenant_meta_cache") as mock_bust:
            self._post("ORD-001", {"score": 3}, tenant=_tenant(slug="myrestaurant"))
        mock_bust.assert_called_once_with("myrestaurant")

    @patch("menu.views.Order.objects")
    def test_non_owner_session_returns_403(self, mock_orders):
        """OPS-5e: a signed-in customer who doesn't own the order cannot rate it."""
        mock_orders.get.return_value = _completed_order(customer_id=1)
        resp = self._post("ORD-001", {"score": 5}, customer_id=2)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_order_owner")

    @patch("menu.views.Order.objects")
    def test_anonymous_returns_403_not_401(self, mock_orders):
        """RISK IDENTITY-1: the view stays AllowAny on purpose — an anonymous caller
        must still get the coded 403 (and the 404 order check must run first), not the
        401 an IsCustomer permission class would raise ahead of both."""
        mock_orders.get.return_value = _completed_order(customer_id=1)
        resp = self._post("ORD-001", {"score": 5}, customer_id=None)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_order_owner")

    @patch("menu.views.Order.objects")
    def test_unknown_order_404s_before_the_ownership_gate(self, mock_orders):
        """Ordering contract: order-existence (404) is checked before ownership (403),
        even for an anonymous caller."""
        from menu.models import Order as _O
        mock_orders.get.side_effect = _O.DoesNotExist
        resp = self._post("BAD-999", {"score": 5}, customer_id=None)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "order_not_found")


# ── OwnerRatingListView tests ─────────────────────────────────────────────────

class OwnerRatingListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRatingListView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        user = user or _owner()
        req = self.factory.get("/api/owner/ratings/", params or {})
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _mock_rating_qs(self, ratings=None):
        """Return a mock Rating queryset that yields the given list."""
        qs = MagicMock()
        qs.select_related.return_value = qs
        qs.order_by.return_value = qs
        qs.__iter__ = lambda s: iter(ratings or [])
        qs.__getitem__ = lambda s, k: (ratings or [])[k]
        return qs

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        anon = MagicMock()
        anon.is_authenticated = False
        req = self.factory.get("/api/owner/ratings/")
        req.user = anon
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Rating.objects")
    def test_cross_tenant_user_returns_403(self, mock_ratings):
        wrong_user = _owner(tenant_id=99)
        resp = self._get(user=wrong_user, tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Response shape ────────────────────────────────────────────────────────

    def _mock_qs(self, agg=None):
        """Build a Rating.objects chain mock that satisfies the paginated view."""
        qs = MagicMock()
        qs.filter.return_value = qs  # date-filter chains collapse back to same qs
        qs.aggregate.return_value = agg or {"avg": None, "total": 0}
        qs.__getitem__ = lambda s, k: []  # slicing for pagination returns []
        return qs

    @patch("menu.views.Rating.objects")
    def test_response_includes_count_average_and_ratings(self, mock_ratings):
        qs = self._mock_qs({"avg": 4.2, "total": 10})
        mock_ratings.select_related.return_value.order_by.return_value = qs

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("count", "average", "ratings", "page", "page_size", "has_more"):
            self.assertIn(key, resp.data, f"Missing key: {key}")
        self.assertEqual(resp.data["count"], 10)
        self.assertEqual(resp.data["average"], 4.2)
        self.assertFalse(resp.data["has_more"])  # 10 > 0+50 → False

    @patch("menu.views.Rating.objects")
    def test_response_with_no_ratings(self, mock_ratings):
        qs = self._mock_qs({"avg": None, "total": 0})
        mock_ratings.select_related.return_value.order_by.return_value = qs

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
        self.assertIsNone(resp.data["average"])
        self.assertEqual(resp.data["ratings"], [])
        self.assertFalse(resp.data["has_more"])

    @patch("menu.views.Rating.objects")
    def test_pagination_has_more_true(self, mock_ratings):
        qs = self._mock_qs({"avg": 3.5, "total": 20})
        mock_ratings.select_related.return_value.order_by.return_value = qs

        resp = self._get(params={"page": "1", "page_size": "10"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["page_size"], 10)
        self.assertTrue(resp.data["has_more"])  # 20 > 0+10 → True

    @patch("menu.views.Rating.objects")
    def test_invalid_from_date_returns_400(self, mock_ratings):
        resp = self._get(params={"from": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Rating.objects")
    def test_invalid_to_date_returns_400(self, mock_ratings):
        resp = self._get(params={"to": "99-99-9999"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Rating.objects")
    def test_date_filter_applied_to_queryset(self, mock_ratings):
        qs = self._mock_qs({"avg": 5.0, "total": 3})
        mock_ratings.select_related.return_value.order_by.return_value = qs

        resp = self._get(params={"from": "2026-01-01", "to": "2026-06-01"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(qs.filter.call_count, 2)  # once for from, once for to
