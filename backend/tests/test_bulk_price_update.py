"""
Tests for DishBulkPriceUpdateView.

  PATCH /api/owner/dishes/bulk-price/

All tests are SimpleTestCase (no database).
ORM calls are mocked so the suite runs without Postgres.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import DishBulkPriceUpdateView


# ── Helpers ────────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 10
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.effective_perm_edit_menu.return_value = True
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock(spec=User)
    u.is_authenticated = False
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, slug="demo")


def _make_dish(pk=1, name="Tagine", price="50.00"):
    d = MagicMock()
    d.id = pk
    d.pk = pk
    d.name = name
    d.price = Decimal(price)
    d.is_published = True
    return d


# ── Test class ─────────────────────────────────────────────────────────────────

class DishBulkPriceUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DishBulkPriceUpdateView.as_view()

    def _patch(self, body=None, user=None, tenant=None):
        req = self.factory.patch(
            "/api/owner/dishes/bulk-price/",
            body or {},
            format="json",
        )
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── 403 ───────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        resp = self._patch(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_tenant_returns_403(self):
        resp = self._patch(user=_owner(tenant_id=2), tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── 400 validation ────────────────────────────────────────────────────────

    def test_missing_action_returns_400(self):
        resp = self._patch(body={"value": 10})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_action_returns_400(self):
        resp = self._patch(body={"action": "multiply", "value": 10})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_value_returns_400(self):
        resp = self._patch(body={"action": "increase_percent", "value": -5})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_value_returns_400(self):
        resp = self._patch(body={"action": "increase_percent", "value": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_percent_over_100_returns_400(self):
        resp = self._patch(body={"action": "increase_percent", "value": 150})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_numeric_value_returns_400(self):
        resp = self._patch(body={"action": "increase_percent", "value": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_category_id_returns_400(self):
        resp = self._patch(body={"action": "increase_percent", "value": 10, "category_id": "bad"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 200 dry_run ───────────────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_dry_run_does_not_save(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "increase_percent", "value": 10, "dry_run": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["dry_run"])
        self.assertEqual(resp.data["updated"], 0)
        mock_qs.bulk_update.assert_not_called()

    @patch("menu.views.Dish.objects")
    def test_dry_run_returns_preview_items(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "increase_percent", "value": 10, "dry_run": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        items = resp.data["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["old_price"], "100.00")
        self.assertEqual(items[0]["new_price"], "110.00")

    # ── 200 math correctness ──────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_increase_percent_computes_correct_price(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "increase_percent", "value": 10, "dry_run": True})
        self.assertEqual(resp.data["items"][0]["new_price"], "110.00")

    @patch("menu.views.Dish.objects")
    def test_decrease_percent_computes_correct_price(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "decrease_percent", "value": 20, "dry_run": True})
        self.assertEqual(resp.data["items"][0]["new_price"], "80.00")

    @patch("menu.views.Dish.objects")
    def test_increase_flat_computes_correct_price(self, mock_qs):
        dish = _make_dish(price="50.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "increase_flat", "value": 5, "dry_run": True})
        self.assertEqual(resp.data["items"][0]["new_price"], "55.00")

    @patch("menu.views.Dish.objects")
    def test_decrease_flat_does_not_go_below_one_cent(self, mock_qs):
        dish = _make_dish(price="0.50")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "decrease_flat", "value": 999, "dry_run": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(resp.data["items"][0]["new_price"]), Decimal("0.01"))

    @patch("menu.views.Dish.objects")
    def test_decrease_percent_does_not_go_below_one_cent(self, mock_qs):
        dish = _make_dish(price="0.01")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "decrease_percent", "value": 99, "dry_run": True})
        self.assertEqual(Decimal(resp.data["items"][0]["new_price"]), Decimal("0.01"))

    @patch("menu.views.Dish.objects")
    def test_rounding_to_nearest_100(self, mock_qs):
        """round_to=100 should round to the nearest 1.00."""
        dish = _make_dish(price="10.60")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        # 10.60 + 5% = 11.13 → rounded to nearest 1.00 = 11.00
        resp = self._patch(body={"action": "increase_percent", "value": 5, "round_to": 100, "dry_run": True})
        new = Decimal(resp.data["items"][0]["new_price"])
        # Must be a whole number (multiple of 1.00)
        self.assertEqual(new % Decimal("1.00"), Decimal("0.00"))

    # ── 200 apply (not dry_run) ───────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_apply_calls_bulk_update(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        resp = self._patch(body={"action": "increase_percent", "value": 10, "dry_run": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["dry_run"])
        self.assertEqual(resp.data["updated"], 1)
        mock_qs.bulk_update.assert_called_once()

    @patch("menu.views.Dish.objects")
    def test_apply_sets_price_on_dish_object(self, mock_qs):
        dish = _make_dish(price="100.00")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[dish])
        self._patch(body={"action": "increase_percent", "value": 10, "dry_run": False})
        # bulk_update is passed the modified dish; check price attribute was set
        self.assertEqual(dish.price, Decimal("110.00"))

    # ── 200 empty result ──────────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_empty_dishes_returns_updated_zero(self, mock_qs):
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[])
        resp = self._patch(body={"action": "increase_percent", "value": 10})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated"], 0)
        self.assertEqual(resp.data["items"], [])
