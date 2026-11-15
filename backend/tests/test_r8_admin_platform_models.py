"""Run 8 G2 — A-42: Django-admin registrations for key platform models."""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.test import RequestFactory, SimpleTestCase

from accounts.admin import (
    PlatformConfigAdmin,
    PlatformFlashSaleAdmin,
    RideRequestAdmin,
    WalletVoucherAdmin,
)
from accounts.models import (
    PlatformConfig,
    PlatformFlashSale,
    RideRequest,
    WalletVoucher,
)


def _admin(admin_cls, model):
    return admin_cls(model, django_admin.site)


def _request():
    request = RequestFactory().post("/admin/")
    request.user = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True, pk=1)
    return request


def _editable_fields(model):
    # The pk is auto-managed and never appears in an admin form.
    return {field.name for field in model._meta.fields if field.editable and not field.primary_key}


class PlatformModelRegistrationTests(SimpleTestCase):
    def test_platform_models_are_registered(self):
        for model in (PlatformConfig, PlatformFlashSale, RideRequest, WalletVoucher):
            self.assertTrue(
                django_admin.site.is_registered(model),
                f"{model.__name__} has no Django-admin registration",
            )

    def test_platform_config_is_singleton_guarded(self):
        admin = _admin(PlatformConfigAdmin, PlatformConfig)
        self.assertFalse(admin.has_delete_permission(_request(), None))
        with patch("accounts.admin.PlatformConfig") as config_cls:
            config_cls.objects.exists.return_value = True
            self.assertFalse(admin.has_add_permission(_request()))
            config_cls.objects.exists.return_value = False
            self.assertTrue(admin.has_add_permission(_request()))

    def test_flash_sale_counter_is_readonly(self):
        admin = _admin(PlatformFlashSaleAdmin, PlatformFlashSale)
        self.assertIn("redemption_count", admin.get_readonly_fields(_request()))

    def test_ride_requests_are_read_first_and_hide_secrets(self):
        admin = _admin(RideRequestAdmin, RideRequest)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue(_editable_fields(RideRequest) <= readonly)
        self.assertNotIn("delivery_code", admin.list_display)
        self.assertNotIn("recipient_track_token", admin.list_display)
        self.assertIn("delivery_code", admin.exclude)
        self.assertIn("recipient_track_token", admin.exclude)
        self.assertFalse(admin.has_add_permission(_request()))
        self.assertFalse(admin.has_delete_permission(_request(), None))

    def test_vouchers_are_read_first_and_hide_codes(self):
        admin = _admin(WalletVoucherAdmin, WalletVoucher)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue(_editable_fields(WalletVoucher) <= readonly)
        self.assertNotIn("code", admin.list_display)
        self.assertNotIn("code", admin.search_fields)
        self.assertIn("code", admin.exclude)
        self.assertFalse(admin.has_add_permission(_request()))
        self.assertFalse(admin.has_delete_permission(_request(), None))
