"""Tests for ApplyTemplateView (starter templates):
  GET  /api/owner/apply-template/  — list templates
  POST /api/owner/apply-template/  — apply theme + optional sample menu

Unit-level (SimpleTestCase + mocks — no real DB). Run with DJANGO_DEBUG=True.
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from decimal import Decimal


@contextmanager
def _noop_atomic(*args, **kwargs):
    """Stand-in for transaction.atomic() so unit tests need no real DB."""
    yield

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import ApplyTemplateView
from menu.menu_templates import TEMPLATES, template_summaries
from tenancy.models import Profile
from accounts.models import User


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


def _outsider(tenant_id=99):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id, schema_name="tenant1")


class TemplateDataTests(SimpleTestCase):
    """Pure validation of the template definitions (no view, no DB)."""

    VALID_BUSINESS_TYPES = {"restaurant", "cafe", "bakery", "grocery", "retail"}
    THEME_KEYS = {"primary_color", "secondary_color", "menu_theme", "menu_card_layout"}

    def test_expected_templates_exist(self):
        self.assertEqual(set(TEMPLATES), {"cafe", "hotel", "fine_dining", "fast_casual", "bakery", "bar"})

    def test_each_template_is_well_formed(self):
        for key, tpl in TEMPLATES.items():
            self.assertIn(tpl["business_type"], self.VALID_BUSINESS_TYPES, key)
            self.assertEqual(set(tpl["theme"]), self.THEME_KEYS, key)
            self.assertEqual(len(tpl["theme"]["primary_color"]), 7, key)
            self.assertTrue(tpl["theme"]["primary_color"].startswith("#"), key)
            self.assertIn(tpl["theme"]["menu_theme"], ("dark", "light"), key)
            self.assertTrue(tpl["categories"], key)
            for cat in tpl["categories"]:
                self.assertTrue(cat["name"])
                self.assertTrue(cat["dishes"])
                for d in cat["dishes"]:
                    self.assertTrue(d["name"])
                    Decimal(str(d["price"]))  # must parse

    def test_summaries_match_templates(self):
        sums = {s["key"]: s for s in template_summaries()}
        self.assertEqual(set(sums), set(TEMPLATES))
        for key, s in sums.items():
            expected = sum(len(c["dishes"]) for c in TEMPLATES[key]["categories"])
            self.assertEqual(s["dish_count"], expected)


class ApplyTemplateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ApplyTemplateView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/apply-template/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _post(self, body, user=None, tenant=None):
        req = self.factory.post("/api/owner/apply-template/", body, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ────────────────────────────────────────────────────────────────────
    def test_get_outsider_403(self):
        self.assertEqual(self._get(user=_outsider()).status_code, status.HTTP_403_FORBIDDEN)

    def test_post_outsider_403(self):
        resp = self._post({"template": "cafe"}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET lists templates ───────────────────────────────────────────────────────
    def test_get_lists_templates(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        keys = {t["key"] for t in resp.data["templates"]}
        self.assertEqual(keys, {"cafe", "hotel", "fine_dining", "fast_casual", "bakery", "bar"})

    # ── POST validation ───────────────────────────────────────────────────────────
    def test_post_unknown_template_400(self):
        resp = self._post({"template": "spaceship"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "unknown_template")

    # ── POST happy paths ──────────────────────────────────────────────────────────
    def test_post_theme_only_applies_to_profile(self):
        prof = MagicMock()
        with patch("django.db.transaction.atomic", _noop_atomic), \
             patch("menu.views.Profile") as mock_profile:
            mock_profile.objects.filter.return_value.first.return_value = prof
            resp = self._post({"template": "cafe", "with_sample_content": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["applied"], "cafe")
        self.assertEqual(resp.data["business_type"], "cafe")
        self.assertEqual(resp.data["created_dishes"], 0)
        # Theme written onto the profile + business_type set.
        self.assertEqual(prof.business_type, "cafe")
        self.assertEqual(prof.primary_color, TEMPLATES["cafe"]["theme"]["primary_color"])
        prof.save.assert_called_once()

    def test_post_with_content_creates_sample_menu(self):
        prof = MagicMock()
        with patch("django.db.transaction.atomic", _noop_atomic), \
             patch("menu.views.Profile") as mock_profile, \
             patch("menu.views.SuperCategory") as mock_sc, \
             patch("menu.views.Category") as mock_cat, \
             patch("menu.views.Dish") as mock_dish:
            mock_profile.objects.filter.return_value.first.return_value = prof
            mock_sc.objects.order_by.return_value.first.return_value = MagicMock(id=1)
            mock_cat.objects.filter.return_value.first.return_value = None   # no existing category
            mock_cat.objects.filter.return_value.exists.return_value = False  # slug free
            mock_cat.objects.count.return_value = 0
            mock_cat.objects.create.return_value = MagicMock()
            mock_dish.objects.filter.return_value.exists.return_value = False  # no dup / slug free
            mock_dish.objects.create.return_value = MagicMock()
            resp = self._post({"template": "fast_casual"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected_dishes = sum(len(c["dishes"]) for c in TEMPLATES["fast_casual"]["categories"])
        self.assertEqual(resp.data["created_dishes"], expected_dishes)
        self.assertGreater(resp.data["created_categories"], 0)
