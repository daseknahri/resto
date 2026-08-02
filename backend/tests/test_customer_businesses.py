"""Tests for the flywheel "My businesses" surface.

  - CustomerBusinessesView       GET  /api/customer/businesses/
  - CustomerBusinessFollowView   POST/DELETE /api/customer/businesses/follow/

Unit-level (SimpleTestCase + mocks — no real DB): the public-schema querysets
(CustomerOrderRef, CustomerTenantFollow, Tenant, Profile) are mocked, so the
merge/sort logic and the follow/unfollow behavior are exercised without Postgres.
"""
from datetime import datetime, timezone as _tz
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.authentication import CustomerSessionAuthentication
from accounts.permissions import IsCustomer
from accounts.throttles import CustomerBusinessesThrottle
from accounts.models import Customer
from tenancy.models import Tenant
from accounts.views import CustomerBusinessesView, CustomerBusinessFollowView


DT_NEW = datetime(2026, 8, 1, 12, 0, tzinfo=_tz.utc)
DT_MID = datetime(2026, 7, 15, 12, 0, tzinfo=_tz.utc)
DT_OLD = datetime(2026, 7, 1, 12, 0, tzinfo=_tz.utc)


def _customer(pk=1):
    return Customer(id=pk, phone_verified=True, phone="+212600001234", phone_digits="600001234")


class CustomerBusinessesViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate the per-customer customer_businesses throttle counter
        self.factory = APIRequestFactory()
        self.view = CustomerBusinessesView.as_view()

    def _get(self, principal=None, refs=None, follows=None):
        mock_ref = MagicMock()
        mock_ref.objects.filter.return_value.order_by.return_value.values.return_value = refs or []
        mock_follow = MagicMock()
        mock_follow.objects.filter.return_value.values.return_value = follows or []

        req = self.factory.get("/api/customer/businesses/")
        if principal is not None:
            force_authenticate(req, user=principal)
        with patch("accounts.models.CustomerOrderRef", mock_ref), \
                patch("accounts.models.CustomerTenantFollow", mock_follow):
            return self.view(req)

    def test_anonymous_returns_401(self):
        self.assertEqual(self._get(principal=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_merges_ordered_and_followed_and_sorts(self):
        refs = [  # most-recent first (as .order_by('-order_created_at') would yield)
            {"tenant_id": 10, "restaurant_name": "Bistro", "restaurant_slug": "bistro",
             "vertical": "food", "order_created_at": DT_NEW},
            {"tenant_id": 20, "restaurant_name": "Souk", "restaurant_slug": "souk",
             "vertical": "shops", "order_created_at": DT_MID},
            {"tenant_id": 10, "restaurant_name": "Bistro", "restaurant_slug": "bistro",
             "vertical": "food", "order_created_at": DT_OLD},
        ]
        follows = [  # a followed business never ordered from
            {"tenant_id": 30, "restaurant_name": "Cafe", "restaurant_slug": "cafe", "vertical": "food"},
        ]
        resp = self._get(principal=_customer(), refs=refs, follows=follows)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 3)
        rows = resp.data["businesses"]
        # Favorite first, then most-recently-ordered.
        self.assertEqual(rows[0]["tenant_id"], 30)
        self.assertTrue(rows[0]["is_favorite"])
        self.assertEqual(rows[0]["order_count"], 0)
        self.assertIsNone(rows[0]["last_order_at"])
        self.assertEqual(rows[1]["tenant_id"], 10)      # Bistro — 2 orders, latest DT_NEW
        self.assertFalse(rows[1]["is_favorite"])
        self.assertEqual(rows[1]["order_count"], 2)
        self.assertEqual(rows[1]["last_order_at"], DT_NEW.isoformat())
        self.assertEqual(rows[2]["tenant_id"], 20)      # Souk — 1 order, DT_MID
        self.assertEqual(rows[2]["order_count"], 1)

    def test_followed_business_also_ordered_is_marked_favorite(self):
        refs = [{"tenant_id": 10, "restaurant_name": "Bistro", "restaurant_slug": "bistro",
                 "vertical": "food", "order_created_at": DT_NEW}]
        follows = [{"tenant_id": 10, "restaurant_name": "Bistro", "restaurant_slug": "bistro",
                    "vertical": "food"}]
        resp = self._get(principal=_customer(), refs=refs, follows=follows)
        self.assertEqual(resp.data["count"], 1)
        self.assertTrue(resp.data["businesses"][0]["is_favorite"])
        self.assertEqual(resp.data["businesses"][0]["order_count"], 1)

    def test_auth_contract(self):
        self.assertIn(CustomerSessionAuthentication, CustomerBusinessesView.authentication_classes)
        self.assertIn(IsCustomer, CustomerBusinessesView.permission_classes)
        self.assertIn(CustomerBusinessesThrottle, CustomerBusinessesView.throttle_classes)


class CustomerBusinessFollowViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = CustomerBusinessFollowView.as_view()

    def _req(self, method, body, principal=None, tenant_exists=True):
        mock_tenant_cls = MagicMock()
        mock_tenant_cls.DoesNotExist = Tenant.DoesNotExist
        if tenant_exists:
            mock_tenant_cls.objects.get.return_value = MagicMock(id=10, name="Bistro", slug="bistro")
        else:
            mock_tenant_cls.objects.get.side_effect = Tenant.DoesNotExist

        mock_profile = MagicMock()
        mock_profile.objects.filter.return_value.values_list.return_value.first.return_value = "restaurant"
        mock_follow = MagicMock()

        req = getattr(self.factory, method)("/api/customer/businesses/follow/", body, format="json")
        if principal is not None:
            force_authenticate(req, user=principal)
        with patch("tenancy.models.Tenant", mock_tenant_cls), \
                patch("tenancy.models.Profile", mock_profile), \
                patch("accounts.models.CustomerTenantFollow", mock_follow):
            resp = self.view(req)
        return resp, mock_follow

    def test_follow_upserts(self):
        resp, mock_follow = self._req("post", {"restaurant": "bistro"}, principal=_customer())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["followed"])
        mock_follow.objects.update_or_create.assert_called_once()
        kwargs = mock_follow.objects.update_or_create.call_args.kwargs
        self.assertEqual(kwargs.get("tenant_id"), 10)
        self.assertEqual(kwargs["defaults"]["vertical"], "food")  # restaurant → food

    def test_unfollow_deletes(self):
        resp, mock_follow = self._req("delete", {"restaurant": "bistro"}, principal=_customer())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["followed"])
        mock_follow.objects.filter.return_value.delete.assert_called_once()

    def test_follow_anonymous_401(self):
        resp, _ = self._req("post", {"restaurant": "bistro"}, principal=None)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_follow_missing_slug_400(self):
        resp, _ = self._req("post", {}, principal=_customer())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_follow_tenant_not_found_404(self):
        resp, _ = self._req("post", {"restaurant": "nope"}, principal=_customer(), tenant_exists=False)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
