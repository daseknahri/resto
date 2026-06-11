"""
Tests for StaffOrderItemReadyView — kitchen ticks a single line item ready/unready
on a multi-item ticket (PATCH /api/staff/order-items/<item_id>/ready/).

All unit-level (SimpleTestCase + mocks — no real DB). The permission gate and the
live-refresh broadcast are patched out; this exercises the gate, the 404 path, the
boolean coercion of the `ready` body field, and that ready_at is set/cleared.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import StaffOrderItemReadyView


class StaffOrderItemReadyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffOrderItemReadyView.as_view()

    def _item(self, **kw):
        item = MagicMock()
        item.id = kw.get("id", 11)
        item.is_ready = kw.get("is_ready", False)
        item.is_voided = kw.get("is_voided", False)
        item.ready_at = kw.get("ready_at", None)
        item.order = MagicMock()
        item.save = MagicMock()
        return item

    def _set(self, objects_mock, item):
        objects_mock.select_related.return_value.filter.return_value.first.return_value = item

    def _patch(self, body=None):
        req = self.factory.patch(
            "/api/staff/order-items/11/ready/",
            body if body is not None else {},
            format="json",
        )
        req.user = MagicMock(id=9)
        req.tenant = MagicMock(id=7)
        return req

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    @patch("menu.views.OrderItem.objects")
    def test_denied_for_non_editor(self, objects_mock, _gate):
        self._set(objects_mock, self._item())
        resp = self.view(self._patch(), item_id=11)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_unknown_item_404(self, objects_mock, _gate, _access):
        self._set(objects_mock, None)
        resp = self.view(self._patch(), item_id=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_mark_ready_default_true(self, objects_mock, _gate, _access, broadcast_mock):
        item = self._item(is_ready=False)
        self._set(objects_mock, item)
        resp = self.view(self._patch(), item_id=11)  # no body → defaults to ready=True
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_ready"])
        self.assertTrue(item.is_ready)
        self.assertIsNotNone(item.ready_at)
        item.save.assert_called_once()
        broadcast_mock.assert_called_once_with(item.order)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_mark_not_ready_clears_ready_at(self, objects_mock, _gate, _access, _broadcast):
        item = self._item(is_ready=True, ready_at="2026-01-01T00:00:00Z")
        self._set(objects_mock, item)
        resp = self.view(self._patch({"ready": False}), item_id=11)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["is_ready"])
        self.assertFalse(item.is_ready)
        self.assertIsNone(item.ready_at)

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_string_true_coerces(self, objects_mock, _gate, _access, _broadcast):
        item = self._item(is_ready=False)
        self._set(objects_mock, item)
        resp = self.view(self._patch({"ready": "true"}), item_id=11)
        self.assertTrue(resp.data["is_ready"])

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_string_zero_coerces_false(self, objects_mock, _gate, _access, _broadcast):
        item = self._item(is_ready=True)
        self._set(objects_mock, item)
        resp = self.view(self._patch({"ready": "0"}), item_id=11)
        self.assertFalse(resp.data["is_ready"])

    @patch("menu.views._broadcast_order_change", side_effect=RuntimeError("ws down"))
    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_broadcast_failure_is_swallowed(self, objects_mock, _gate, _access, _broadcast):
        item = self._item(is_ready=False)
        self._set(objects_mock, item)
        resp = self.view(self._patch(), item_id=11)  # broadcast raises → must still 200
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_ready"])

    @patch("menu.views._can_access_order", return_value=True)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_voided_item_rejected(self, objects_mock, _gate, _access):
        """PATCH on a voided item must return 409 item_voided."""
        item = self._item(is_voided=True)
        self._set(objects_mock, item)
        resp = self.view(self._patch(), item_id=11)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "item_voided")

    @patch("menu.views._can_access_order", return_value=False)
    @patch("menu.views._can_edit_tenant_order", return_value=True)
    @patch("menu.views.OrderItem.objects")
    def test_section_denied(self, objects_mock, _gate, _access):
        """PATCH by a waiter who doesn't own that table's section returns 403."""
        item = self._item()
        self._set(objects_mock, item)
        resp = self.view(self._patch(), item_id=11)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "section_denied")
