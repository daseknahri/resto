"""
Tests for the menu ViewSets and their shared PublishAccessMixin logic:
  - SuperCategoryViewSet
  - CategoryViewSet
  - DishViewSet   (including perform_create dish-limit gate)
  - DishOptionViewSet
  - OptionGroupViewSet  (including cache-bust)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import (
    CategoryViewSet,
    DishOptionViewSet,
    DishViewSet,
    OptionGroupViewSet,
    SuperCategoryViewSet,
)


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
        with patch("django_tenants.utils.get_public_schema_name", return_value="public"):
            with patch("django_tenants.utils.schema_context") as mock_sc:
                mock_sc.return_value.__enter__ = lambda s: None
                mock_sc.return_value.__exit__ = lambda s, *a: None
                with patch("tenancy.models.Plan") as mock_plan:
                    mock_plan.objects.filter.return_value.values_list.return_value.first.return_value = 10
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
