"""
OPS-6 backend tests (SimpleTestCase + mocks — no real DB).

Covers:
  - StaffChangePasswordView  POST /api/staff/change-password/
  - CategorySerializer.dish_count  (menu/serializers.py)
  - ProfileSerializer.publish_warnings  (tenancy/serializers.py)
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import StaffChangePasswordView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(is_authenticated=True, password_ok=True):
    """Return a mock User for staff/owner."""
    u = MagicMock()
    u.is_authenticated = is_authenticated
    u.check_password = MagicMock(return_value=password_ok)
    u.set_password = MagicMock()
    u.save = MagicMock()
    return u


# ── StaffChangePasswordView ───────────────────────────────────────────────────

class StaffChangePasswordViewTests(SimpleTestCase):
    """POST /api/staff/change-password/"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffChangePasswordView.as_view()
        # The view now declares a per-user throttle (StaffChangePasswordThrottle).
        # Clear the throttle bucket between tests so independent cases never bleed
        # into one another's rate-limit window.
        from django.core.cache import cache
        cache.clear()

    def _make_uid_user(self, **kwargs):
        """Like _make_user but with a deterministic pk so the per-user throttle
        keys are stable/distinct within a test."""
        u = _make_user(**kwargs)
        u.pk = id(u)
        return u

    def _post(self, data, user=None):
        req = self.factory.post("/api/staff/change-password/", data, format="json")
        req.user = user or self._make_uid_user()
        return self.view(req)

    # ── Auth guard ────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        """DRF IsAuthenticated returns 403 when credentials are absent but not
        rejected by an authenticator (the test factory provides no session)."""
        u = MagicMock()
        u.is_authenticated = False
        resp = self._post({}, user=u)
        # DRF returns 403 for IsAuthenticated when no authenticator ran (not 401)
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_current_password_returns_400(self):
        resp = self._post({"new_password": "Str0ngPass!"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "current_password_required")

    def test_missing_new_password_returns_400(self):
        resp = self._post({"current_password": "OldPass123"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "new_password_required")

    def test_wrong_current_password_returns_400(self):
        user = _make_user(password_ok=False)
        resp = self._post({"current_password": "WrongPass", "new_password": "Str0ngPass!"}, user=user)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "wrong_current_password")
        user.set_password.assert_not_called()

    def test_weak_new_password_returns_400(self):
        """Django AUTH_PASSWORD_VALIDATORS must be applied.

        We patch validate_password at module level in accounts.views so the test
        does not depend on the project's specific validator configuration.
        """
        from django.core.exceptions import ValidationError as DVE
        user = _make_user(password_ok=True)
        with patch(
            "accounts.views.validate_password",
            side_effect=DVE(["This password is too short."]),
        ):
            resp = self._post(
                {"current_password": "OldPass123", "new_password": "abc"},
                user=user,
            )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "password_too_weak")
        user.set_password.assert_not_called()

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_happy_path_changes_password_and_returns_200(self):
        """Valid payload: password changed, session kept alive, 200 returned."""
        user = _make_user(password_ok=True)
        with patch("accounts.views.validate_password") as mock_validate, \
             patch("accounts.views._update_session_auth_hash") as mock_update_session:
            mock_validate.return_value = None  # no error = strong enough
            resp = self._post(
                {"current_password": "OldPass123", "new_password": "Str0ngNewPass!9"},
                user=user,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.set_password.assert_called_once_with("Str0ngNewPass!9")
        user.save.assert_called_once_with(update_fields=["password"])
        mock_update_session.assert_called_once()

    def test_happy_path_strips_whitespace_from_passwords(self):
        """Leading/trailing whitespace in form data must be stripped before use."""
        user = _make_user(password_ok=True)
        with patch("accounts.views.validate_password") as mock_validate, \
             patch("accounts.views._update_session_auth_hash"):
            mock_validate.return_value = None
            resp = self._post(
                {"current_password": "  OldPass123  ", "new_password": "  Str0ngNewPass!9  "},
                user=user,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # set_password must receive the stripped value
        user.set_password.assert_called_once_with("Str0ngNewPass!9")

    # ── Throttle (OPS-6: brute-force backstop on the current-password check) ────

    def test_view_declares_staff_change_password_throttle(self):
        """throttle_classes must include StaffChangePasswordThrottle (scope
        'staff_change_password') so a session-holder cannot brute-force the
        current-password check."""
        from accounts.throttles import StaffChangePasswordThrottle

        throttles = StaffChangePasswordView.throttle_classes
        self.assertIn(StaffChangePasswordThrottle, throttles)
        scopes = [t.scope for t in throttles if hasattr(t, "scope")]
        self.assertIn("staff_change_password", scopes)

    def test_throttle_cache_key_keyed_on_user_pk(self):
        """get_cache_key must bucket per authenticated user (pk in the key)."""
        from accounts.throttles import StaffChangePasswordThrottle

        throttle = StaffChangePasswordThrottle()
        req = SimpleNamespace(
            META={},
            user=SimpleNamespace(is_authenticated=True, pk=42, id=42),
        )
        key = throttle.get_cache_key(req, None)
        self.assertIsNotNone(key)
        self.assertIn("42", key)
        self.assertIn("staff_change_password", key)

    def test_throttle_cache_key_falls_back_to_ip_when_unauthenticated(self):
        """Unauthenticated requests fall back to an IP-based key (defensive — the
        view also requires auth, but the throttle class must be safe alone)."""
        from accounts.throttles import StaffChangePasswordThrottle

        throttle = StaffChangePasswordThrottle()
        req = SimpleNamespace(
            META={"REMOTE_ADDR": "203.0.113.7"},
            user=SimpleNamespace(is_authenticated=False, pk=None),
        )
        key = throttle.get_cache_key(req, None)
        self.assertIsNotNone(key)
        self.assertIn("203.0.113.7", key)

    def test_distinct_users_get_distinct_buckets(self):
        """Two different users must not share a throttle bucket."""
        from accounts.throttles import StaffChangePasswordThrottle

        throttle = StaffChangePasswordThrottle()
        key_a = throttle.get_cache_key(
            SimpleNamespace(META={}, user=SimpleNamespace(is_authenticated=True, pk=1, id=1)),
            None,
        )
        key_b = throttle.get_cache_key(
            SimpleNamespace(META={}, user=SimpleNamespace(is_authenticated=True, pk=2, id=2)),
            None,
        )
        self.assertNotEqual(key_a, key_b)


# ── CategorySerializer.dish_count ────────────────────────────────────────────

class CategorySerializerDishCountTests(SimpleTestCase):
    """dish_count is derived from the prefetched dishes cache; no extra DB query."""

    def _make_category(self, dishes=None, prefetched=True):
        """Return a mock Category instance."""
        category = MagicMock()
        dish_list = dishes or []
        if prefetched:
            # Simulate the Django prefetch cache (_prefetched_objects_cache)
            category._prefetched_objects_cache = {"dishes": dish_list}
        else:
            # No prefetch cache — fall back to .count()
            del category._prefetched_objects_cache
            category.dishes.count.return_value = len(dish_list)
        return category

    def _get_dish_count(self, category):
        from menu.serializers import CategorySerializer
        ser = CategorySerializer()
        return ser.get_dish_count(category)

    def test_returns_count_from_prefetch_cache(self):
        dishes = [MagicMock(), MagicMock(), MagicMock()]
        cat = self._make_category(dishes=dishes, prefetched=True)
        self.assertEqual(self._get_dish_count(cat), 3)

    def test_returns_zero_for_empty_prefetch_cache(self):
        cat = self._make_category(dishes=[], prefetched=True)
        self.assertEqual(self._get_dish_count(cat), 0)

    def test_falls_back_to_db_count_when_cache_key_absent(self):
        """When the prefetch cache exists but the 'dishes' key is absent,
        fall back to the DB count via .dishes.count()."""
        cat = self._make_category(dishes=[MagicMock()], prefetched=False)
        cat._prefetched_objects_cache = {}  # cache exists but key absent
        cat.dishes.count.return_value = 7
        self.assertEqual(self._get_dish_count(cat), 7)


# ── _get_publish_warnings (tenancy/serializers.py) ───────────────────────────

class PublishWarningsTests(SimpleTestCase):
    """_get_publish_warnings is a module-level helper — test it directly.

    The helper is extracted from ProfileSerializer.to_representation so it can
    be unit-tested without the full DRF serializer machinery.
    """

    def _call(self, is_menu_published, zero_price_count):
        """Call _get_publish_warnings with a mocked profile and patched ORM."""
        from tenancy.serializers import _get_publish_warnings
        import menu.models as _menu

        profile = SimpleNamespace(is_menu_published=is_menu_published)

        with patch.object(_menu.Dish, "objects") as dish_obj:
            dish_obj.filter.return_value.count.return_value = zero_price_count
            return _get_publish_warnings(profile)

    def test_no_warnings_when_menu_not_published(self):
        warnings = self._call(is_menu_published=False, zero_price_count=5)
        self.assertEqual(warnings, [])

    def test_no_warnings_when_published_and_no_zero_price_dishes(self):
        warnings = self._call(is_menu_published=True, zero_price_count=0)
        self.assertEqual(warnings, [])

    def test_warning_emitted_when_published_with_zero_price_dishes(self):
        warnings = self._call(is_menu_published=True, zero_price_count=3)
        self.assertEqual(len(warnings), 1)
        w = warnings[0]
        self.assertEqual(w["code"], "zero_price_dishes")
        self.assertEqual(w["count"], 3)
        self.assertIn("3", w["message"])

    def test_warning_uses_singular_for_one_dish(self):
        warnings = self._call(is_menu_published=True, zero_price_count=1)
        self.assertEqual(len(warnings), 1)
        self.assertIn("1 published dish has", warnings[0]["message"])

    def test_returns_empty_list_on_orm_exception(self):
        """ORM failures must be silently swallowed — never break the GET profile."""
        from tenancy.serializers import _get_publish_warnings
        import menu.models as _menu

        profile = SimpleNamespace(is_menu_published=True)
        with patch.object(_menu.Dish, "objects") as dish_obj:
            dish_obj.filter.side_effect = RuntimeError("DB down")
            result = _get_publish_warnings(profile)
        self.assertEqual(result, [])
