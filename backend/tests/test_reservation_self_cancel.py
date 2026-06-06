"""
Unit tests for customer self-service reservation cancellation
(PublicReservationManageView). SimpleTestCase + mocks (no DB).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory

from sales.views import PublicReservationManageView

TOKEN = "11111111-1111-1111-1111-111111111111"


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _wire_status(mock_lead):
    mock_lead.Status.NEW = "new"
    mock_lead.Status.CONTACTED = "contacted"
    mock_lead.Status.WON = "won"
    mock_lead.Status.LOST = "lost"
    mock_lead.Status.NO_SHOW = "no_show"


def _lead(status_value="won", booked_for=None):
    return SimpleNamespace(
        status=status_value,
        booked_for=booked_for if booked_for is not None else timezone.now() + timedelta(days=1),
        name="Sam",
        party_size=4,
        tenant=SimpleNamespace(name="Bistro", schema_name="bistro"),
        save=MagicMock(),
    )


class ReservationManageTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PublicReservationManageView.as_view()

    # ── GET ────────────────────────────────────────────────────────────────
    @patch("sales.views.Lead")
    def test_get_not_found(self, mock_lead):
        mock_lead.objects.select_related.return_value.filter.return_value.first.return_value = None
        resp = self.view(self.factory.get(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("sales.views.Lead")
    def test_get_returns_summary(self, mock_lead):
        _wire_status(mock_lead)
        mock_lead.objects.select_related.return_value.filter.return_value.first.return_value = _lead()
        resp = self.view(self.factory.get(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["restaurant"], "Bistro")
        self.assertTrue(resp.data["can_cancel"])
        self.assertFalse(resp.data["cancelled"])

    # ── POST (cancel) ──────────────────────────────────────────────────────
    @patch("accounts.tasks.enqueue")
    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("sales.views.Lead")
    def test_cancel_active_sets_lost(self, mock_lead, _atomic, _enq):
        _wire_status(mock_lead)
        lead = _lead(status_value="won")
        mock_lead.objects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = lead
        resp = self.view(self.factory.post(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(lead.status, "lost")          # cancelled
        self.assertTrue(resp.data["cancelled"])
        lead.save.assert_called_once()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("sales.views.Lead")
    def test_cancel_idempotent_when_already_lost(self, mock_lead, _atomic):
        _wire_status(mock_lead)
        lead = _lead(status_value="lost")
        mock_lead.objects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = lead
        resp = self.view(self.factory.post(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["cancelled"])
        lead.save.assert_not_called()                  # no state change

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("sales.views.Lead")
    def test_cancel_too_late_when_past(self, mock_lead, _atomic):
        _wire_status(mock_lead)
        lead = _lead(status_value="won", booked_for=timezone.now() - timedelta(hours=1))
        mock_lead.objects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = lead
        resp = self.view(self.factory.post(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "too_late")
        lead.save.assert_not_called()

    @patch("django.db.transaction.atomic", return_value=_noop_atomic())
    @patch("sales.views.Lead")
    def test_cancel_not_found(self, mock_lead, _atomic):
        mock_lead.objects.select_for_update.return_value.select_related.return_value.filter.return_value.first.return_value = None
        resp = self.view(self.factory.post(f"/api/reservations/manage/{TOKEN}/"), token=TOKEN)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
