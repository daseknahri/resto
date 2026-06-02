"""
Tests for OwnerStaffListCreateView and OwnerStaffDeleteView.

GET  /api/owner/staff/        — list staff for the current tenant
POST /api/owner/staff/        — create a staff account (waiter)
DELETE /api/owner/staff/<id>/ — remove a staff account

All tests are unit-level (SimpleTestCase + mocks — no real DB).
Note: the views use inline `from .models import User` so patches target
`accounts.models.User`, not `accounts.views.User`.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import OwnerStaffDeleteView, OwnerStaffListCreateView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tenant(tenant_id=1, name="Demo Restaurant"):
    t = SimpleNamespace(id=tenant_id, name=name)
    domains_qs = MagicMock()
    domains_qs.filter.return_value.values_list.return_value.first.return_value = None
    t.domains = domains_qs
    return t


def _make_owner(tenant_id=1):
    """Return a user that looks like a TENANT_OWNER."""
    from accounts.models import User
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.tenant_id = tenant_id
    u.role = User.Roles.TENANT_OWNER
    # _is_tenant_owner checks `user.role == user.Roles.TENANT_OWNER`; since
    # `user` is a MagicMock, `user.Roles` would otherwise be a fresh mock.
    u.Roles = User.Roles
    return u


def _non_owner():
    """Return an authenticated user that is NOT a tenant owner."""
    from accounts.models import User
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.tenant_id = 1
    u.role = User.Roles.TENANT_STAFF
    return u


# ── OwnerStaffListCreateView — GET ────────────────────────────────────────────

class OwnerStaffListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerStaffListCreateView.as_view()

    def _get(self, user=None, tenant=None):
        req = self.factory.get("/api/owner/staff/")
        req.user = user or _make_owner()
        req.tenant = tenant or _make_tenant()
        return self.view(req)

    def test_returns_403_for_non_owner(self):
        resp = self._get(user=_non_owner())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "forbidden")

    def test_returns_staff_list_structure(self):
        """GET returns results + count for an owner."""
        staff_rows = [
            {
                "id": 10,
                "email": "waiter@demo.com",
                "first_name": "Jean",
                "last_name": "Dupont",
                "username": "jeandupont",
                "date_joined": None,
                "perm_manage_orders": True,
                "perm_view_revenue": False,
                "perm_edit_menu": False,
            }
        ]
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            # .filter(tenant=..., role=...).order_by(...).values(...) → list
            obj_mock.filter.return_value.order_by.return_value.values.return_value = staff_rows
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["email"], "waiter@demo.com")


# ── OwnerStaffListCreateView — POST ───────────────────────────────────────────

class OwnerStaffCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerStaffListCreateView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/staff/", data, format="json")
        req.user = user or _make_owner()
        req.tenant = tenant or _make_tenant()
        return req

    def test_returns_403_for_non_owner(self):
        req = self._post({"name": "Jean", "email": "jean@demo.com"}, user=_non_owner())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejects_empty_name(self):
        req = self._post({"name": "", "email": "jean@demo.com"})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "name_required")

    def test_rejects_short_name(self):
        req = self._post({"name": "J", "email": "jean@demo.com"})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "name_required")

    def test_rejects_missing_email(self):
        req = self._post({"name": "Jean Dupont", "email": ""})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "email_required")

    def test_rejects_malformed_email(self):
        req = self._post({"name": "Jean Dupont", "email": "notanemail"})
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(resp.data["code"], ("email_required", "email_invalid"))

    def test_rejects_duplicate_email(self):
        req = self._post({"name": "Jean Dupont", "email": "taken@demo.com"})
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.exists.return_value = True  # email taken
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "email_taken")

    def test_rejects_when_plan_staff_limit_reached(self):
        """When the plan's max_staff_accounts is hit, creation is blocked with a clear code."""
        tenant = _make_tenant()
        tenant.plan = SimpleNamespace(max_staff_accounts=2)
        req = self._post({"name": "Jean Dupont", "email": "jean@demo.com"}, tenant=tenant)
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.exists.return_value = False  # email not taken
            obj_mock.filter.return_value.count.return_value = 2       # already at the limit
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "staff_limit_reached")
        self.assertEqual(resp.data["limit"], 2)
        self.assertEqual(resp.data["current"], 2)

    def test_creates_staff_and_returns_credentials(self):
        """Successful creation returns id, email, name, username, temp_password."""
        req = self._post({"name": "Jean Dupont", "email": "jean@demo.com"})
        new_user = MagicMock()
        new_user.id = 20
        new_user.email = "jean@demo.com"
        new_user.username = "jeandemo"

        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            # Email uniqueness check → not taken
            obj_mock.filter.return_value.exists.return_value = False
            # Username uniqueness check → not taken
            obj_mock.filter.return_value.exists.side_effect = None
            obj_mock.filter.return_value.exists.return_value = False
            obj_mock.create_user.return_value = new_user
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        for field in ("id", "email", "name", "username", "temp_password"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertTrue(resp.data["temp_password"])  # non-empty


# ── OwnerStaffDeleteView ──────────────────────────────────────────────────────

class OwnerStaffDeleteViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerStaffDeleteView.as_view()

    def _delete(self, staff_id, user=None, tenant=None):
        req = self.factory.delete(f"/api/owner/staff/{staff_id}/")
        req.user = user or _make_owner()
        req.tenant = tenant or _make_tenant()
        return self.view(req, staff_id=staff_id)

    def test_returns_403_for_non_owner(self):
        resp = self._delete(10, user=_non_owner())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_404_for_unknown_staff_id(self):
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = None  # not found
            resp = self._delete(999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    def test_deletes_staff_and_returns_204(self):
        staff_user = MagicMock()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._delete(10)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        staff_user.delete.assert_called_once()


# ── OwnerStaffDeleteView — PATCH (permissions) ────────────────────────────────

class OwnerStaffPatchViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerStaffDeleteView.as_view()

    def _patch(self, staff_id, data, user=None, tenant=None):
        req = self.factory.patch(f"/api/owner/staff/{staff_id}/", data, format="json")
        req.user = user or _make_owner()
        req.tenant = tenant or _make_tenant()
        return self.view(req, staff_id=staff_id)

    def _staff_user(self):
        u = MagicMock()
        u.id = 10
        u.perm_manage_orders = True
        u.perm_view_revenue = False
        u.perm_edit_menu = False
        return u

    # ── Auth / access ─────────────────────────────────────────────────────────

    def test_returns_403_for_non_owner(self):
        resp = self._patch(10, {"permissions": {"manage_orders": False}}, user=_non_owner())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_404_for_unknown_staff_id(self):
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = None
            resp = self._patch(999, {"permissions": {"manage_orders": False}})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    # ── Validation ────────────────────────────────────────────────────────────

    def test_non_dict_permissions_returns_400(self):
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._patch(10, {"permissions": "not-a-dict"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid")

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_valid_permission_update_returns_200_with_permissions(self):
        """PATCH with a valid bool flag updates the field and returns the full permissions dict."""
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._patch(10, {"permissions": {"view_revenue": True}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("permissions", resp.data)
        self.assertEqual(resp.data["id"], 10)
        for key in ("manage_orders", "view_revenue", "edit_menu"):
            self.assertIn(key, resp.data["permissions"])

    def test_save_called_with_correct_update_fields(self):
        """save() must be called with only the fields that were updated."""
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            self._patch(10, {"permissions": {"edit_menu": True}})
        staff_user.save.assert_called_once_with(update_fields=["perm_edit_menu"])

    def test_no_valid_fields_skips_save(self):
        """If no recognised bool fields are in the payload, save() is not called."""
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._patch(10, {"permissions": {}})
        staff_user.save.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_boolean_values_are_silently_ignored(self):
        """Non-bool values for valid keys must be ignored; save() is not called."""
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._patch(10, {"permissions": {"manage_orders": 1}})
        staff_user.save.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unknown_permission_keys_are_silently_ignored(self):
        """Unknown keys in the permissions dict must not cause errors."""
        staff_user = self._staff_user()
        import accounts.models as _accts
        with patch.object(_accts.User, "objects") as obj_mock:
            obj_mock.filter.return_value.first.return_value = staff_user
            resp = self._patch(10, {"permissions": {"delete_everything": True}})
        staff_user.save.assert_not_called()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
