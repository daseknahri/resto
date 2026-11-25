"""R P1-2 server-side clock-in gate — the five staff mutation views with no
direct test coverage (FireCourse, BulkReady, Transfer, Merge, SeatSplit).

Each test drives the real view with a staff user who passes
_can_edit_tenant_order but has no open Shift: the view must refuse with 409
not_clocked_in before any order work. Owners are exempt (proven on Transfer).

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import (
    StaffBulkReadyView,
    StaffFireCourseView,
    StaffMergeOrdersView,
    StaffSeatSplitView,
    StaffTransferItemsView,
)


def _user(role=User.Roles.TENANT_STAFF, tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.id = 9
    u.effective_perm_manage_orders = MagicMock(return_value=True)
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


class StaffMutationClockInGateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # The staff user has NO open shift by default in this file.
        _shift = patch("menu.models.Shift")
        self._shift_mock = _shift.start()
        self.addCleanup(_shift.stop)
        self._shift_mock.objects.filter.return_value.exists.return_value = False

    def _post(self, view, url, body=None, user=None, **kwargs):
        req = self.factory.post(url, body or {}, format="json")
        force_authenticate(req, user=user or _user())
        req.tenant = _tenant()
        return view(req, **kwargs)

    def test_fire_course_not_clocked_in_409(self):
        resp = self._post(
            StaffFireCourseView.as_view(), "/api/staff/orders/10/fire-course/",
            order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_clocked_in")

    def test_bulk_ready_not_clocked_in_409(self):
        resp = self._post(
            StaffBulkReadyView.as_view(), "/api/staff/orders/10/bulk-ready/",
            order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_clocked_in")

    def test_transfer_not_clocked_in_409(self):
        resp = self._post(
            StaffTransferItemsView.as_view(), "/api/staff/orders/10/transfer/",
            src_order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_clocked_in")

    def test_merge_not_clocked_in_409(self):
        resp = self._post(
            StaffMergeOrdersView.as_view(), "/api/staff/orders/10/merge/",
            dest_order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "not_clocked_in")

    @patch("menu.views.Order.objects")
    def test_seat_split_get_is_not_gated(self, order_om):
        """StaffSeatSplitView is a READ-only GET (seat grouping for the settle
        screen), not a mutation — the clock-in gate deliberately does NOT apply.
        A staff user with no open shift reaches the order lookup (404 here)."""
        order_om.prefetch_related.return_value.filter.return_value.first.return_value = None
        req = self.factory.get("/api/staff/orders/10/seat-split/")
        force_authenticate(req, user=_user())
        req.tenant = _tenant()
        resp = StaffSeatSplitView.as_view()(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")
        self._shift_mock.objects.filter.assert_not_called()

    def test_owner_is_exempt_from_clock_in(self):
        """Owners do not clock in — Transfer proceeds past the gate (400 for the
        missing item_ids, not 409)."""
        owner = _user(role=User.Roles.TENANT_OWNER)
        resp = self._post(
            StaffTransferItemsView.as_view(), "/api/staff/orders/10/transfer/",
            user=owner, src_order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "no_items")
        self._shift_mock.objects.filter.assert_not_called()
