"""Tests for the delivery-pricing → admin move:
- ProfileSerializer marks delivery pricing read-only (owner can't edit it)
- AdminTenantDeliveryView (GET/PATCH /api/admin-tenants/<id>/delivery/) is
  platform-admin only and sets the tenant's delivery pricing.

Unit-level (SimpleTestCase + mocks). Run with DJANGO_DEBUG=True.
"""
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.models import AdminAuditLog
from sales.views import AdminTenantDeliveryView
from tenancy.serializers import ProfileSerializer


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _admin():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True, pk=1, id=1)


def _nonadmin():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=False, pk=2, id=2)


def _tenant():
    return SimpleNamespace(id=1, pk=1, slug="demo", name="Demo", schema_name="demo")


def _profile(**kw):
    p = SimpleNamespace(
        delivery_enabled=True,
        platform_delivery_enabled=False,
        delivery_fee=Decimal("0.00"),
        delivery_base_fee=Decimal("0.00"),
        delivery_per_km=Decimal("0.00"),
        delivery_free_over=Decimal("0.00"),
        delivery_minimum_order=Decimal("0.00"),
        delivery_radius_km=None,
        delivery_zone_description="",
        delivery_commission_pct=Decimal("0.00"),
        save=Mock(),
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class ProfileSerializerDeliveryReadOnlyTests(SimpleTestCase):
    READ_ONLY = (
        "delivery_fee", "delivery_base_fee", "delivery_per_km", "delivery_free_over",
        "delivery_minimum_order", "delivery_radius_km", "delivery_zone_description",
        "delivery_commission_pct", "platform_delivery_enabled",
    )

    def test_owner_cannot_write_delivery_pricing(self):
        s = ProfileSerializer(data={
            "delivery_per_km": "5.00",
            "delivery_base_fee": "10.00",
            "delivery_radius_km": 8,
            "delivery_commission_pct": "20",
            "platform_delivery_enabled": True,
            "delivery_zone_description": "hacked",
            "delivery_enabled": False,  # operational toggle — must stay writable
        }, partial=True)
        s.is_valid()
        for f in self.READ_ONLY:
            self.assertNotIn(f, s.validated_data, f"{f} should be read-only for the owner")

    def test_owner_keeps_operational_delivery_toggle(self):
        s = ProfileSerializer(data={"delivery_enabled": False}, partial=True)
        s.is_valid()
        self.assertIn("delivery_enabled", s.validated_data)
        self.assertFalse(s.validated_data["delivery_enabled"])


class AdminTenantDeliveryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminTenantDeliveryView.as_view()
        # Every successful PATCH now writes an AdminAuditLog row; patch the helper
        # so these SimpleTestCase tests never touch the DB.
        log_patcher = patch("sales.views.log_admin_action")
        self.mock_log = log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_non_admin_forbidden(self):
        req = self.factory.get("/api/admin-tenants/1/delivery/")
        force_authenticate(req, user=_nonadmin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_get_returns_delivery(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        mock_profile.objects.filter.return_value.first.return_value = _profile(delivery_per_km=Decimal("4.50"))
        req = self.factory.get("/api/admin-tenants/1/delivery/")
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["delivery"]["delivery_per_km"], "4.50")
        self.assertEqual(resp.data["tenant"]["slug"], "demo")

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_sets_pricing(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        prof = _profile()
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/",
            {"delivery_per_km": "6", "platform_delivery_enabled": True, "delivery_radius_km": 10},
            format="json",
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(prof.delivery_per_km, Decimal("6.00"))
        self.assertTrue(prof.platform_delivery_enabled)
        self.assertEqual(prof.delivery_radius_km, 10.0)
        prof.save.assert_called_once()
        # Guard the no-updated_at fix: Profile has no updated_at field, so a stray
        # "updated_at" in update_fields would raise ValueError → 500 in production.
        _saved = prof.save.call_args.kwargs.get("update_fields") or []
        self.assertNotIn("updated_at", _saved)
        self.assertIn("delivery_per_km", _saved)

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_rejects_negative(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        mock_profile.objects.filter.return_value.first.return_value = _profile()
        req = self.factory.patch("/api/admin-tenants/1/delivery/", {"delivery_per_km": "-3"}, format="json")
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_sets_commission(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        prof = _profile()
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/", {"delivery_commission_pct": "15"}, format="json"
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(prof.delivery_commission_pct, Decimal("15.00"))
        self.assertEqual(resp.data["delivery"]["delivery_commission_pct"], "15.00")

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_rejects_commission_over_100(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        mock_profile.objects.filter.return_value.first.return_value = _profile()
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/", {"delivery_commission_pct": "150"}, format="json"
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # A rejected PATCH saves nothing, so it must not write an audit row.
        self.mock_log.assert_not_called()

    # --- Audit trail: this endpoint is the ONLY writer of the platform's revenue
    # share (delivery/marketplace commission) — every real change must be logged.

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_commission_change_is_audited_with_old_and_new(self, mock_g404, mock_profile):
        tenant = _tenant()
        mock_g404.return_value = tenant
        prof = _profile(
            delivery_commission_pct=Decimal("10.00"),
            marketplace_commission_pct=Decimal("0.10"),
        )
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/",
            {"delivery_commission_pct": "20", "marketplace_commission_pct": "0.15"},
            format="json",
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.mock_log.assert_called_once()
        kwargs = self.mock_log.call_args.kwargs
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.TENANT_DELIVERY_PRICING_UPDATED)
        self.assertIs(kwargs["tenant"], tenant)
        self.assertEqual(kwargs["target_repr"], "tenant:demo")
        meta = kwargs["metadata"]
        self.assertEqual(
            meta["changes"]["delivery_commission_pct"], {"old": "10.00", "new": "20.00"}
        )
        self.assertEqual(
            meta["changes"]["marketplace_commission_pct"], {"old": "0.10", "new": "0.15"}
        )
        self.assertIn("delivery_commission_pct", meta["changed_fields"])
        self.assertIn("marketplace_commission_pct", meta["changed_fields"])
        # Must be JSON-serializable: a raw Decimal would make log_admin_action
        # swallow the error and silently drop the audit row.
        json.dumps(meta)

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_audit_records_only_real_diffs_and_no_free_text(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        prof = _profile(delivery_fee=Decimal("7.00"))
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/",
            {
                "delivery_fee": "7",  # re-submitted unchanged (full-form PATCH)
                "delivery_per_km": "5",
                "platform_delivery_enabled": True,
                "delivery_zone_description": "Downtown only",
            },
            format="json",
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        meta = self.mock_log.call_args.kwargs["metadata"]
        self.assertEqual(meta["changes"]["delivery_per_km"], {"old": "0.00", "new": "5.00"})
        self.assertEqual(meta["changes"]["platform_delivery_enabled"], {"old": False, "new": True})
        self.assertNotIn("delivery_fee", meta["changes"])
        # Free-text field: its name is recorded, its value never is.
        self.assertIn("delivery_zone_description", meta["changed_fields"])
        self.assertNotIn("delivery_zone_description", meta["changes"])
        self.assertNotIn("Downtown only", json.dumps(meta))

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_noop_patch_is_not_audited(self, mock_g404, mock_profile):
        mock_g404.return_value = _tenant()
        prof = _profile()
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/", {"unknown_field": "x"}, format="json"
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prof.save.assert_not_called()
        self.mock_log.assert_not_called()
