"""Run 8 G2 — A-34, A-35, A-36, A-43: accounts Django-admin money hardening."""
from types import SimpleNamespace

from django.contrib import admin as django_admin
from django.test import RequestFactory, SimpleTestCase

from accounts.admin import (
    CustomerAdmin,
    PasswordResetTokenAdmin,
    UserAdmin,
    WalletTransactionAdmin,
)
from accounts.models import Customer, PasswordResetToken, User, WalletTransaction


def _admin(admin_cls, model):
    return admin_cls(model, django_admin.site)


def _request():
    request = RequestFactory().post("/admin/")
    request.user = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
        is_staff=True,
        pk=1,
        has_module_perms=lambda app_label: True,
        has_perm=lambda perm: True,
    )
    return request


def _editable_fields(model):
    # The pk is auto-managed and never appears in an admin form.
    return {field.name for field in model._meta.fields if field.editable and not field.primary_key}


class WalletTransactionAdminTests(SimpleTestCase):
    def test_every_money_field_is_readonly(self):
        admin = _admin(WalletTransactionAdmin, WalletTransaction)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue(
            _editable_fields(WalletTransaction) <= readonly,
            f"editable but not readonly: {_editable_fields(WalletTransaction) - readonly}",
        )

    def test_cannot_add_or_delete_rows(self):
        admin = _admin(WalletTransactionAdmin, WalletTransaction)
        request = _request()
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_delete_permission(request, None))


class CustomerAdminTests(SimpleTestCase):
    def test_wallet_balance_is_readonly(self):
        admin = _admin(CustomerAdmin, Customer)
        self.assertIn("wallet_balance", admin.get_readonly_fields(_request()))


class PasswordResetTokenAdminTests(SimpleTestCase):
    def test_token_never_in_list_or_search(self):
        admin = _admin(PasswordResetTokenAdmin, PasswordResetToken)
        self.assertNotIn("token", admin.list_display)
        self.assertNotIn("token", admin.search_fields)
        self.assertIn("token", admin.get_readonly_fields(_request()))


class UserAdminTests(SimpleTestCase):
    def test_search_fields(self):
        admin = _admin(UserAdmin, User)
        self.assertEqual(admin.search_fields, ("username", "email"))
