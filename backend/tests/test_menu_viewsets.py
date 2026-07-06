"""
Tests for the menu ViewSets and their shared PublishAccessMixin logic:
  - SuperCategoryViewSet
  - CategoryViewSet
  - DishViewSet   (including perform_create dish-limit gate)
  - DishOptionViewSet
  - OptionGroupViewSet  (including cache-bust)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import (
    CategoryViewSet,
    DishViewSet,
    OptionGroupViewSet,
    SuperCategoryViewSet,
)


@contextmanager
def _noop_atomic(*args, **kwargs):
    """Stand-in for transaction.atomic() so unit tests need no real DB."""
    yield


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


def _staff(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, slug="restaurant", schema_name="restaurant")


def _profile(is_menu_published=True, is_menu_temporarily_disabled=False):
    p = MagicMock()
    p.is_menu_published = is_menu_published
    p.is_menu_temporarily_disabled = is_menu_temporarily_disabled
    p.menu_disabled_note = ""
    return p


def _make_qs(items=None):
    """Return a mock queryset that behaves like an empty or populated list."""
    qs = MagicMock()
    items = items or []
    qs.filter.return_value = qs
    qs.annotate.return_value = qs
    qs.all.return_value = qs
    qs.order_by.return_value = qs
    qs.select_related.return_value = qs
    qs.prefetch_related.return_value = qs
    qs.count.return_value = len(items)
    qs.__iter__ = lambda s: iter(items)
    qs.__len__ = lambda s: len(items)
    return qs


# ── PublishAccessMixin policy tests (via SuperCategoryViewSet) ─────────────────

class PublishPolicyTests(SimpleTestCase):
    """Test _enforce_public_menu_policy via the simplest ViewSet."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SuperCategoryViewSet.as_view({"get": "list"})

    def _get(self, user=None, tenant=None, profile=None):
        req = self.factory.get("/api/super-categories/")
        req.user = user or _anon()
        if tenant is not None:
            req.tenant = tenant
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.annotate.return_value.all.return_value.order_by.return_value = \
                _make_qs()
            with patch.object(SuperCategoryViewSet, "_profile", return_value=profile):
                return self.view(req)

    def test_unpublished_menu_returns_403_for_anonymous(self):
        p = _profile(is_menu_published=False)
        resp = self._get(user=_anon(), tenant=_tenant(), profile=p)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_published_menu_returns_200_for_anonymous(self):
        p = _profile(is_menu_published=True)
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.annotate.return_value.all.return_value.order_by.return_value = \
                _make_qs()
            with patch("menu.views.cache") as mock_cache:
                mock_cache.get.return_value = None
                req = self.factory.get("/api/super-categories/")
                req.user = _anon()
                req.tenant = _tenant()
                with patch.object(SuperCategoryViewSet, "_profile", return_value=p):
                    resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_temporarily_disabled_returns_503_for_anonymous(self):
        p = _profile(is_menu_published=True, is_menu_temporarily_disabled=True)
        resp = self._get(user=_anon(), tenant=_tenant(), profile=p)
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "menu_temporarily_disabled")

    def test_owner_can_preview_despite_unpublished_menu(self):
        p = _profile(is_menu_published=False)
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.annotate.return_value.all.return_value.order_by.return_value = \
                _make_qs()
            req = self.factory.get("/api/super-categories/")
            req.user = _owner(tenant_id=1)
            req.tenant = _tenant(tenant_id=1)
            with patch.object(SuperCategoryViewSet, "_profile", return_value=p):
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_no_tenant_blocks_public_access_when_unpublished(self):
        """With no tenant on request, _profile() returns None → unpublished."""
        resp = self._get(user=_anon(), tenant=None, profile=None)
        # No tenant → _menu_is_published() = False → 403
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── _can_preview_unpublished ──────────────────────────────────────────────────

class CanPreviewUnpublishedTests(SimpleTestCase):
    """Unit-test the mixin method directly via an instance."""

    def _make_viewset(self, user=None, tenant=None):
        vs = SuperCategoryViewSet()
        vs.request = SimpleNamespace(
            user=user or _anon(),
            tenant=tenant,
        )
        return vs

    def test_anon_cannot_preview(self):
        vs = self._make_viewset()
        self.assertFalse(vs._can_preview_unpublished())

    def test_owner_with_matching_tenant_can_preview(self):
        vs = self._make_viewset(user=_owner(tenant_id=1), tenant=_tenant(tenant_id=1))
        self.assertTrue(vs._can_preview_unpublished())

    def test_owner_different_tenant_cannot_preview(self):
        vs = self._make_viewset(user=_owner(tenant_id=99), tenant=_tenant(tenant_id=1))
        self.assertFalse(vs._can_preview_unpublished())

    def test_staff_can_preview(self):
        vs = self._make_viewset(user=_staff(tenant_id=1), tenant=_tenant(tenant_id=1))
        self.assertTrue(vs._can_preview_unpublished())

    def test_superuser_can_preview(self):
        user = _owner(tenant_id=99)
        user.is_superuser = True
        vs = self._make_viewset(user=user, tenant=_tenant(tenant_id=1))
        self.assertTrue(vs._can_preview_unpublished())

    def test_no_tenant_cannot_preview(self):
        vs = self._make_viewset(user=_owner(tenant_id=1), tenant=None)
        self.assertFalse(vs._can_preview_unpublished())


# ── DishViewSet – perform_create dish limit ───────────────────────────────────

class DishViewSetPerformCreateTests(SimpleTestCase):
    """Test the per-plan dish-limit gate in DishViewSet.perform_create."""

    def _make_viewset(self, tenant=None):
        vs = DishViewSet()
        vs.request = SimpleNamespace(
            tenant=tenant or _tenant(),
            user=_owner(),
        )
        return vs

    def _serializer(self):
        s = MagicMock()
        s.save.return_value = MagicMock()
        return s

    def test_no_plan_limit_saves_without_error(self):
        """When plan.max_dishes is None/0, no limit is enforced."""
        vs = self._make_viewset()
        ser = self._serializer()
        with patch("django_tenants.utils.get_public_schema_name", return_value="public"):
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                with patch("tenancy.models.Plan") as mock_plan:
                    mock_plan.objects.filter.return_value.values_list.return_value.first.return_value = 0
                    with patch("menu.views.Dish") as mock_dish:
                        mock_dish.objects.count.return_value = 5
                        vs.perform_create(ser)
        ser.save.assert_called_once()

    def test_under_limit_saves_normally(self):
        vs = self._make_viewset()
        ser = self._serializer()
        with patch("django_tenants.utils.get_public_schema_name", return_value="public"):
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                with patch("tenancy.models.Plan") as mock_plan:
                    mock_plan.objects.filter.return_value.values_list.return_value.first.return_value = 50
                    with patch("menu.views.Dish") as mock_dish:
                        mock_dish.objects.count.return_value = 10  # under limit
                        vs.perform_create(ser)
        ser.save.assert_called_once()

    def test_at_limit_raises_validation_error(self):
        from rest_framework.exceptions import ValidationError
        vs = self._make_viewset()
        ser = self._serializer()
        # OPS-5b: perform_create now uses select_for_update() + transaction.atomic().
        # Patch atomic to act as a no-op context manager so the limit check runs
        # without a real DB (SimpleTestCase).  Plan mock chain updated accordingly.
        plan_obj = MagicMock()
        plan_obj.max_dishes = 10
        with patch("django.db.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__enter__ = lambda s: None
            mock_atomic.return_value.__exit__ = lambda s, *a: False
            with patch("django_tenants.utils.get_public_schema_name", return_value="public"):
                with patch("django_tenants.utils.schema_context") as mock_sc:
                    mock_sc.return_value.__enter__ = lambda s: None
                    mock_sc.return_value.__exit__ = lambda s, *a: None
                    with patch("tenancy.models.Plan") as mock_plan:
                        mock_plan.objects.select_for_update.return_value.filter.return_value.first.return_value = plan_obj
                        with patch("menu.views.Dish") as mock_dish:
                            mock_dish.objects.count.return_value = 10  # at limit
                            with self.assertRaises(ValidationError) as ctx:
                                vs.perform_create(ser)
        self.assertEqual(ctx.exception.detail["code"], "dish_limit_reached")
        ser.save.assert_not_called()

    def test_no_tenant_saves_without_limit_check(self):
        """No tenant on request → skip limit check entirely."""
        vs = DishViewSet()
        vs.request = SimpleNamespace(tenant=None, user=_owner())
        ser = self._serializer()
        vs.perform_create(ser)
        ser.save.assert_called_once()


# ── DishViewSet – cache busting (B2) ───────────────────────────────────────────
# DishViewSet.perform_create/perform_update call serializer.save() directly
# (bypassing PublishAccessMixin's super().perform_create/update), so they must
# explicitly bust the menu cache themselves — otherwise newly-created/edited
# dishes stay invisible to anonymous customers for up to 60s after being
# published (menu_ver per-slug cache).

class DishViewSetCacheBustTests(SimpleTestCase):
    def _make_viewset(self, tenant=None):
        vs = DishViewSet()
        vs.request = SimpleNamespace(
            tenant=tenant or _tenant(),
            user=_owner(),
        )
        return vs

    def _serializer(self, validated_data=None):
        s = MagicMock()
        s.save.return_value = MagicMock()
        s.validated_data = validated_data or {}
        return s

    def test_perform_create_busts_cache_no_tenant_limit_path(self):
        """No tenant on request → falls to the plain serializer.save() path, which
        must still bust the cache."""
        vs = DishViewSet()
        vs.request = SimpleNamespace(tenant=None, user=_owner())
        ser = self._serializer()
        with patch("menu.views._bust_menu_cache") as mock_bust:
            vs.perform_create(ser)
        ser.save.assert_called_once()
        # No tenant → _bust_current_tenant_menu_cache() finds no tenant and no-ops.
        mock_bust.assert_not_called()

    def test_perform_create_busts_cache_with_tenant(self):
        vs = self._make_viewset(tenant=_tenant(tenant_id=1))
        ser = self._serializer()
        with patch("django_tenants.utils.get_public_schema_name", return_value="public"):
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                with patch("tenancy.models.Plan") as mock_plan:
                    mock_plan.objects.select_for_update.return_value.filter.return_value.first.return_value = None
                    with patch("menu.views.Dish") as mock_dish:
                        mock_dish.objects.count.return_value = 0
                        with patch("menu.views._bust_menu_cache") as mock_bust:
                            vs.perform_create(ser)
        ser.save.assert_called_once()
        mock_bust.assert_called_once_with("restaurant")

    def test_perform_update_busts_cache(self):
        vs = self._make_viewset(tenant=_tenant(tenant_id=1))
        ser = self._serializer(validated_data={})
        with patch("django.db.transaction.atomic", _noop_atomic):
            with patch("menu.views._bust_menu_cache") as mock_bust:
                vs.perform_update(ser)
        ser.save.assert_called_once()
        mock_bust.assert_called_once_with("restaurant")

    def test_perform_update_with_stock_qty_still_busts_cache(self):
        instance = MagicMock(pk=7)
        vs = self._make_viewset(tenant=_tenant(tenant_id=1))
        ser = self._serializer(validated_data={"stock_qty": 5})
        ser.save.return_value = instance
        with patch("django.db.transaction.atomic", _noop_atomic):
            with patch("menu.views.Dish") as mock_dish:
                with patch("menu.views._bust_menu_cache") as mock_bust:
                    vs.perform_update(ser)
        mock_dish.objects.filter.assert_called_once_with(pk=7)
        mock_dish.objects.filter.return_value.update.assert_called_once_with(stock_auto_zeroed=False)
        mock_bust.assert_called_once_with("restaurant")


# ── DishViewSet.destroy – combo-component 409 (not a bare 500) ────────────────

class DishViewSetDestroyComboProtectionTests(SimpleTestCase):
    """A dish that is a combo component is PROTECTed; destroy() must translate
    the resulting ProtectedError/RestrictedError into a clean 409, not a 500."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DishViewSet.as_view({"delete": "destroy"})

    def _delete(self, instance, side_effect):
        req = self.factory.delete("/api/dishes/1/")
        req.user = _owner(tenant_id=1)
        req.tenant = _tenant(tenant_id=1)
        with patch.object(DishViewSet, "get_object", return_value=instance):
            with patch.object(DishViewSet, "perform_destroy", side_effect=side_effect):
                return self.view(req, pk=1)

    def test_protected_error_returns_409_not_500(self):
        from django.db.models import ProtectedError
        combo_cc = MagicMock()
        combo_cc.dish.name = "Burger Combo"
        instance = MagicMock()
        instance.name = "Fries"
        instance.part_of_combos.select_related.return_value.first.return_value = combo_cc
        resp = self._delete(instance, ProtectedError("protected", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "dish_is_combo_component")
        self.assertIn("Burger Combo", resp.data["detail"])

    def test_restricted_error_returns_409_not_500(self):
        from django.db.models import RestrictedError
        instance = MagicMock()
        instance.name = "Fries"
        instance.part_of_combos.select_related.return_value.first.return_value = None
        resp = self._delete(instance, RestrictedError("restricted", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "dish_is_combo_component")

    def test_normal_delete_returns_204(self):
        instance = MagicMock()
        instance.name = "Fries"
        resp = self._delete(instance, None)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


# ── IsTenantEditorOrReadOnly – write access ───────────────────────────────────

class MenuViewSetWritePermissionTests(SimpleTestCase):
    """POST/PUT/PATCH requires authenticated tenant owner/staff."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CategoryViewSet.as_view({"post": "create"})

    def _post(self, user=None, tenant=None):
        req = self.factory.post("/api/categories/", {"name": "Mains"}, format="json")
        req.user = user or _anon()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_anonymous_post_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_from_different_tenant_returns_403(self):
        resp = self._post(
            user=_owner(tenant_id=99),
            tenant=_tenant(tenant_id=1),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_with_correct_tenant_gets_past_permission(self):
        """Owner passes permission check; gets 400 from missing serializer data."""
        with patch("menu.views.Category") as mock_cat:
            mock_cat.objects.select_related.return_value.prefetch_related.return_value.all.return_value.order_by.return_value = \
                _make_qs()
            with patch("menu.views.CategorySerializer") as mock_ser:
                instance = mock_ser.return_value
                instance.is_valid.return_value = False
                instance.errors = {"name": ["required"]}
                resp = self._post(
                    user=_owner(tenant_id=1),
                    tenant=_tenant(tenant_id=1),
                )
        # Got past permission check
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── CategoryViewSet.destroy – combo-component 409 (B5) ────────────────────────
# Category.dishes is on_delete=CASCADE, so deleting a category that contains a
# combo-referenced dish cascades into the same ComboComponent.component
# on_delete=PROTECT that DishViewSet.destroy already handles. Before this fix,
# CategoryViewSet had no destroy() override, so the ProtectedError propagated
# as a bare 500 instead of a clean 409.

class CategoryViewSetDestroyComboProtectionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CategoryViewSet.as_view({"delete": "destroy"})

    def _delete(self, instance, side_effect):
        req = self.factory.delete("/api/categories/1/")
        req.user = _owner(tenant_id=1)
        req.tenant = _tenant(tenant_id=1)
        with patch.object(CategoryViewSet, "get_object", return_value=instance):
            with patch.object(CategoryViewSet, "perform_destroy", side_effect=side_effect):
                return self.view(req, pk=1)

    def test_protected_error_returns_409_not_500(self):
        from django.db.models import ProtectedError
        combo_cc = MagicMock()
        combo_cc.dish.name = "Burger Combo"
        blocked_dish = MagicMock()
        blocked_dish.name = "Fries"
        blocked_dish.part_of_combos.select_related.return_value.first.return_value = combo_cc
        instance = MagicMock()
        instance.name = "Sides"
        instance.dishes.filter.return_value.first.return_value = blocked_dish
        resp = self._delete(instance, ProtectedError("protected", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "category_has_combo_component")
        self.assertIn("Fries", resp.data["detail"])
        self.assertIn("Burger Combo", resp.data["detail"])

    def test_restricted_error_returns_409_not_500(self):
        from django.db.models import RestrictedError
        instance = MagicMock()
        instance.name = "Sides"
        instance.dishes.filter.return_value.first.return_value = None
        resp = self._delete(instance, RestrictedError("restricted", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "category_has_combo_component")

    def test_normal_delete_returns_204(self):
        instance = MagicMock()
        instance.name = "Sides"
        resp = self._delete(instance, None)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


# ── SuperCategoryViewSet.destroy – combo-component 409 (B5) ───────────────────
# SuperCategory.categories and Category.dishes are both on_delete=CASCADE, so
# deleting a super-category that (transitively) contains a combo-referenced
# dish hits the same PROTECT. SuperCategoryViewSet had no destroy() override
# either, so this also 500'd before this fix.

class SuperCategoryViewSetDestroyComboProtectionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SuperCategoryViewSet.as_view({"delete": "destroy"})

    def _delete(self, instance, side_effect):
        req = self.factory.delete("/api/super-categories/1/")
        req.user = _owner(tenant_id=1)
        req.tenant = _tenant(tenant_id=1)
        with patch.object(SuperCategoryViewSet, "get_object", return_value=instance):
            with patch.object(SuperCategoryViewSet, "perform_destroy", side_effect=side_effect):
                return self.view(req, pk=1)

    def test_protected_error_returns_409_not_500(self):
        from django.db.models import ProtectedError
        combo_cc = MagicMock()
        combo_cc.dish.name = "Burger Combo"
        blocked_dish = MagicMock()
        blocked_dish.name = "Fries"
        blocked_dish.part_of_combos.select_related.return_value.first.return_value = combo_cc
        instance = MagicMock()
        instance.name = "Menu"
        with patch("menu.views.Dish") as mock_dish:
            mock_dish.objects.filter.return_value.first.return_value = blocked_dish
            resp = self._delete(instance, ProtectedError("protected", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "super_category_has_combo_component")
        self.assertIn("Fries", resp.data["detail"])
        self.assertIn("Burger Combo", resp.data["detail"])

    def test_restricted_error_returns_409_not_500(self):
        from django.db.models import RestrictedError
        instance = MagicMock()
        instance.name = "Menu"
        with patch("menu.views.Dish") as mock_dish:
            mock_dish.objects.filter.return_value.first.return_value = None
            resp = self._delete(instance, RestrictedError("restricted", set()))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "super_category_has_combo_component")

    def test_normal_delete_returns_204(self):
        instance = MagicMock()
        instance.name = "Menu"
        resp = self._delete(instance, None)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


# ── OptionGroupViewSet – cache busting ───────────────────────────────────────

class OptionGroupViewSetCacheBustTests(SimpleTestCase):
    """perform_create/update/destroy each call _bust() → _bust_menu_cache."""

    def _make_viewset(self, tenant=None):
        vs = OptionGroupViewSet()
        vs.request = SimpleNamespace(
            tenant=tenant or _tenant(),
            user=_owner(),
        )
        return vs

    def test_perform_create_busts_cache(self):
        vs = self._make_viewset()
        ser = MagicMock()
        with patch("menu.views._bust_menu_cache") as mock_bust:
            with patch.object(OptionGroupViewSet, "perform_create", wraps=vs.perform_create):
                # Call the real perform_create (which calls super then _bust)
                with patch("rest_framework.mixins.CreateModelMixin.perform_create"):
                    vs.perform_create(ser)
        mock_bust.assert_called_once_with("restaurant")

    def test_perform_update_busts_cache(self):
        vs = self._make_viewset()
        ser = MagicMock()
        with patch("menu.views._bust_menu_cache") as mock_bust:
            with patch("rest_framework.mixins.UpdateModelMixin.perform_update"):
                vs.perform_update(ser)
        mock_bust.assert_called_once_with("restaurant")

    def test_perform_destroy_busts_cache(self):
        vs = self._make_viewset()
        instance = MagicMock()
        with patch("menu.views._bust_menu_cache") as mock_bust:
            with patch("rest_framework.mixins.DestroyModelMixin.perform_destroy"):
                vs.perform_destroy(instance)
        mock_bust.assert_called_once_with("restaurant")

    def test_no_tenant_does_not_bust(self):
        vs = self._make_viewset(tenant=None)
        vs.request = SimpleNamespace(tenant=None, user=_owner())
        ser = MagicMock()
        with patch("menu.views._bust_menu_cache") as mock_bust:
            with patch("rest_framework.mixins.CreateModelMixin.perform_create"):
                vs.perform_create(ser)
        mock_bust.assert_not_called()


# ── PublishAccessMixin._auto_unpublish_if_menu_empty (B3) ─────────────────────
# Deleting the last published dish/category left is_menu_published stuck True
# (ProfileSerializer only checks category/dish counts when *turning on*
# publish). This mirrors that exact check (0 published categories OR 0
# published dishes) after a delete and flips the flag back off.

class AutoUnpublishIfMenuEmptyTests(SimpleTestCase):
    def _make_viewset(self, tenant=None, profile=None):
        vs = DishViewSet()
        vs.request = SimpleNamespace(tenant=tenant or _tenant(), user=_owner())
        vs._cached_profile = profile
        return vs

    def test_deleting_last_dish_flips_is_menu_published_false(self):
        """Menu now empty (0 dishes) + was published → flips to False and notifies."""
        profile = _profile(is_menu_published=True)
        profile.published_at = "2026-01-01T00:00:00Z"
        vs = self._make_viewset(profile=profile)

        with patch("menu.views.Category") as mock_cat, patch("menu.views.Dish") as mock_dish:
            mock_cat.objects.filter.return_value.count.return_value = 1
            mock_dish.objects.filter.return_value.count.return_value = 0  # last dish gone
            with patch.object(DishViewSet, "_notify_owner_menu_auto_unpublished") as mock_notify:
                vs._auto_unpublish_if_menu_empty()

        self.assertFalse(profile.is_menu_published)
        self.assertIsNone(profile.published_at)
        profile.save.assert_called_once_with(update_fields=["is_menu_published", "published_at"])
        mock_notify.assert_called_once_with(profile)

    def test_deleting_last_category_flips_is_menu_published_false(self):
        """Menu now empty (0 categories) + was published → flips to False."""
        profile = _profile(is_menu_published=True)
        profile.published_at = "2026-01-01T00:00:00Z"
        vs = self._make_viewset(profile=profile)

        with patch("menu.views.Category") as mock_cat, patch("menu.views.Dish") as mock_dish:
            mock_cat.objects.filter.return_value.count.return_value = 0  # last category gone
            mock_dish.objects.filter.return_value.count.return_value = 0
            with patch.object(DishViewSet, "_notify_owner_menu_auto_unpublished"):
                vs._auto_unpublish_if_menu_empty()

        self.assertFalse(profile.is_menu_published)
        profile.save.assert_called_once_with(update_fields=["is_menu_published", "published_at"])

    def test_deleting_a_non_last_dish_leaves_published_true(self):
        """Menu still has >=1 category and >=1 dish → no flip, no save."""
        profile = _profile(is_menu_published=True)
        vs = self._make_viewset(profile=profile)

        with patch("menu.views.Category") as mock_cat, patch("menu.views.Dish") as mock_dish:
            mock_cat.objects.filter.return_value.count.return_value = 2
            mock_dish.objects.filter.return_value.count.return_value = 3
            with patch.object(DishViewSet, "_notify_owner_menu_auto_unpublished") as mock_notify:
                vs._auto_unpublish_if_menu_empty()

        self.assertTrue(profile.is_menu_published)
        profile.save.assert_not_called()
        mock_notify.assert_not_called()

    def test_already_unpublished_tenant_is_untouched(self):
        """Profile already has is_menu_published=False → no-op regardless of counts."""
        profile = _profile(is_menu_published=False)
        vs = self._make_viewset(profile=profile)

        with patch("menu.views.Category") as mock_cat, patch("menu.views.Dish") as mock_dish:
            vs._auto_unpublish_if_menu_empty()
            mock_cat.objects.filter.assert_not_called()
            mock_dish.objects.filter.assert_not_called()

        self.assertFalse(profile.is_menu_published)
        profile.save.assert_not_called()

    def test_no_profile_is_a_safe_noop(self):
        vs = self._make_viewset(profile=None)
        with patch("menu.views.Category") as mock_cat, patch("menu.views.Dish") as mock_dish:
            vs._auto_unpublish_if_menu_empty()
            mock_cat.objects.filter.assert_not_called()
            mock_dish.objects.filter.assert_not_called()

    def test_db_error_is_swallowed_not_raised(self):
        """Under SimpleTestCase-style callers with no real DB, any exception from the
        profile/count queries must be swallowed — this is a best-effort side-effect
        that must never break the primary delete response."""
        vs = self._make_viewset(tenant=_tenant())
        vs._cached_profile = None
        with patch.object(DishViewSet, "_profile", side_effect=RuntimeError("db down")):
            vs._auto_unpublish_if_menu_empty()  # must not raise


class DestroyCallsAutoUnpublishTests(SimpleTestCase):
    """destroy() on all three menu ViewSets calls the B3 check exactly once on the
    success path, after perform_destroy succeeds and before returning 204."""

    def _delete(self, viewset_cls, instance):
        factory = APIRequestFactory()
        req = factory.delete("/api/x/1/")
        req.user = _owner(tenant_id=1)
        req.tenant = _tenant(tenant_id=1)
        view = viewset_cls.as_view({"delete": "destroy"})
        with patch.object(viewset_cls, "get_object", return_value=instance):
            with patch.object(viewset_cls, "perform_destroy", return_value=None):
                with patch.object(viewset_cls, "_auto_unpublish_if_menu_empty") as mock_check:
                    resp = view(req, pk=1)
        return resp, mock_check

    def test_dish_destroy_calls_check(self):
        instance = MagicMock()
        instance.name = "Fries"
        resp, mock_check = self._delete(DishViewSet, instance)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_check.assert_called_once()

    def test_category_destroy_calls_check(self):
        instance = MagicMock()
        instance.name = "Sides"
        resp, mock_check = self._delete(CategoryViewSet, instance)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_check.assert_called_once()

    def test_super_category_destroy_calls_check(self):
        instance = MagicMock()
        instance.name = "Menu"
        resp, mock_check = self._delete(SuperCategoryViewSet, instance)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        mock_check.assert_called_once()
