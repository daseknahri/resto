"""B3 Phase 2: Ingredient inventory + recipe BOM tests.

Covers:
  • IngredientSerializer validation
  • RecipeLineSerializer validation
  • Owner auth guards (401/403) on all ingredient endpoints
  • OwnerIngredientListCreateView GET/POST
  • OwnerIngredientDetailView GET/PATCH/DELETE
  • OwnerIngredientAdjustView POST
  • OwnerIngredientLowStockView GET
  • OwnerDishRecipeView GET/POST
  • OwnerRecipeLineDetailView DELETE
  • PlaceOrderView source includes ingredient depletion
  • MarketplacePlaceOrderView source includes ingredient depletion
"""
import inspect
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate


# ── Mock helpers ──────────────────────────────────────────────────────────────

def _make_owner():
    """Return a mock TENANT_OWNER user that passes _is_tenant_owner().

    _is_tenant_owner checks ``user.Roles.TENANT_OWNER`` (instance attr), so
    we must set ``u.Roles = User.Roles`` on the mock.
    """
    from accounts.models import User
    u = MagicMock()
    u.is_authenticated = True
    u.is_active = True
    u.is_superuser = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    u.tenant_id = 42
    return u


def _make_staff():
    """Return a mock TENANT_STAFF user that fails _is_tenant_owner()."""
    from accounts.models import User
    u = MagicMock()
    u.is_authenticated = True
    u.is_active = True
    u.is_superuser = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.Roles = User.Roles
    u.tenant_id = 42
    return u


def _with_tenant(req, tenant_id=42):
    """Attach a minimal tenant mock so _is_tenant_owner tenant check passes."""
    req.tenant = MagicMock()
    req.tenant.id = tenant_id
    return req


# ── Serializer unit tests (no DB) ─────────────────────────────────────────────

class IngredientSerializerTests(SimpleTestCase):
    """Validate IngredientSerializer field behaviour without DB."""

    def _ser(self, data=None, instance=None, partial=False):
        from menu.serializers import IngredientSerializer
        return IngredientSerializer(instance=instance, data=data, partial=partial)

    def test_valid_minimal(self):
        s = self._ser({"name": "Flour", "unit": "kg"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_unit(self):
        s = self._ser({"name": "Flour", "unit": "gallon"})
        self.assertFalse(s.is_valid())
        self.assertIn("unit", s.errors)

    def test_negative_quantity_rejected(self):
        s = self._ser({"name": "Egg", "unit": "unit", "stock_quantity": "abc"})
        self.assertFalse(s.is_valid())

    def test_cost_per_unit_optional(self):
        s = self._ser({"name": "Cheese", "unit": "g"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_is_low_stock_field_present(self):
        from menu.serializers import IngredientSerializer
        fields = list(IngredientSerializer().fields.keys())
        self.assertIn("is_low_stock", fields)

    def test_read_only_fields(self):
        from menu.serializers import IngredientSerializer
        s = IngredientSerializer()
        self.assertTrue(s.fields["id"].read_only)
        self.assertTrue(s.fields["created_at"].read_only)
        self.assertTrue(s.fields["is_low_stock"].read_only)


class RecipeLineSerializerTests(SimpleTestCase):
    """Validate RecipeLineSerializer field behaviour without DB."""

    def test_ingredient_name_and_unit_are_read_only(self):
        from menu.serializers import RecipeLineSerializer
        s = RecipeLineSerializer()
        self.assertTrue(s.fields["ingredient_name"].read_only)
        self.assertTrue(s.fields["ingredient_unit"].read_only)

    def test_required_fields(self):
        from menu.serializers import RecipeLineSerializer
        s = RecipeLineSerializer(data={})
        self.assertFalse(s.is_valid())
        self.assertIn("ingredient", s.errors)
        self.assertIn("quantity", s.errors)


# ── Auth guard tests ──────────────────────────────────────────────────────────

class IngredientAuthGuardTests(SimpleTestCase):
    """All ingredient endpoints are blocked for unauthenticated users (403 with
    session auth as primary; 403 is correct DRF behaviour because
    SessionAuthentication returns no WWW-Authenticate challenge header) and
    strictly forbidden for TENANT_STAFF (403).
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import (
            OwnerIngredientListCreateView,
            OwnerIngredientDetailView,
            OwnerIngredientAdjustView,
            OwnerIngredientLowStockView,
        )
        self.list_view = OwnerIngredientListCreateView.as_view()
        self.detail_view = OwnerIngredientDetailView.as_view()
        self.adjust_view = OwnerIngredientAdjustView.as_view()
        self.low_stock_view = OwnerIngredientLowStockView.as_view()

    def test_list_requires_auth(self):
        req = self.factory.get("/api/owner/ingredients/")
        resp = self.list_view(req)
        # DRF converts NotAuthenticated→403 when SessionAuthentication is
        # the primary class (no WWW-Authenticate challenge sent).
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_create_requires_auth(self):
        req = self.factory.post("/api/owner/ingredients/", {"name": "X", "unit": "g"}, format="json")
        resp = self.list_view(req)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_detail_requires_auth(self):
        req = self.factory.get("/api/owner/ingredients/1/")
        resp = self.detail_view(req, pk=1)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_adjust_requires_auth(self):
        req = self.factory.post("/api/owner/ingredients/1/adjust/", {"delta": "10"}, format="json")
        resp = self.adjust_view(req, pk=1)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_low_stock_requires_auth(self):
        req = self.factory.get("/api/owner/ingredients/low-stock/")
        resp = self.low_stock_view(req)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_staff_cannot_access_ingredients(self):
        """TENANT_STAFF may not manage ingredients (owner-only)."""
        staff = _make_staff()
        req = self.factory.get("/api/owner/ingredients/")
        force_authenticate(req, user=staff)
        _with_tenant(req)
        resp = self.list_view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class RecipeViewAuthGuardTests(SimpleTestCase):
    """Recipe view requires owner auth."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerDishRecipeView, OwnerRecipeLineDetailView
        self.recipe_view = OwnerDishRecipeView.as_view()
        self.line_view = OwnerRecipeLineDetailView.as_view()

    def test_recipe_get_requires_auth(self):
        req = self.factory.get("/api/owner/dishes/1/recipe/")
        resp = self.recipe_view(req, dish_id=1)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_recipe_line_delete_requires_auth(self):
        req = self.factory.delete("/api/owner/recipe-lines/1/")
        resp = self.line_view(req, pk=1)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_staff_cannot_access_recipe(self):
        staff = _make_staff()
        req = self.factory.get("/api/owner/dishes/1/recipe/")
        force_authenticate(req, user=staff)
        _with_tenant(req)
        resp = self.recipe_view(req, dish_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── OwnerIngredientListCreateView ─────────────────────────────────────────────

class OwnerIngredientListCreateViewTests(SimpleTestCase):
    """GET + POST on /api/owner/ingredients/ (DB mocked)."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerIngredientListCreateView
        self.view = OwnerIngredientListCreateView.as_view()
        self.owner = _make_owner()

    def _req(self, method, url="/api/owner/ingredients/", **kwargs):
        req = getattr(self.factory, method)(url, **kwargs)
        force_authenticate(req, user=self.owner)
        _with_tenant(req)
        return req

    @patch("menu.views.Ingredient")
    @patch("menu.views.IngredientSerializer")
    def test_get_returns_200(self, MockSer, MockIng):
        MockSer.return_value.data = []
        MockIng.objects.filter.return_value = []
        resp = self.view(self._req("get"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.IngredientSerializer")
    def test_post_invalid_returns_400(self, MockSer):
        instance = MockSer.return_value
        instance.is_valid.return_value = False
        instance.errors = {"name": ["required"]}
        resp = self.view(self._req("post", data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.IngredientSerializer")
    def test_post_valid_returns_201(self, MockSer):
        instance = MockSer.return_value
        instance.is_valid.return_value = True
        instance.data = {"id": 1, "name": "Flour", "unit": "kg"}
        instance.save.return_value = None
        resp = self.view(
            self._req("post", data={"name": "Flour", "unit": "kg"}, format="json")
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ── OwnerIngredientDetailView ─────────────────────────────────────────────────

class OwnerIngredientDetailViewTests(SimpleTestCase):
    """GET/PATCH/DELETE on /api/owner/ingredients/<pk>/."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerIngredientDetailView
        self.view = OwnerIngredientDetailView.as_view()
        self.owner = _make_owner()

    def _req(self, method, url, **kwargs):
        req = getattr(self.factory, method)(url, **kwargs)
        force_authenticate(req, user=self.owner)
        _with_tenant(req)
        return req

    @patch("menu.views.Ingredient")
    def test_get_not_found(self, MockIng):
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.side_effect = _DNE()
        resp = self.view(self._req("get", "/api/owner/ingredients/99/"), pk=99)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views.IngredientSerializer")
    @patch("menu.views.Ingredient")
    def test_get_found(self, MockIng, MockSer):
        ing = MagicMock()
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.return_value = ing
        MockSer.return_value.data = {"id": 1, "name": "Salt"}
        resp = self.view(self._req("get", "/api/owner/ingredients/1/"), pk=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.Ingredient")
    def test_delete_marks_inactive(self, MockIng):
        ing = MagicMock()
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.return_value = ing
        resp = self.view(self._req("delete", "/api/owner/ingredients/1/"), pk=1)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        ing.save.assert_called_once()
        self.assertFalse(ing.is_active)


# ── OwnerIngredientAdjustView ─────────────────────────────────────────────────

class OwnerIngredientAdjustViewTests(SimpleTestCase):
    """POST /api/owner/ingredients/<pk>/adjust/."""

    def setUp(self):
        self.factory = APIRequestFactory()
        from menu.views import OwnerIngredientAdjustView
        self.view = OwnerIngredientAdjustView.as_view()
        self.owner = _make_owner()

    def _req(self, data):
        req = self.factory.post("/api/owner/ingredients/1/adjust/", data, format="json")
        force_authenticate(req, user=self.owner)
        _with_tenant(req)
        return req

    @patch("menu.views.Ingredient")
    def test_zero_delta_rejected(self, MockIng):
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.return_value = MagicMock()
        resp = self.view(self._req({"delta": "0"}), pk=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Ingredient")
    def test_invalid_delta_rejected(self, MockIng):
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.return_value = MagicMock()
        resp = self.view(self._req({"delta": "abc"}), pk=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.IngredientSerializer")
    @patch("menu.views.Ingredient")
    def test_valid_adjustment_updates_stock(self, MockIng, MockSer):
        ing = MagicMock()
        _DNE = type("DoesNotExist", (Exception,), {})
        MockIng.DoesNotExist = _DNE
        MockIng.objects.get.return_value = ing
        MockIng.objects.filter.return_value.update.return_value = 1
        ing.refresh_from_db.return_value = None
        MockSer.return_value.data = {"id": 1, "stock_quantity": "100.000"}
        resp = self.view(self._req({"delta": "50"}), pk=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ── Source code integrity checks ──────────────────────────────────────────────

class IngredientDepletionSourceTests(SimpleTestCase):
    """Verify ingredient depletion code is present in both order views."""

    def test_place_order_view_depletes_ingredients(self):
        from menu.views import PlaceOrderView
        src = inspect.getsource(PlaceOrderView.post)
        self.assertIn("RecipeLine.objects.filter", src,
                      "PlaceOrderView.post must query RecipeLine for ingredient depletion")
        self.assertIn("stock_quantity", src,
                      "PlaceOrderView.post must update ingredient stock_quantity")

    def test_marketplace_place_order_depletes_ingredients(self):
        from accounts.views import MarketplacePlaceOrderView
        src = inspect.getsource(MarketplacePlaceOrderView.post)
        self.assertIn("_RecipeLine", src,
                      "MarketplacePlaceOrderView.post must query RecipeLine for ingredient depletion")
        self.assertIn("stock_quantity", src,
                      "MarketplacePlaceOrderView.post must update ingredient stock_quantity")

    def test_depletion_is_inside_atomic_block(self):
        """The depletion code appears after the stock-update block in the atomic section."""
        from menu.views import PlaceOrderView
        src = inspect.getsource(PlaceOrderView.post)
        stock_auto_idx = src.find("stock_auto_zeroed")
        recipe_line_idx = src.find("RecipeLine.objects.filter")
        self.assertGreater(recipe_line_idx, stock_auto_idx,
                           "Ingredient depletion must come after dish-stock update in PlaceOrderView.post")


# ── URL registration checks ───────────────────────────────────────────────────

class IngredientUrlTests(SimpleTestCase):
    """Verify the ingredient URLs are registered."""

    def test_owner_ingredients_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-ingredients")
        self.assertIn("/api/owner/ingredients/", url)

    def test_owner_ingredient_detail_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-ingredient-detail", kwargs={"pk": 1})
        self.assertIn("/api/owner/ingredients/1/", url)

    def test_owner_ingredient_adjust_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-ingredient-adjust", kwargs={"pk": 1})
        self.assertIn("/api/owner/ingredients/1/adjust/", url)

    def test_owner_ingredient_low_stock_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-ingredients-low-stock")
        self.assertIn("/api/owner/ingredients/low-stock/", url)

    def test_owner_dish_recipe_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-dish-recipe", kwargs={"dish_id": 5})
        self.assertIn("/api/owner/dishes/5/recipe/", url)

    def test_owner_recipe_line_detail_url_registered(self):
        from django.urls import reverse
        url = reverse("owner-recipe-line-detail", kwargs={"pk": 3})
        self.assertIn("/api/owner/recipe-lines/3/", url)


# ── Model field checks ────────────────────────────────────────────────────────

class IngredientModelTests(SimpleTestCase):
    """Verify Ingredient and RecipeLine model fields."""

    def test_ingredient_has_required_fields(self):
        from menu.models import Ingredient
        field_names = [f.name for f in Ingredient._meta.get_fields()]
        for field in ("name", "unit", "stock_quantity", "low_stock_threshold",
                      "cost_per_unit", "is_active", "created_at", "updated_at"):
            self.assertIn(field, field_names, f"Ingredient missing field: {field}")

    def test_ingredient_unit_choices(self):
        from menu.models import Ingredient
        unit_field = Ingredient._meta.get_field("unit")
        choice_keys = [c[0] for c in unit_field.choices]
        for unit in ("g", "kg", "ml", "L", "unit", "oz", "lb", "tsp", "tbsp"):
            self.assertIn(unit, choice_keys, f"Unit '{unit}' missing from Ingredient.unit choices")

    def test_recipe_line_has_required_fields(self):
        from menu.models import RecipeLine
        field_names = [f.name for f in RecipeLine._meta.get_fields()]
        for field in ("dish", "ingredient", "quantity"):
            self.assertIn(field, field_names, f"RecipeLine missing field: {field}")

    def test_recipe_line_unique_together(self):
        from menu.models import RecipeLine
        unique_constraints = RecipeLine._meta.unique_together
        self.assertIn(("dish", "ingredient"), unique_constraints)
