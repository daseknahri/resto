"""
Tests for OwnerMenuImportView:
  GET  /api/owner/menu/import/  — download CSV template
  POST /api/owner/menu/import/  — import dishes from CSV

Also covers OwnerCustomerListView auth check.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerMenuImportView, OwnerCustomerListView
from accounts.models import User


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
    # Staff can edit — mimic perm_edit_menu
    u.perm_edit_menu = True
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


def _csv_file(content, name="menu.csv", size=None):
    encoded = content.encode("utf-8")
    f = SimpleUploadedFile(name, encoded, content_type="text/csv")
    if size is not None:
        f.size = size
    return f


# ── OwnerMenuImportView ───────────────────────────────────────────────────────

class OwnerMenuImportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerMenuImportView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/menu/import/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _post(self, file=None, user=None, tenant=None):
        data = {}
        if file is not None:
            data["file"] = file
        req = self.factory.post("/api/owner/menu/import/", data, format="multipart")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_outsider_returns_403(self):
        resp = self._post(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET returns template ──────────────────────────────────────────────────

    def test_get_returns_csv_template(self):
        resp = self._get()
        self.assertIn("csv", resp.get("Content-Type", "").lower())
        self.assertIn("attachment", resp.get("Content-Disposition", ""))
        self.assertIn(b"dish_name", resp.content)

    def test_get_template_has_required_columns(self):
        resp = self._get()
        content = resp.content.decode("utf-8")
        for col in ("category_name", "dish_name", "price"):
            self.assertIn(col, content, f"Missing column: {col}")

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_no_file_returns_400(self):
        resp = self._post(file=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_file")

    def test_post_non_csv_returns_400(self):
        f = SimpleUploadedFile("menu.xlsx", b"PK...", content_type="application/vnd.ms-excel")
        resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "bad_format")

    def test_post_file_too_large_returns_400(self):
        # Use a real large file (just over 2 MB)
        big_content = "a" * (2 * 1024 * 1024 + 1)
        f = SimpleUploadedFile("menu.csv", big_content.encode("utf-8"), content_type="text/csv")
        resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "too_large")

    def test_post_missing_required_columns_returns_400(self):
        # CSV with only dish_name (missing category_name and price)
        f = _csv_file("dish_name,description\nBurger,Tasty\n")
        resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_columns")

    def test_post_invalid_encoding_returns_400(self):
        # Simulate a file with invalid UTF-8 bytes
        f = SimpleUploadedFile("menu.csv", b"\xff\xfe invalid utf8", content_type="text/csv")
        resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "decode_error")

    # ── POST happy path ───────────────────────────────────────────────────────

    def test_post_valid_csv_returns_200(self):
        csv_content = "category_name,dish_name,price,description\nMain,Burger,12.50,Juicy\n"
        f = _csv_file(csv_content)
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.order_by.return_value.first.return_value = MagicMock(id=1)
            with patch("menu.views.Category") as mock_cat:
                # filter() used for: name lookup (.first) AND slug uniqueness (.exists)
                mock_cat.objects.filter.return_value.first.return_value = None   # no existing cat
                mock_cat.objects.filter.return_value.exists.return_value = False  # slug not taken
                mock_cat.objects.count.return_value = 0
                new_cat = MagicMock()
                mock_cat.objects.create.return_value = new_cat
                with patch("menu.views.Dish") as mock_dish:
                    mock_dish.objects.filter.return_value.exists.return_value = False  # no dup
                    mock_dish.objects.create.return_value = MagicMock()
                    resp = self._post(file=f)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for field in ("created_dishes", "created_categories", "skipped", "errors"):
            self.assertIn(field, resp.data, f"Missing field: {field}")

    def test_post_skips_duplicate_dishes(self):
        csv_content = "category_name,dish_name,price\nMain,Burger,12.50\n"
        f = _csv_file(csv_content)
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.order_by.return_value.first.return_value = MagicMock(id=1)
            with patch("menu.views.Category") as mock_cat:
                # Category already exists (lookup returns one)
                mock_cat.objects.filter.return_value.first.return_value = MagicMock()
                mock_cat.objects.filter.return_value.exists.return_value = False
                with patch("menu.views.Dish") as mock_dish:
                    mock_dish.objects.filter.return_value.exists.return_value = True  # dup dish
                    resp = self._post(file=f)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["created_dishes"], 0)
        self.assertGreater(resp.data["skipped"], 0)

    def test_post_skips_rows_with_invalid_price(self):
        csv_content = "category_name,dish_name,price\nMain,Burger,not_a_price\n"
        f = _csv_file(csv_content)
        with patch("menu.views.SuperCategory") as mock_sc:
            mock_sc.objects.order_by.return_value.first.return_value = MagicMock(id=1)
            with patch("menu.views.Category") as mock_cat:
                mock_cat.objects.filter.return_value.exists.return_value = False
            with patch("menu.views.Dish"):
                    resp = self._post(file=f)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data["skipped"], 0)
        self.assertTrue(any("invalid price" in e.lower() for e in resp.data["errors"]))


# ── OwnerCustomerListView auth check ─────────────────────────────────────────

class OwnerCustomerListViewAuthTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCustomerListView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/customers/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
