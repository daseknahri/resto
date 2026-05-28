"""
Unit tests for three private helper functions in sales/services.py that are
never directly called in existing tests (only via the higher-level
onboarding_package_for_lead which is always mocked away):

  _get_latest_provisioning_job(lead)
    Returns the most-recent successful ProvisioningJob or raises ValueError.

  _get_tenant_owner_user(tenant)
    Returns the TENANT_OWNER user; falls back to any user; raises ValueError.

  _get_reusable_activation_token(user, tenant)
    Returns a non-expired, unused ActivationToken or None.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from sales.services import (
    _get_latest_provisioning_job,
    _get_tenant_owner_user,
    _get_reusable_activation_token,
)


# ══════════════════════════════════════════════════════════════════════════════
# _get_latest_provisioning_job
# ══════════════════════════════════════════════════════════════════════════════

def _make_job(tenant=None):
    return SimpleNamespace(tenant=tenant)


def _queryset_returning(value):
    """Build a mock queryset chain that returns `value` from .first()."""
    qs = MagicMock()
    qs.filter.return_value.select_related.return_value.order_by.return_value.first.return_value = value
    return qs


class GetLatestProvisioningJobTests(SimpleTestCase):
    """_get_latest_provisioning_job: returns job with tenant or raises ValueError."""

    def test_returns_job_when_found_with_tenant(self):
        mock_tenant = SimpleNamespace(id=1, slug="demo")
        job = _make_job(tenant=mock_tenant)
        with patch("sales.services.ProvisioningJob") as mock_pj:
            mock_pj.objects = _queryset_returning(job)
            result = _get_latest_provisioning_job(lead=SimpleNamespace(id=10))
        self.assertIs(result, job)

    def test_raises_value_error_when_no_job_found(self):
        with patch("sales.services.ProvisioningJob") as mock_pj:
            mock_pj.objects = _queryset_returning(None)  # queryset.first() → None
            with self.assertRaises(ValueError):
                _get_latest_provisioning_job(lead=SimpleNamespace(id=10))

    def test_raises_value_error_when_job_has_no_tenant(self):
        """Job exists but job.tenant is None → still raises."""
        job = _make_job(tenant=None)
        with patch("sales.services.ProvisioningJob") as mock_pj:
            mock_pj.objects = _queryset_returning(job)
            with self.assertRaises(ValueError):
                _get_latest_provisioning_job(lead=SimpleNamespace(id=10))

    def test_error_message_mentions_tenant(self):
        with patch("sales.services.ProvisioningJob") as mock_pj:
            mock_pj.objects = _queryset_returning(None)
            with self.assertRaises(ValueError) as cm:
                _get_latest_provisioning_job(lead=SimpleNamespace(id=10))
        self.assertIn("tenant", str(cm.exception).lower())


# ══════════════════════════════════════════════════════════════════════════════
# _get_tenant_owner_user
# ══════════════════════════════════════════════════════════════════════════════

def _make_tenant_with_users(*, owner_user=None, any_user=None):
    """
    Build a fake tenant whose `.users` manager returns owner_user from
    filter(...).order_by("id").first(), and any_user from
    order_by("id").first() (the fallback query).
    """
    users_mgr = MagicMock()
    # Filtered query (role = TENANT_OWNER)
    users_mgr.filter.return_value.order_by.return_value.first.return_value = owner_user
    # Unfiltered fallback query
    users_mgr.order_by.return_value.first.return_value = any_user
    return SimpleNamespace(users=users_mgr)


class GetTenantOwnerUserTests(SimpleTestCase):
    """_get_tenant_owner_user: prioritises owner role; falls back; raises if empty."""

    def test_returns_owner_user_when_found(self):
        owner = SimpleNamespace(pk=1, role="tenant_owner")
        tenant = _make_tenant_with_users(owner_user=owner)
        result = _get_tenant_owner_user(tenant)
        self.assertIs(result, owner)

    def test_falls_back_to_any_user_when_no_owner(self):
        """No TENANT_OWNER user → falls back to any user on the tenant."""
        fallback = SimpleNamespace(pk=2, role="tenant_staff")
        tenant = _make_tenant_with_users(owner_user=None, any_user=fallback)
        result = _get_tenant_owner_user(tenant)
        self.assertIs(result, fallback)

    def test_raises_value_error_when_no_users_at_all(self):
        tenant = _make_tenant_with_users(owner_user=None, any_user=None)
        with self.assertRaises(ValueError):
            _get_tenant_owner_user(tenant)

    def test_error_message_mentions_user(self):
        tenant = _make_tenant_with_users(owner_user=None, any_user=None)
        with self.assertRaises(ValueError) as cm:
            _get_tenant_owner_user(tenant)
        self.assertIn("user", str(cm.exception).lower())


# ══════════════════════════════════════════════════════════════════════════════
# _get_reusable_activation_token
# ══════════════════════════════════════════════════════════════════════════════

def _token_queryset_returning(value):
    qs = MagicMock()
    qs.filter.return_value.order_by.return_value.first.return_value = value
    return qs


class GetReusableActivationTokenTests(SimpleTestCase):
    """_get_reusable_activation_token: returns valid token or None."""

    def test_returns_token_when_found(self):
        token = SimpleNamespace(pk=5, used_at=None)
        user = SimpleNamespace(pk=1)
        tenant = SimpleNamespace(pk=1)
        with patch("sales.services.ActivationToken") as mock_at:
            mock_at.objects = _token_queryset_returning(token)
            result = _get_reusable_activation_token(user, tenant)
        self.assertIs(result, token)

    def test_returns_none_when_no_token_found(self):
        user = SimpleNamespace(pk=1)
        tenant = SimpleNamespace(pk=1)
        with patch("sales.services.ActivationToken") as mock_at:
            mock_at.objects = _token_queryset_returning(None)
            result = _get_reusable_activation_token(user, tenant)
        self.assertIsNone(result)

    def test_filter_includes_used_at_isnull(self):
        """Filter kwargs must include used_at__isnull=True."""
        user = SimpleNamespace(pk=1)
        tenant = SimpleNamespace(pk=1)
        with patch("sales.services.ActivationToken") as mock_at:
            mock_at.objects = _token_queryset_returning(None)
            _get_reusable_activation_token(user, tenant)
        kw = mock_at.objects.filter.call_args[1]
        self.assertTrue(kw.get("used_at__isnull"))

    def test_filter_includes_user_and_tenant(self):
        user = SimpleNamespace(pk=1)
        tenant = SimpleNamespace(pk=2)
        with patch("sales.services.ActivationToken") as mock_at:
            mock_at.objects = _token_queryset_returning(None)
            _get_reusable_activation_token(user, tenant)
        kw = mock_at.objects.filter.call_args[1]
        self.assertIs(kw.get("user"), user)
        self.assertIs(kw.get("tenant"), tenant)
