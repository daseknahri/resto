"""
Tests for OwnerCustomerRatingView
POST /api/owner/orders/<order_id>/customer-rating/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerCustomerRatingView
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
    return SimpleNamespace(id=tenant_id)


def _make_order(order_id=1, order_number="ORD-001", customer_id=42):
    order = MagicMock()
    order.id = order_id
    order.order_number = order_number
    order.customer_id = customer_id
    return order


# ── Tests ─────────────────────────────────────────────────────────────────────

class OwnerCustomerRatingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCustomerRatingView.as_view()

    def _post(self, order_id, data, user=None, tenant=None):
        req = self.factory.post(
            f"/api/owner/orders/{order_id}/customer-rating/",
            data,
            format="json",
        )
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_outsider_returns_403(self):
        resp = self._post(1, {"score": 4}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Order lookup ──────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_unknown_order_returns_404(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = None
        resp = self._post(999, {"score": 4})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.Order.objects")
    def test_order_without_customer_returns_400(self, mock_order_objs):
        order = _make_order(customer_id=None)
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = order
        resp = self._post(1, {"score": 4})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_customer")

    # ── Score validation ──────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_score_zero_returns_400(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()
        resp = self._post(1, {"score": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    @patch("menu.views.Order.objects")
    def test_score_six_returns_400(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()
        resp = self._post(1, {"score": 6})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    @patch("menu.views.Order.objects")
    def test_non_integer_score_returns_400(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()
        resp = self._post(1, {"score": "great"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_score")

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_valid_rating_returns_200_with_fields(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()

        cr = MagicMock()
        cr.score = 4
        cr.note = "Reliable"
        agg = {"avg": 4.0, "cnt": 3}

        with patch("accounts.models.CustomerRating.objects") as mock_cr_objs:
            mock_cr_objs.update_or_create.return_value = (cr, True)
            mock_cr_objs.filter.return_value.aggregate.return_value = agg
            resp = self._post(1, {"score": 4, "note": "Reliable"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("score", "note", "avg_score", "rating_count"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertEqual(resp.data["score"], 4)
        self.assertEqual(resp.data["note"], "Reliable")
        self.assertEqual(resp.data["rating_count"], 3)

    @patch("menu.views.Order.objects")
    def test_note_is_optional(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()

        cr = MagicMock()
        cr.score = 5
        cr.note = ""
        agg = {"avg": 5.0, "cnt": 1}

        with patch("accounts.models.CustomerRating.objects") as mock_cr_objs:
            mock_cr_objs.update_or_create.return_value = (cr, True)
            mock_cr_objs.filter.return_value.aggregate.return_value = agg
            resp = self._post(1, {"score": 5})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.Order.objects")
    def test_avg_score_is_none_when_no_ratings(self, mock_order_objs):
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = _make_order()

        cr = MagicMock()
        cr.score = 3
        cr.note = ""
        agg = {"avg": None, "cnt": 0}

        with patch("accounts.models.CustomerRating.objects") as mock_cr_objs:
            mock_cr_objs.update_or_create.return_value = (cr, True)
            mock_cr_objs.filter.return_value.aggregate.return_value = agg
            resp = self._post(1, {"score": 3})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data["avg_score"])

    @patch("menu.views.Order.objects")
    def test_update_or_create_called_with_correct_args(self, mock_order_objs):
        order = _make_order(order_id=10, order_number="ORD-010", customer_id=7)
        mock_order_objs.select_related.return_value.filter.return_value.first.return_value = order

        cr = MagicMock()
        cr.score = 4
        cr.note = "Good"
        agg = {"avg": 4.0, "cnt": 1}

        with patch("accounts.models.CustomerRating.objects") as mock_cr_objs:
            mock_cr_objs.update_or_create.return_value = (cr, True)
            mock_cr_objs.filter.return_value.aggregate.return_value = agg
            self._post(10, {"score": 4, "note": "Good"})

        call_kwargs = mock_cr_objs.update_or_create.call_args[1]
        self.assertEqual(call_kwargs.get("customer_id"), 7)
        self.assertEqual(call_kwargs.get("order_number"), "ORD-010")
        self.assertEqual(call_kwargs["defaults"]["score"], 4)
