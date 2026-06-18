"""
B4 backend tests — Labor module: clock-in / clock-out / my-shift endpoints.

Covers:
  Contract 1 — StaffClockInView   POST /api/staff/clock-in/
    - happy path: creates Shift, returns 201 with payload
    - 409 if already clocked in (open shift exists)
    - 403 unauthenticated / no perm

  Contract 2 — StaffClockOutView  POST /api/staff/clock-out/
    - happy path: closes open shift, returns 200 with updated payload
    - 404 if not currently clocked in
    - 403 unauthenticated / no perm

  Contract 3 — StaffMyShiftView   GET /api/staff/my-shift/
    - returns open shift when present
    - returns null when no open shift
    - 403 unauthenticated / no perm

House style: SimpleTestCase + MagicMock, no real DB.
"""
from datetime import datetime, timezone as _tz
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffClockInView, StaffClockOutView, StaffMyShiftView
from accounts.models import User


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _user(perm_manage=True, tenant_id=1, user_id=10):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_STAFF
    u.tenant_id = tenant_id
    u.id = user_id
    u.pk = user_id
    u.effective_perm_manage_orders = MagicMock(return_value=perm_manage)
    u.get_full_name = MagicMock(return_value="Alice Waiter")
    u.username = "alice"
    return u


def _tenant(tenant_id=1):
    t = MagicMock()
    t.id = tenant_id
    return t


def _make_shift(pk=1, user_id=10, clock_out=None):
    s = MagicMock()
    s.id = pk
    s.user_id = user_id
    s.user_name = "Alice Waiter"
    s.clock_in = datetime(2026, 6, 18, 9, 0, 0, tzinfo=_tz.utc)
    s.clock_out = clock_out
    s.hourly_rate = None
    s.note = ""
    s.duration_hours = None if clock_out is None else (clock_out - s.clock_in).total_seconds() / 3600
    s.save = MagicMock()
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 1 — StaffClockInView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffClockInViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffClockInView.as_view()

    def _post(self, payload=None, user=None, tenant_id=1):
        req = self.factory.post("/api/staff/clock-in/", payload or {}, format="json")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req)

    def test_happy_path_creates_shift(self):
        shift = _make_shift()
        with patch("menu.models.Shift") as _S, patch("django.utils.timezone.now") as _now:
            _now.return_value = shift.clock_in
            _S.objects.filter.return_value.exists.return_value = False
            _S.objects.create.return_value = shift
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["id"], 1)
        self.assertEqual(resp.data["user_id"], 10)
        self.assertIsNone(resp.data["clock_out"])

    def test_already_clocked_in_is_409(self):
        with patch("menu.models.Shift") as _S:
            _S.objects.filter.return_value.exists.return_value = True
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "already_clocked_in")

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.post("/api/staff/clock-in/", {}, format="json")
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 2 — StaffClockOutView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffClockOutViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffClockOutView.as_view()

    def _post(self, user=None, tenant_id=1):
        req = self.factory.post("/api/staff/clock-out/", {}, format="json")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req)

    def test_happy_path_closes_shift(self):
        now = datetime(2026, 6, 18, 17, 0, 0, tzinfo=_tz.utc)
        shift = _make_shift()
        with patch("menu.models.Shift") as _S, patch("django.utils.timezone.now") as _now:
            _now.return_value = now
            _S.objects.filter.return_value.first.return_value = shift
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(shift.save.call_count, 1)
        self.assertEqual(shift.clock_out, now)

    def test_not_clocked_in_is_404(self):
        with patch("menu.models.Shift") as _S:
            _S.objects.filter.return_value.first.return_value = None
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_clocked_in")

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.post("/api/staff/clock-out/", {}, format="json")
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 3 — StaffMyShiftView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffMyShiftViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffMyShiftView.as_view()

    def _get(self, user=None, tenant_id=1):
        req = self.factory.get("/api/staff/my-shift/")
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req)

    def test_returns_open_shift_when_present(self):
        shift = _make_shift()
        with patch("menu.models.Shift") as _S:
            _S.objects.filter.return_value.first.return_value = shift
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], 1)
        self.assertIsNone(resp.data["clock_out"])

    def test_returns_null_when_no_open_shift(self):
        with patch("menu.models.Shift") as _S:
            _S.objects.filter.return_value.first.return_value = None
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_perm_is_403(self, _mock):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_403(self):
        req = self.factory.get("/api/staff/my-shift/")
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
