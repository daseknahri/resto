"""Run 8 G2 — A-44, A-45, A-48: menu Django-admin hardening."""
from types import SimpleNamespace

from django.contrib import admin as django_admin
from django.test import RequestFactory, SimpleTestCase

from menu.admin import (
    AnalyticsEventAdmin,
    CategoryAdmin,
    CurrencyRateAdmin,
    DishAdmin,
)
from menu.models import AnalyticsEvent, Category, CurrencyRate, Dish


def _admin(admin_cls, model):
    return admin_cls(model, django_admin.site)


def _request():
    request = RequestFactory().post("/admin/")
    request.user = SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True, pk=1)
    return request


class DishAndCategoryAdminTests(SimpleTestCase):
    def test_search_fields(self):
        dish_admin = _admin(DishAdmin, Dish)
        category_admin = _admin(CategoryAdmin, Category)
        self.assertEqual(dish_admin.search_fields, ("name", "slug"))
        self.assertEqual(category_admin.search_fields, ("name", "slug"))


class CurrencyRateAdminTests(SimpleTestCase):
    def test_no_inline_editing_from_the_changelist(self):
        admin = _admin(CurrencyRateAdmin, CurrencyRate)
        self.assertFalse(getattr(admin, "list_editable", None))


class AnalyticsEventAdminTests(SimpleTestCase):
    def test_event_rows_cannot_be_deleted(self):
        admin = _admin(AnalyticsEventAdmin, AnalyticsEvent)
        self.assertFalse(admin.has_delete_permission(_request(), None))
