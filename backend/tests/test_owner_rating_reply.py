"""
Tests for OwnerRatingReplyView.

  POST   /api/owner/ratings/<pk>/reply/  — save / update owner reply
  DELETE /api/owner/ratings/<pk>/reply/  — remove owner reply

All tests are SimpleTestCase (no database).
ORM calls are mocked.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import OwnerRatingReplyView


# ── Helpers ────────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 10
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders.return_value = True
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock(spec=User)
    u.is_authenticated = False
    return u


def _tenant(tid=1):
    from types import SimpleNamespace
    return SimpleNamespace(id=tid, slug="demo")


def _make_rating(pk=42, with_reply=False):
    r = MagicMock()
    r.pk = pk
    r.owner_reply = "Great feedback!" if with_reply else ""
    r.owner_reply_at = MagicMock() if with_reply else None
    if with_reply:
        r.owner_reply_at.isoformat.return_value = "2026-01-01T10:00:00+00:00"
    return r


# ── Test class ─────────────────────────────────────────────────────────────────

class OwnerRatingReplyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerRatingReplyView.as_view()

    # ── POST helpers ───────────────────────────────────────────────────────────

    def _post(self, pk=42, body=None, user=None, tenant=None):
        req = self.factory.post(
            f"/api/owner/ratings/{pk}/reply/",
            body or {},
            format="json",
        )
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, pk=pk)

    # ── DELETE helpers ─────────────────────────────────────────────────────────

    def _delete(self, pk=42, user=None, tenant=None):
        req = self.factory.delete(f"/api/owner/ratings/{pk}/reply/")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req, pk=pk)

    # ── POST — 403 ─────────────────────────────────────────────────────────────

    def test_post_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_wrong_tenant_returns_403(self):
        # user belongs to tenant 2, request is for tenant 1
        owner = _owner(tenant_id=2)
        resp = self._post(user=owner, tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── POST — 404 ─────────────────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    def test_post_unknown_rating_returns_404(self, mock_ratings):
        from menu.models import Rating as _R
        mock_ratings.select_related.return_value.get.side_effect = _R.DoesNotExist
        resp = self._post(pk=999, body={"reply": "Thanks!"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── POST — 400 ─────────────────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    def test_post_empty_reply_returns_400(self, mock_ratings):
        mock_ratings.select_related.return_value.get.return_value = _make_rating()
        resp = self._post(body={"reply": ""})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Rating.objects")
    def test_post_whitespace_only_reply_returns_400(self, mock_ratings):
        mock_ratings.select_related.return_value.get.return_value = _make_rating()
        resp = self._post(body={"reply": "   "})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Rating.objects")
    def test_post_missing_reply_field_returns_400(self, mock_ratings):
        mock_ratings.select_related.return_value.get.return_value = _make_rating()
        resp = self._post(body={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("menu.views.Rating.objects")
    def test_post_reply_too_long_returns_400(self, mock_ratings):
        mock_ratings.select_related.return_value.get.return_value = _make_rating()
        resp = self._post(body={"reply": "x" * 1001})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── POST — 200 happy path ──────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    def test_post_valid_reply_saves_and_returns_200(self, mock_ratings):
        rating = _make_rating()
        mock_ratings.select_related.return_value.get.return_value = rating
        # simulate save + tz.now() stamp
        from unittest.mock import patch as _patch
        with _patch("menu.views.timezone") as mock_tz:
            now_dt = MagicMock()
            now_dt.isoformat.return_value = "2026-05-01T08:30:00+00:00"
            mock_tz.now.return_value = now_dt
            rating.owner_reply_at = now_dt
            resp = self._post(body={"reply": "Thank you for your feedback!"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("owner_reply", resp.data)
        self.assertIn("owner_reply_at", resp.data)
        rating.save.assert_called_once_with(update_fields=["owner_reply", "owner_reply_at"])
        self.assertEqual(rating.owner_reply, "Thank you for your feedback!")

    @patch("menu.views.Rating.objects")
    def test_post_reply_exactly_1000_chars_allowed(self, mock_ratings):
        rating = _make_rating()
        mock_ratings.select_related.return_value.get.return_value = rating
        with patch("menu.views.timezone") as mock_tz:
            now_dt = MagicMock()
            now_dt.isoformat.return_value = "2026-05-01T08:30:00+00:00"
            mock_tz.now.return_value = now_dt
            rating.owner_reply_at = now_dt
            resp = self._post(body={"reply": "a" * 1000})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("menu.views.Rating.objects")
    def test_post_strips_leading_trailing_whitespace(self, mock_ratings):
        rating = _make_rating()
        mock_ratings.select_related.return_value.get.return_value = rating
        with patch("menu.views.timezone") as mock_tz:
            now_dt = MagicMock()
            now_dt.isoformat.return_value = "2026-05-01T08:00:00+00:00"
            mock_tz.now.return_value = now_dt
            rating.owner_reply_at = now_dt
            self._post(body={"reply": "  Great!  "})
        self.assertEqual(rating.owner_reply, "Great!")

    # ── DELETE — 403 ──────────────────────────────────────────────────────────

    def test_delete_unauthenticated_returns_403(self):
        resp = self._delete(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_wrong_tenant_returns_403(self):
        owner = _owner(tenant_id=2)
        resp = self._delete(user=owner, tenant=_tenant(tid=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── DELETE — 404 ──────────────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    def test_delete_unknown_rating_returns_404(self, mock_ratings):
        from menu.models import Rating as _R
        mock_ratings.select_related.return_value.get.side_effect = _R.DoesNotExist
        resp = self._delete(pk=999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── DELETE — 204 happy path ────────────────────────────────────────────────

    @patch("menu.views.Rating.objects")
    def test_delete_clears_reply_and_returns_204(self, mock_ratings):
        rating = _make_rating(with_reply=True)
        mock_ratings.select_related.return_value.get.return_value = rating
        resp = self._delete()
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(rating.owner_reply, "")
        self.assertIsNone(rating.owner_reply_at)
        rating.save.assert_called_once_with(update_fields=["owner_reply", "owner_reply_at"])

    @patch("menu.views.Rating.objects")
    def test_delete_on_rating_without_reply_still_returns_204(self, mock_ratings):
        """Deleting on a rating that has no reply is idempotent."""
        rating = _make_rating(with_reply=False)
        mock_ratings.select_related.return_value.get.return_value = rating
        resp = self._delete()
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        rating.save.assert_called_once()
