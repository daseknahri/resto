"""
Tests for OwnerOrderBulkStatusView.

  POST /api/owner/orders/bulk-status/

All tests are SimpleTestCase (no database).
ORM calls are fully mocked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import OwnerOrderBulkStatusView


# ── Helpers ────────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 10
    u.id = 10
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.effective_perm_edit_menu.return_value = True
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock(spec=User)
    u.is_authenticated = False
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, slug="demo", name="Demo Restaurant")


def _make_order(pk=1, order_number="ORD-001", status_val="pending"):
    o = MagicMock()
    o.id = pk
    o.order_number = order_number
    o.status = status_val
    o.handled_by_user_id = None
    o.fulfillment_type = "pickup"
    o.customer = None
    return o


# ── Test class ─────────────────────────────────────────────────────────────────

class OwnerOrderBulkStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerOrderBulkStatusView.as_view()

    def _post(self, body=None, user=None, tenant=None):
        req = self.factory.post(
            "/api/owner/orders/bulk-status/",
            body or {},
            format="json",
        )
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_tenant_returns_403(self):
        resp = self._post(user=_owner(tenant_id=2), tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── 400 validation ────────────────────────────────────────────────────────

    def test_unsupported_status_returns_400(self):
        resp = self._post(body={"order_ids": [1, 2], "status": "ready"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_order_ids_returns_400(self):
        resp = self._post(body={"status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_order_ids_returns_400(self):
        resp = self._post(body={"order_ids": [], "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_list_order_ids_returns_400(self):
        resp = self._post(body={"order_ids": "1,2,3", "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_integer_order_ids_returns_400(self):
        resp = self._post(body={"order_ids": ["abc", "def"], "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_order_ids_returns_400(self):
        resp = self._post(body={"order_ids": list(range(51)), "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 200 success ───────────────────────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._send_order_status_email")
    @patch("menu.views.Order.objects")
    def test_updates_pending_orders_to_confirmed(self, mock_qs, mock_mail, mock_bcast):
        o1 = _make_order(pk=1, status_val="pending")
        o2 = _make_order(pk=2, status_val="pending")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[o1, o2])
        resp = self._post(body={"order_ids": [1, 2], "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated"], 2)
        self.assertEqual(resp.data["skipped"], 0)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._send_order_status_email")
    @patch("menu.views.Order.objects")
    def test_sets_status_confirmed_on_each_order(self, mock_qs, mock_mail, mock_bcast):
        o = _make_order(pk=1, status_val="pending")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[o])
        self._post(body={"order_ids": [1], "status": "confirmed"})
        self.assertEqual(o.status, "confirmed")

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._send_order_status_email")
    @patch("menu.views.Order.objects")
    def test_calls_bulk_update(self, mock_qs, mock_mail, mock_bcast):
        o = _make_order(pk=1, status_val="pending")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[o])
        self._post(body={"order_ids": [1], "status": "confirmed"})
        mock_qs.bulk_update.assert_called_once()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._send_order_status_email")
    @patch("menu.views.Order.objects")
    def test_fires_broadcast_for_each_order(self, mock_qs, mock_mail, mock_bcast):
        o1 = _make_order(pk=1, status_val="pending")
        o2 = _make_order(pk=2, status_val="pending")
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[o1, o2])
        self._post(body={"order_ids": [1, 2], "status": "confirmed"})
        self.assertEqual(mock_bcast.call_count, 2)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._send_order_status_email")
    @patch("menu.views.Order.objects")
    def test_sets_handler_id_when_unset(self, mock_qs, mock_mail, mock_bcast):
        o = _make_order(pk=1, status_val="pending")
        o.handled_by_user_id = None
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[o])
        self._post(body={"order_ids": [1], "status": "confirmed"})
        self.assertEqual(o.handled_by_user_id, 10)  # _owner().id == 10

    # ── Empty / all-skipped ───────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_empty_result_returns_updated_zero(self, mock_qs):
        mock_qs.filter.return_value.select_related.return_value.__getitem__ = \
            MagicMock(return_value=[])
        resp = self._post(body={"order_ids": [99], "status": "confirmed"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["updated"], 0)
        self.assertEqual(resp.data["skipped"], 1)
