"""
Tests for the per-restaurant ratings feature.

  POST /api/orders/<order_number>/rate/   — CustomerOrderRateView
  GET  /api/owner/ratings/               — OwnerRatingListView

All tests are SimpleTestCase (no database).
The Order and Rating ORM calls are mocked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import CustomerOrderRateView, OwnerRatingListView


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _completed_order(order_number="ORD-001", has_rating=False):
    """Return a mock Order in 'completed' status."""
    from menu.models import Order
    order = MagicMock()
    order.order_number = order_number
    order.status = Order.Status.COMPLETED
    order.customer_name = "Alice"
    if has_rating:
        # hasattr(order, 'rating') → True means already rated
        order.rating = MagicMock()
    else:
        # hasattr(order, 'rating') → False means not yet rated
        del order.rating  # MagicMock deletes the attribute
    return order


def _pending_order(order_number="ORD-002"):
    from menu.models import Order
    order = MagicMock()
    order.order_number = order_number
    order.status = Order.Status.PENDING
    del order.rating
    return order


# ── CustomerOrderRateView tests ────────────────────────────────────────────────

class CustomerOrderRateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrderRateView.as_view()

    def _post(self, order_number, body, tenant=None):
        req = self.factory.post(
            f"/api/orders/{order_number}/rate/",
            body,
            format="json",
        )
        req.user = MagicMock(is_authenticated=False)
        req.tenant = tenant or _tenant()
        req.session = {}
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
        mock_ratings.create.assert_called_once_with(
            order=mock_orders.get.return_value,
            score=4,
            comment="Very good!",
            customer=None,
        )

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

    @patch("menu.views.Rating.objects")
    def test_response_includes_count_average_and_ratings(self, mock_ratings):
        mock_ratings.select_related.return_value.order_by.return_value = []
        mock_ratings.aggregate.return_value = {"avg": 4.2, "total": 10}

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("count", "average", "ratings"):
            self.assertIn(key, resp.data, f"Missing key: {key}")
        self.assertEqual(resp.data["count"], 10)
        self.assertEqual(resp.data["average"], 4.2)

    @patch("menu.views.Rating.objects")
    def test_response_with_no_ratings(self, mock_ratings):
        mock_ratings.select_related.return_value.order_by.return_value = []
        mock_ratings.aggregate.return_value = {"avg": None, "total": 0}

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)
        self.assertIsNone(resp.data["average"])
        self.assertEqual(resp.data["ratings"], [])
