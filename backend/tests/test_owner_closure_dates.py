"""
Tests for closure-date views:
  - OwnerClosureDateListCreateView  GET/POST /api/owner/closure-dates/
  - OwnerClosureDateDeleteView      DELETE   /api/owner/closure-dates/<id>/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerClosureDateDeleteView, OwnerClosureDateListCreateView
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


def _outsider(tenant_id=99):
    """Authenticated owner from a different tenant — fails the tenant check."""
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
    return SimpleNamespace(id=tenant_id)


def _make_closure(closure_id=1, date_val="2026-12-25", label="Christmas"):
    c = MagicMock()
    c.id = closure_id
    c.date = date.fromisoformat(date_val)
    c.label = label
    return c


# ── OwnerClosureDateListCreateView ────────────────────────────────────────────

class OwnerClosureDateListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerClosureDateListCreateView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/closure-dates/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/closure-dates/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_outsider_returns_403(self):
        resp = self._post({"date": "2026-12-25"}, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET list ──────────────────────────────────────────────────────────────

    def test_get_returns_list(self):
        """Patch the inline import path used by the view."""
        c1 = _make_closure(1, "2026-12-25", "Christmas")
        c2 = _make_closure(2, "2027-01-01", "New Year")
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.objects.order_by.return_value = [c1, c2]
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]["date"], "2026-12-25")
        self.assertEqual(resp.data[0]["label"], "Christmas")

    def test_get_empty_list(self):
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.objects.order_by.return_value = []
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_missing_date_returns_400(self):
        resp = self._post({"label": "Holiday"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_date_format_returns_400(self):
        resp = self._post({"date": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_wrong_date_format_returns_400(self):
        resp = self._post({"date": "25/12/2026"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── POST happy path ───────────────────────────────────────────────────────

    def test_post_creates_closure_date_and_returns_201(self):
        obj = _make_closure(1, "2026-12-25", "Christmas")
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.objects.create.return_value = obj
            resp = self._post({"date": "2026-12-25", "label": "Christmas"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["date"], "2026-12-25")
        self.assertEqual(resp.data["label"], "Christmas")

    def test_post_duplicate_date_returns_400(self):
        from django.db import IntegrityError
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.objects.create.side_effect = IntegrityError
            resp = self._post({"date": "2026-12-25"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ── OwnerClosureDateDeleteView ────────────────────────────────────────────────

class OwnerClosureDateDeleteViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerClosureDateDeleteView.as_view()

    def _delete(self, closure_id, user=None, tenant=None):
        req = self.factory.delete(f"/api/owner/closure-dates/{closure_id}/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, closure_id=closure_id)

    def test_outsider_returns_403(self):
        resp = self._delete(1, user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_not_found_returns_404(self):
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.DoesNotExist = Exception
            mock_cd.objects.get.side_effect = mock_cd.DoesNotExist
            resp = self._delete(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_not_found_returns_404_real_exception(self):
        from menu.models import ClosureDate
        with patch("menu.models.ClosureDate.objects") as mock_objs:
            mock_objs.get.side_effect = ClosureDate.DoesNotExist
            resp = self._delete(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_returns_204(self):
        obj = _make_closure(1)
        with patch("menu.models.ClosureDate") as mock_cd:
            mock_cd.objects.get.return_value = obj
            resp = self._delete(1)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        obj.delete.assert_called_once()
