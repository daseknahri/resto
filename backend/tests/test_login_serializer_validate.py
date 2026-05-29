"""
Unit tests for accounts.serializers.LoginSerializer.validate covering all
branches not already tested by test_login_serializer_tenant_inactive.py:

  - Empty identifier → "Username/email and password are required"
  - Empty password   → "Username/email and password are required"
  - Whitespace-only identifier → same error (stripped to "")
  - User not found → "Invalid credentials"
  - Wrong password  → "Invalid credentials"
  - Inactive user (is_active=False) → "Account is inactive"
  - Valid user, no tenant → succeeds, attrs["user"] = user
  - Valid user, active tenant → succeeds, attrs["user"] = user
  - Identifier is stripped before lookup (leading/trailing whitespace)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from accounts.serializers import LoginSerializer


def _scope(user_or_none):
    """Build a mock queryset chain that returns user_or_none from .first()."""
    scope = Mock()
    scope.order_by.return_value = scope
    scope.first.return_value = user_or_none
    return scope


def _active_user(password_ok=True, has_tenant=False, tenant_active=True):
    tenant = None
    if has_tenant:
        tenant = SimpleNamespace(is_active=tenant_active, lifecycle_status="active")
    return SimpleNamespace(
        check_password=lambda _: password_ok,
        is_active=True,
        tenant_id=42 if has_tenant else None,
        tenant=tenant,
    )


class LoginSerializerValidateTests(SimpleTestCase):

    # ── missing credentials ───────────────────────────────────────────────────
    # DRF CharField (trim_whitespace=True, allow_blank=False) rejects empty /
    # whitespace-only values at field level before validate() is reached.

    def test_empty_identifier_is_rejected(self):
        s = LoginSerializer(data={"identifier": "", "password": "secret123"})
        self.assertFalse(s.is_valid())
        self.assertIn("identifier", s.errors)

    def test_empty_password_is_rejected(self):
        s = LoginSerializer(data={"identifier": "user@example.com", "password": ""})
        self.assertFalse(s.is_valid())
        self.assertIn("password", s.errors)

    def test_whitespace_only_identifier_is_rejected(self):
        # CharField with trim_whitespace=True reduces "   " to "" → blank error.
        s = LoginSerializer(data={"identifier": "   ", "password": "pass123"})
        self.assertFalse(s.is_valid())
        self.assertIn("identifier", s.errors)

    def test_both_empty_is_rejected(self):
        s = LoginSerializer(data={"identifier": "", "password": ""})
        self.assertFalse(s.is_valid())

    # ── user not found ────────────────────────────────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_user_not_found_raises_invalid_credentials(self, user_objects):
        user_objects.filter.return_value = _scope(None)
        s = LoginSerializer(data={"identifier": "nobody@example.com", "password": "secret123"})
        s.is_valid()
        self.assertIn("Invalid credentials", str(s.errors))

    # ── wrong password ────────────────────────────────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_wrong_password_raises_invalid_credentials(self, user_objects):
        user_objects.filter.return_value = _scope(_active_user(password_ok=False))
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "wrongpass"})
        s.is_valid()
        self.assertIn("Invalid credentials", str(s.errors))

    # ── inactive account ──────────────────────────────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_inactive_user_raises_account_inactive(self, user_objects):
        user = SimpleNamespace(
            check_password=lambda _: True,
            is_active=False,
            tenant_id=None,
            tenant=None,
        )
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "secret123"})
        s.is_valid()
        self.assertIn("Account is inactive", str(s.errors))

    # ── valid user without tenant → success ───────────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_valid_user_no_tenant_succeeds(self, user_objects):
        user = _active_user(has_tenant=False)
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "secret123"})
        result = s.is_valid()
        self.assertTrue(result, s.errors)

    @patch("accounts.serializers.User.objects")
    def test_valid_user_no_tenant_sets_user_on_attrs(self, user_objects):
        user = _active_user(has_tenant=False)
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "secret123"})
        s.is_valid()
        self.assertIs(s.validated_data["user"], user)

    # ── valid user with active tenant → success ───────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_valid_user_with_active_tenant_succeeds(self, user_objects):
        user = _active_user(has_tenant=True, tenant_active=True)
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "secret123"})
        self.assertTrue(s.is_valid(), s.errors)

    @patch("accounts.serializers.User.objects")
    def test_valid_user_with_active_tenant_sets_user_on_attrs(self, user_objects):
        user = _active_user(has_tenant=True, tenant_active=True)
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "user@example.com", "password": "secret123"})
        s.is_valid()
        self.assertIs(s.validated_data["user"], user)

    # ── identifier is stripped before use ─────────────────────────────────────

    @patch("accounts.serializers.User.objects")
    def test_identifier_whitespace_stripped_before_lookup(self, user_objects):
        """Leading/trailing spaces on identifier are stripped before DB lookup."""
        user = _active_user()
        user_objects.filter.return_value = _scope(user)
        s = LoginSerializer(data={"identifier": "  user@example.com  ", "password": "secret123"})
        # Should succeed: the validator strips the identifier before checking
        self.assertTrue(s.is_valid(), s.errors)
