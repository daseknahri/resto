"""
Tests for waitlist and push-subscribe views:
  - WaitlistJoinView        POST /api/waitlist/
  - OwnerWaitlistView       GET  /api/owner/waitlist/
  - OwnerPushSubscribeView  POST/DELETE /api/owner/push-subscribe/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import WaitlistJoinView, OwnerWaitlistView, OwnerPushSubscribeView
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
    u.id = 7
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


def _anon():
    return MagicMock(is_authenticated=False)


# ── WaitlistJoinView ──────────────────────────────────────────────────────────

class WaitlistJoinViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = WaitlistJoinView.as_view()

    def _post(self, data):
        req = self.factory.post("/api/waitlist/", data, format="json")
        req.user = _anon()
        return self.view(req)

    # ── Validation ────────────────────────────────────────────────────────────

    def test_missing_name_returns_400(self):
        resp = self._post({
            "phone": "0612345678",
            "booked_for": "2026-06-01T19:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", resp.data["detail"].lower())

    def test_short_name_returns_400(self):
        resp = self._post({
            "name": "A",
            "phone": "0612345678",
            "booked_for": "2026-06-01T19:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_phone_and_email_returns_400(self):
        resp = self._post({
            "name": "Alice",
            "booked_for": "2026-06-01T19:00:00Z",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_booked_for_returns_400(self):
        resp = self._post({
            "name": "Alice",
            "phone": "0612345678",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_booked_for_returns_400(self):
        resp = self._post({
            "name": "Alice",
            "phone": "0612345678",
            "booked_for": "not-a-date",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Honeypot ──────────────────────────────────────────────────────────────

    def test_honeypot_filled_returns_200_silently(self):
        """Filled hp field (bot detection) → silent 200 without creating entry."""
        with patch("menu.views.WaitlistEntry") as mock_we:
            resp = self._post({
                "name": "Bot",
                "phone": "0612345678",
                "booked_for": "2026-06-01T19:00:00Z",
                "hp": "I am a bot",
            })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_we.objects.create.assert_not_called()

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_valid_request_with_phone_returns_201(self):
        entry = MagicMock()
        entry.id = 42
        with patch("menu.views.WaitlistEntry") as mock_we:
            mock_we.objects.create.return_value = entry
            resp = self._post({
                "name": "Alice",
                "phone": "0612345678",
                "booked_for": "2026-06-01T19:00:00Z",
            })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "waitlisted")
        self.assertEqual(resp.data["id"], 42)

    def test_valid_request_with_email_only_returns_201(self):
        entry = MagicMock()
        entry.id = 43
        with patch("menu.views.WaitlistEntry") as mock_we:
            mock_we.objects.create.return_value = entry
            resp = self._post({
                "name": "Bob",
                "email": "bob@example.com",
                "booked_for": "2026-06-01T20:00:00Z",
                "party_size": 4,
            })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_party_size_defaults_to_1_on_invalid(self):
        entry = MagicMock()
        entry.id = 44
        with patch("menu.views.WaitlistEntry") as mock_we:
            mock_we.objects.create.return_value = entry
            self._post({
                "name": "Carol",
                "phone": "0612345678",
                "booked_for": "2026-06-01T19:00:00Z",
                "party_size": "not-a-number",
            })
        _, kwargs = mock_we.objects.create.call_args
        self.assertEqual(kwargs.get("party_size"), 1)


# ── OwnerWaitlistView ─────────────────────────────────────────────────────────

class OwnerWaitlistViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWaitlistView.as_view()

    def _get(self, user=None, tenant=None, params=None):
        url = "/api/owner/waitlist/"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        req = self.factory.get(url)
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_outsider_returns_403(self):
        resp = self._get(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_date_returns_400(self):
        resp = self._get(params={"date": "not-a-date"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_returns_results_and_count(self):
        with patch("menu.views.WaitlistEntry") as mock_we:
            mock_we.objects.all.return_value.values.return_value = []
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIn("count", resp.data)

    def test_returns_entries(self):
        entry = {
            "id": 1,
            "booked_for": None,
            "party_size": 2,
            "name": "Alice",
            "phone": "0612345678",
            "email": "",
            "notes": "",
            "status": "pending",
            "notified_at": None,
            "created_at": None,
        }
        with patch("menu.views.WaitlistEntry") as mock_we:
            mock_we.objects.all.return_value.values.return_value = [entry]
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_date_filter_is_applied(self):
        with patch("menu.views.WaitlistEntry") as mock_we:
            qs_all = MagicMock()
            mock_we.objects.all.return_value = qs_all
            qs_filtered = MagicMock()
            qs_all.filter.return_value = qs_filtered
            qs_filtered.values.return_value = []
            with patch("menu.views.datetime") as mock_dt:
                from datetime import datetime as real_dt
                mock_dt.side_effect = real_dt
                resp = self._get(params={"date": "2026-06-01"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        qs_all.filter.assert_called_once()


# ── OwnerPushSubscribeView ────────────────────────────────────────────────────

class OwnerPushSubscribeViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerPushSubscribeView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/push-subscribe/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def _delete(self, data=None, user=None, tenant=None):
        req = self.factory.delete("/api/owner/push-subscribe/", data or {}, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_post_outsider_returns_403(self):
        resp = self._post(
            {"endpoint": "https://example.com/push", "p256dh": "key", "auth": "authkey"},
            user=_outsider(),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_outsider_returns_403(self):
        resp = self._delete(user=_outsider())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── POST validation ───────────────────────────────────────────────────────

    def test_post_missing_endpoint_returns_400(self):
        resp = self._post({"p256dh": "key", "auth": "authkey"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_missing_p256dh_returns_400(self):
        resp = self._post({"endpoint": "https://example.com/push", "auth": "authkey"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_missing_auth_returns_400(self):
        resp = self._post({"endpoint": "https://example.com/push", "p256dh": "key"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── POST happy path ───────────────────────────────────────────────────────

    def test_post_valid_subscription_returns_201(self):
        with patch("menu.models.PushSubscription") as mock_ps:
            mock_ps.objects.update_or_create.return_value = (MagicMock(), True)
            resp = self._post({
                "endpoint": "https://fcm.googleapis.com/push/abc",
                "p256dh": "BNtest_key_here",
                "auth": "auth_secret",
            })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data["subscribed"])

    def test_post_stores_with_correct_fields(self):
        with patch("menu.models.PushSubscription") as mock_ps:
            mock_ps.objects.update_or_create.return_value = (MagicMock(), True)
            self._post({
                "endpoint": "https://fcm.googleapis.com/push/abc",
                "p256dh": "BNtest_key_here",
                "auth": "auth_secret",
            })
        _, kwargs = mock_ps.objects.update_or_create.call_args
        self.assertEqual(kwargs["endpoint"], "https://fcm.googleapis.com/push/abc")
        self.assertEqual(kwargs["defaults"]["p256dh"], "BNtest_key_here")
        self.assertEqual(kwargs["defaults"]["auth"], "auth_secret")

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_delete_with_endpoint_returns_204(self):
        with patch("menu.models.PushSubscription") as mock_ps:
            mock_ps.objects.filter.return_value.delete.return_value = (1, {})
            resp = self._delete({"endpoint": "https://fcm.googleapis.com/push/abc"})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_without_endpoint_returns_204(self):
        with patch("menu.models.PushSubscription"):
            resp = self._delete({})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
