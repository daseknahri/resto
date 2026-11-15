"""
Tests for DishBulkResetAvailabilityView (S1-A, B-04).

  POST /api/owner/dishes/bulk-reset-availability/

Scoped morning-reset: re-enables ONLY the dishes named in `dish_ids` (published
+ currently sold out) and clears their auto-zeroed stock counts. This is the
dedicated endpoint the owner boards call after the owner confirms with the
affected count — the bare `/owner/dishes/reset-availability/` endpoint (whole
menu, no scope) is deliberately NOT called by the boards anymore.

All tests are SimpleTestCase (no database). ORM calls are fully mocked
(same pattern as test_bulk_order_status.py / test_bulk_price_update.py).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import DishBulkResetAvailabilityView


# ── Helpers ────────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 10
    u.id = 10
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.effective_perm_edit_menu.return_value = True
    u.Roles = User.Roles
    return u


def _staff_without_menu_perm(tenant_id=1):
    u = _owner(tenant_id=tenant_id)
    u.role = User.Roles.TENANT_STAFF
    u.effective_perm_edit_menu.return_value = False
    return u


def _anon():
    u = MagicMock(spec=User)
    u.is_authenticated = False
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, slug="demo", name="Demo Restaurant")


# ── Test class ─────────────────────────────────────────────────────────────────

class DishBulkResetAvailabilityViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DishBulkResetAvailabilityView.as_view()

    def _post(self, body=None, user=None, tenant=None):
        req = self.factory.post(
            "/api/owner/dishes/bulk-reset-availability/",
            body or {},
            format="json",
        )
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_tenant_returns_403(self):
        resp = self._post(user=_owner(tenant_id=2), tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_without_edit_menu_perm_returns_403(self):
        resp = self._post(user=_staff_without_menu_perm())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── 400 validation ────────────────────────────────────────────────────────

    def test_missing_dish_ids_returns_400(self):
        resp = self._post(body={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_dish_ids_returns_400(self):
        resp = self._post(body={"dish_ids": []})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_list_dish_ids_returns_400(self):
        resp = self._post(body={"dish_ids": "11,12"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_integer_dish_ids_returns_400(self):
        resp = self._post(body={"dish_ids": ["abc", "def"]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_dish_ids_returns_400(self):
        resp = self._post(body={"dish_ids": list(range(501))})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 200 success ───────────────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_restores_only_the_named_sold_out_dishes(self, mock_qs):
        """The restore UPDATE is scoped to id__in + published + sold-out."""
        mock_qs.filter.return_value.update.side_effect = [2, 1]
        resp = self._post(body={"dish_ids": [11, 12]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["restored"], 2)
        self.assertEqual(resp.data["stock_cleared"], 1)
        self.assertEqual(resp.data["requested"], 2)
        # First UPDATE (restore): only the named ids, only published sold-out.
        restore_call = mock_qs.filter.call_args_list[0]
        self.assertEqual(
            restore_call.kwargs,
            {"id__in": [11, 12], "is_published": True, "is_available": False},
        )
        self.assertEqual(
            mock_qs.filter.return_value.update.call_args_list[0].kwargs,
            {"is_available": True, "stock_auto_zeroed": False},
        )

    @patch("menu.views.Dish.objects")
    def test_stock_clear_is_scoped_to_the_same_ids(self, mock_qs):
        """The stock-clear UPDATE must not touch dishes outside the request."""
        mock_qs.filter.return_value.update.side_effect = [2, 1]
        self._post(body={"dish_ids": [11, 12]})
        stock_call = mock_qs.filter.call_args_list[1]
        self.assertEqual(
            stock_call.kwargs,
            {"id__in": [11, 12], "is_published": True, "stock_qty": 0},
        )
        self.assertEqual(
            mock_qs.filter.return_value.update.call_args_list[1].kwargs,
            {"stock_qty": None},
        )

    @patch("menu.views.Dish.objects")
    def test_unknown_or_available_ids_restore_zero(self, mock_qs):
        """Ids that do not exist (or are not sold out) simply restore zero —
        they are reported, not treated as an error."""
        mock_qs.filter.return_value.update.side_effect = [0, 0]
        resp = self._post(body={"dish_ids": [99]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["restored"], 0)
        self.assertEqual(resp.data["requested"], 1)

    @patch("menu.views.Dish.objects")
    def test_string_ids_are_coerced_to_int(self, mock_qs):
        """JSON ids may arrive as strings; the view coerces them like the
        bulk-status order endpoint does."""
        mock_qs.filter.return_value.update.side_effect = [1, 0]
        resp = self._post(body={"dish_ids": ["11"]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            mock_qs.filter.call_args_list[0].kwargs["id__in"], [11]
        )
