"""
Tests for promotion-related views:
  - OwnerPromotionListCreateView  GET/POST /api/owner/promotions/
  - OwnerPromotionDetailView      GET/PATCH/DELETE /api/owner/promotions/<id>/
  - PromoCodeCheckView            GET /api/promo-code-check/?code=XXX

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerPromotionDetailView, OwnerPromotionListCreateView, PromoCodeCheckView
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


def _make_promo(promo_id=1, name="Happy Hour", promo_type="percentage",
                discount_value="10.00", min_order_amount="0.00",
                is_active=True, max_uses=None, use_count=0, code="HAPPY",
                is_platform_flash=False):
    p = MagicMock()
    p.id = promo_id
    p.name = name
    p.description = ""
    p.promo_type = promo_type
    p.discount_value = Decimal(discount_value)
    p.min_order_amount = Decimal(min_order_amount)
    p.days = []
    p.time_start = ""
    p.time_end = ""
    p.active_from = None
    p.active_until = None
    p.is_active = is_active
    p.max_uses = max_uses
    p.use_count = use_count
    p.is_platform_flash = is_platform_flash
    p.code = code
    p.created_at = MagicMock()
    p.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return p


# ── OwnerPromotionListCreateView ──────────────────────────────────────────────

class OwnerPromotionListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerPromotionListCreateView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/promotions/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/promotions/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_outsider_returns_403(self):
        resp = self._post({"name": "Test"}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET list ──────────────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    def test_get_returns_list(self, mock_promo_objs):
        promo = _make_promo()
        mock_promo_objs.all.return_value = [promo]

        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "Happy Hour")

    @patch("menu.views.Promotion.objects")
    def test_get_empty_list(self, mock_promo_objs):
        mock_promo_objs.all.return_value = []
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_missing_name_returns_400(self):
        resp = self._post({"promo_type": "percentage", "discount_value": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_name")

    def test_post_invalid_promo_type_returns_400(self):
        resp = self._post({"name": "Deal", "promo_type": "bogus"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_type")

    # ── POST happy path ───────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    def test_post_creates_promotion_and_returns_201(self, mock_promo_objs):
        promo = _make_promo(name="Lunch Deal", promo_type="fixed",
                            discount_value="5.00", code="LUNCH")
        mock_promo_objs.create.return_value = promo

        resp = self._post({
            "name": "Lunch Deal",
            "promo_type": "fixed",
            "discount_value": "5.00",
            "code": "LUNCH",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        for field in ("id", "name", "promo_type", "discount_value", "is_active", "code"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertEqual(resp.data["name"], "Lunch Deal")
        mock_promo_objs.create.assert_called_once()

    @patch("menu.views.Promotion.objects")
    def test_post_free_delivery_type_accepted(self, mock_promo_objs):
        promo = _make_promo(promo_type="free_delivery")
        mock_promo_objs.create.return_value = promo

        resp = self._post({"name": "Free Delivery Weekend", "promo_type": "free_delivery"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ── OwnerPromotionDetailView ──────────────────────────────────────────────────

class OwnerPromotionDetailViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerPromotionDetailView.as_view()

    def _get(self, promo_id, user=None, tenant=None):
        req = self.factory.get(f"/api/owner/promotions/{promo_id}/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, promo_id=promo_id)

    def _patch(self, promo_id, data, user=None, tenant=None):
        req = self.factory.patch(f"/api/owner/promotions/{promo_id}/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, promo_id=promo_id)

    def _delete(self, promo_id, user=None, tenant=None):
        req = self.factory.delete(f"/api/owner/promotions/{promo_id}/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, promo_id=promo_id)

    # ── Auth / not-found ──────────────────────────────────────────────────────

    def test_get_outsider_returns_403(self):
        resp = self._get(1, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views.Promotion.objects")
    def test_get_not_found_returns_404(self, mock_promo_objs):
        mock_promo_objs.filter.return_value.first.return_value = None
        resp = self._get(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── GET ───────────────────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    def test_get_returns_promotion(self, mock_promo_objs):
        promo = _make_promo(promo_id=1, name="Happy Hour")
        mock_promo_objs.filter.return_value.first.return_value = promo

        resp = self._get(1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["name"], "Happy Hour")

    # ── PATCH ─────────────────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    def test_patch_updates_name(self, mock_promo_objs):
        promo = _make_promo(promo_id=1, name="Old Name")
        mock_promo_objs.filter.return_value.first.return_value = promo

        resp = self._patch(1, {"name": "New Name"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(promo.name, "New Name")
        promo.save.assert_called_once()

    @patch("menu.views.Promotion.objects")
    def test_patch_updates_is_active(self, mock_promo_objs):
        promo = _make_promo(is_active=True)
        mock_promo_objs.filter.return_value.first.return_value = promo

        resp = self._patch(1, {"is_active": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(promo.is_active)

    @patch("menu.views.Promotion.objects")
    def test_patch_invalid_promo_type_ignored(self, mock_promo_objs):
        promo = _make_promo(promo_type="percentage")
        mock_promo_objs.filter.return_value.first.return_value = promo

        resp = self._patch(1, {"promo_type": "bogus"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Original type unchanged
        self.assertEqual(promo.promo_type, "percentage")

    # ── DELETE ────────────────────────────────────────────────────────────────

    @patch("menu.views.Promotion.objects")
    def test_delete_returns_204(self, mock_promo_objs):
        promo = _make_promo()
        mock_promo_objs.filter.return_value.first.return_value = promo

        resp = self._delete(1)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        promo.delete.assert_called_once()


# ── PromoCodeCheckView ────────────────────────────────────────────────────────

class PromoCodeCheckViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PromoCodeCheckView.as_view()

    def _get(self, code=None, tenant=None):
        params = {"code": code} if code is not None else {}
        req = self.factory.get("/api/promo-code-check/", params)
        req.user = MagicMock(is_authenticated=False)
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_no_code_returns_400(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["valid"])

    @patch("menu.views.Promotion.objects")
    def test_unknown_code_returns_200_invalid(self, mock_promo_objs):
        from menu.models import Promotion
        mock_promo_objs.get.side_effect = Promotion.DoesNotExist
        resp = self._get(code="NOPE")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["valid"])

    @patch("menu.views.Promotion.objects")
    def test_usage_cap_reached_returns_invalid(self, mock_promo_objs):
        promo = _make_promo(max_uses=10, use_count=10)
        mock_promo_objs.get.return_value = promo
        resp = self._get(code="FULL")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["valid"])

    @patch("menu.views._is_promo_active_now")
    @patch("menu.views.Promotion.objects")
    def test_not_active_now_returns_invalid(self, mock_promo_objs, mock_active_now):
        promo = _make_promo(max_uses=None)
        mock_promo_objs.get.return_value = promo
        mock_active_now.return_value = False

        resp = self._get(code="OFFHOURS")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["valid"])

    @patch("menu.views._is_promo_active_now")
    @patch("menu.views.Promotion.objects")
    def test_valid_code_returns_200_with_details(self, mock_promo_objs, mock_active_now):
        promo = _make_promo(
            name="Happy Hour", promo_type="percentage",
            discount_value="15.00", min_order_amount="20.00",
            max_uses=None,
        )
        mock_promo_objs.get.return_value = promo
        mock_active_now.return_value = True

        resp = self._get(code="HAPPY")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["valid"])
        self.assertEqual(resp.data["name"], "Happy Hour")
        self.assertEqual(resp.data["promo_type"], "percentage")
        self.assertEqual(resp.data["discount_value"], "15.00")
        self.assertEqual(resp.data["min_order_amount"], "20.00")

    @patch("menu.views._is_promo_active_now")
    @patch("menu.views.Promotion.objects")
    def test_code_lookup_is_case_insensitive(self, mock_promo_objs, mock_active_now):
        """The view uppercases the code before lookup (iexact handled by ORM)."""
        promo = _make_promo(code="HAPPY")
        mock_promo_objs.get.return_value = promo
        mock_active_now.return_value = True

        self._get(code="happy")
        # Verify the get was called with the uppercased code
        call_kwargs = mock_promo_objs.get.call_args[1]
        self.assertEqual(call_kwargs.get("code__iexact"), "HAPPY")
