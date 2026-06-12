"""
Tests for DishBulkAvailabilityResetView
POST /api/owner/dishes/reset-availability/
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import DishBulkAvailabilityResetView


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
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid)


def _filter_mock(update_return):
    """Return a queryset mock whose .update() returns `update_return`."""
    m = MagicMock()
    m.update.return_value = update_return
    return m


class DishBulkAvailabilityResetViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DishBulkAvailabilityResetView.as_view()

    def _post(self, body=None, user=None, tenant=None):
        user = user or _owner()
        req = self.factory.post(
            "/api/owner/dishes/reset-availability/",
            body or {},
            format="json",
        )
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        anon = MagicMock()
        anon.is_authenticated = False
        req = self.factory.post(
            "/api/owner/dishes/reset-availability/", {}, format="json"
        )
        req.user = anon
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Dish.objects")
    def test_cross_tenant_returns_403(self, dish_objects):
        wrong_user = _owner(tenant_id=99)
        resp = self._post(user=wrong_user, tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        dish_objects.filter.assert_not_called()

    # ── Happy path — default (clear_stock=false) ──────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_restores_sold_out_dishes(self, dish_objects):
        """By default, all published unavailable dishes are re-enabled."""
        dish_objects.filter.side_effect = [
            _filter_mock(4),  # is_available=False → update(is_available=True) → 4
            _filter_mock(2),  # stock_qty=0        → update(stock_qty=None)    → 2
        ]
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["restored"], 4)
        self.assertEqual(resp.data["stock_cleared"], 2)
        self.assertFalse(resp.data["clear_stock_all"])

    @patch("menu.views.Dish.objects")
    def test_zero_restored_when_all_already_available(self, dish_objects):
        """Idempotent — returns 0 when nothing needs resetting."""
        dish_objects.filter.side_effect = [_filter_mock(0), _filter_mock(0)]
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["restored"], 0)
        self.assertEqual(resp.data["stock_cleared"], 0)

    # ── clear_stock=true path ─────────────────────────────────────────────────

    @patch("menu.views.Dish.objects")
    def test_clear_stock_true_clears_all_tracked_stock(self, dish_objects):
        """When clear_stock=true, ALL non-null stock_qty rows are cleared."""
        dish_objects.filter.side_effect = [
            _filter_mock(1),   # availability reset
            _filter_mock(7),   # full stock wipe
        ]
        resp = self._post({"clear_stock": True})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["stock_cleared"], 7)
        self.assertTrue(resp.data["clear_stock_all"])

    @patch("menu.views.Dish.objects")
    def test_clear_stock_false_only_clears_zero_stock(self, dish_objects):
        """When clear_stock=false (default), only auto-zeroed rows are cleared.

        The second filter call must use stock_qty=0, not stock_qty__isnull=False.
        """
        dish_objects.filter.side_effect = [_filter_mock(0), _filter_mock(3)]
        self._post({"clear_stock": False})

        # Second call should filter on stock_qty=0, not isnull
        second_call_kwargs = dish_objects.filter.call_args_list[1][1]
        self.assertIn("stock_qty", second_call_kwargs)
        self.assertEqual(second_call_kwargs["stock_qty"], 0)

    @patch("menu.views.Dish.objects")
    def test_availability_reset_clears_stock_auto_zeroed(self, dish_objects):
        """The availability-restore update must also clear stock_auto_zeroed=False.

        Without this, the 5am cron (auto_reset_availability) will find dishes
        with stock_auto_zeroed=True and zero out any stock_qty the owner set
        between the bulk reset and the cron run.
        """
        avail_filter_mock = _filter_mock(3)
        dish_objects.filter.side_effect = [avail_filter_mock, _filter_mock(0)]
        self._post()

        # First filter().update() must include stock_auto_zeroed=False
        update_kwargs = avail_filter_mock.update.call_args[1]
        self.assertIn("stock_auto_zeroed", update_kwargs,
                      "availability reset must clear stock_auto_zeroed to prevent cron re-zero")
        self.assertFalse(update_kwargs["stock_auto_zeroed"])
