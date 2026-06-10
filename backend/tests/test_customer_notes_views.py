"""
Tests for OwnerCustomerNotesView and OwnerCustomerLoyaltyGrantView.

  PATCH /api/owner/customers/<id>/notes/
  POST  /api/owner/customers/<id>/loyalty-grant/

All tests are SimpleTestCase (no database). ORM calls are fully mocked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from menu.views import OwnerCustomerLoyaltyGrantView, OwnerCustomerNotesView


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
    u.Roles = User.Roles
    return u


def _anon():
    u = MagicMock(spec=User)
    u.is_authenticated = False
    u.is_active = False  # prevent SessionAuthentication from "succeeding" on the mock
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, slug="demo", name="Demo Restaurant")


def _factory():
    return APIRequestFactory()


# ── OwnerCustomerNotesView ──────────────────────────────────────────────────────

class OwnerCustomerNotesViewTests(SimpleTestCase):

    def _patch_req(self, data, user=None):
        req = _factory().patch(
            "/api/owner/customers/42/notes/", data, format="json"
        )
        req.user = user or _owner()
        req.tenant = _tenant()
        return req

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_patch_saves_notes(self, MockNote, _mock_owner):
        note_obj = MagicMock()
        note_obj.notes = "VIP customer"
        MockNote.objects.update_or_create.return_value = (note_obj, True)
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({"notes": "VIP customer"}), customer_id=42)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["notes"], "VIP customer")
        MockNote.objects.update_or_create.assert_called_once_with(
            customer_id=42, defaults={"notes": "VIP customer"}
        )

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_patch_strips_whitespace(self, MockNote, _mock_owner):
        note_obj = MagicMock()
        note_obj.notes = "trimmed"
        MockNote.objects.update_or_create.return_value = (note_obj, True)
        OwnerCustomerNotesView.as_view()(self._patch_req({"notes": "  trimmed  "}), customer_id=42)
        MockNote.objects.update_or_create.assert_called_once_with(
            customer_id=42, defaults={"notes": "trimmed"}
        )

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_patch_empty_string_clears_notes(self, MockNote, _mock_owner):
        note_obj = MagicMock()
        note_obj.notes = ""
        MockNote.objects.update_or_create.return_value = (note_obj, False)
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({"notes": ""}), customer_id=99)
        self.assertEqual(resp.status_code, 200)
        MockNote.objects.update_or_create.assert_called_once_with(
            customer_id=99, defaults={"notes": ""}
        )

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_missing_notes_key_treated_as_empty(self, MockNote, _mock_owner):
        """Request without a 'notes' key treats it as empty string."""
        note_obj = MagicMock()
        note_obj.notes = ""
        MockNote.objects.update_or_create.return_value = (note_obj, True)
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({}), customer_id=42)
        self.assertEqual(resp.status_code, 200)
        MockNote.objects.update_or_create.assert_called_once_with(
            customer_id=42, defaults={"notes": ""}
        )

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_response_includes_customer_id(self, MockNote, _mock_owner):
        note_obj = MagicMock()
        note_obj.notes = "note"
        MockNote.objects.update_or_create.return_value = (note_obj, True)
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({"notes": "note"}), customer_id=77)
        self.assertEqual(resp.data["customer_id"], 77)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_non_owner_gets_403(self, _mock_owner):
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({"notes": "x"}), customer_id=42)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_gets_403(self):
        req = _factory().patch(
            "/api/owner/customers/42/notes/", {"notes": "x"}, format="json"
        )
        req.user = _anon()
        req.tenant = _tenant()
        resp = OwnerCustomerNotesView.as_view()(req, customer_id=42)
        self.assertIn(resp.status_code, (401, 403))

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.CustomerNote")
    def test_upserts_existing_record(self, MockNote, _mock_owner):
        """update_or_create handles both create and update transparently."""
        note_obj = MagicMock()
        note_obj.notes = "updated"
        # Second call: created=False (upsert of existing)
        MockNote.objects.update_or_create.return_value = (note_obj, False)
        resp = OwnerCustomerNotesView.as_view()(self._patch_req({"notes": "updated"}), customer_id=42)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["notes"], "updated")


# ── OwnerCustomerLoyaltyGrantView ───────────────────────────────────────────────

class _FakeDoesNotExist(Exception):
    """Substitute for Customer.DoesNotExist in mock tests."""


class OwnerCustomerLoyaltyGrantViewTests(SimpleTestCase):

    def _post_req(self, data, user=None):
        req = _factory().post(
            "/api/owner/customers/42/loyalty-grant/", data, format="json"
        )
        req.user = user or _owner()
        req.tenant = _tenant()
        return req

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_non_owner_gets_403(self, _):
        resp = OwnerCustomerLoyaltyGrantView.as_view()(self._post_req({"delta": 50}), customer_id=42)
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_gets_403(self):
        req = _factory().post(
            "/api/owner/customers/42/loyalty-grant/", {"delta": 50}, format="json"
        )
        req.user = _anon()
        req.tenant = _tenant()
        resp = OwnerCustomerLoyaltyGrantView.as_view()(req, customer_id=42)
        self.assertIn(resp.status_code, (401, 403))

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_non_integer_delta_is_400(self, _):
        resp = OwnerCustomerLoyaltyGrantView.as_view()(
            self._post_req({"delta": "not-a-number"}), customer_id=42
        )
        self.assertEqual(resp.status_code, 400)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_missing_delta_is_400(self, _):
        resp = OwnerCustomerLoyaltyGrantView.as_view()(self._post_req({}), customer_id=42)
        self.assertEqual(resp.status_code, 400)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_delta_over_max_positive_is_400(self, _):
        resp = OwnerCustomerLoyaltyGrantView.as_view()(
            self._post_req({"delta": 200_000}), customer_id=42
        )
        self.assertEqual(resp.status_code, 400)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_delta_over_max_negative_is_400(self, _):
        resp = OwnerCustomerLoyaltyGrantView.as_view()(
            self._post_req({"delta": -200_000}), customer_id=42
        )
        self.assertEqual(resp.status_code, 400)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_customer_not_found_is_404(self, _):
        with patch("accounts.models.Customer") as MockCust:
            MockCust.DoesNotExist = _FakeDoesNotExist
            MockCust.objects.select_for_update.return_value.get.side_effect = _FakeDoesNotExist()
            with patch("django.db.transaction.atomic") as mock_tx:
                mock_tx.return_value.__enter__ = MagicMock(return_value=None)
                mock_tx.return_value.__exit__ = MagicMock(return_value=False)
                resp = OwnerCustomerLoyaltyGrantView.as_view()(
                    self._post_req({"delta": 50}), customer_id=9999
                )
        self.assertEqual(resp.status_code, 404)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_grant_adds_points(self, _):
        mock_cust = MagicMock()
        mock_cust.loyalty_points = 100
        mock_cust.save = MagicMock()
        with patch("accounts.models.Customer") as MockCust:
            MockCust.DoesNotExist = _FakeDoesNotExist
            MockCust.objects.select_for_update.return_value.get.return_value = mock_cust
            with patch("django.db.transaction.atomic") as mock_tx:
                mock_tx.return_value.__enter__ = MagicMock(return_value=None)
                mock_tx.return_value.__exit__ = MagicMock(return_value=False)
                resp = OwnerCustomerLoyaltyGrantView.as_view()(
                    self._post_req({"delta": 50}), customer_id=42
                )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["loyalty_points"], 150)
        self.assertEqual(mock_cust.loyalty_points, 150)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_deduct_removes_points(self, _):
        mock_cust = MagicMock()
        mock_cust.loyalty_points = 80
        mock_cust.save = MagicMock()
        with patch("accounts.models.Customer") as MockCust:
            MockCust.DoesNotExist = _FakeDoesNotExist
            MockCust.objects.select_for_update.return_value.get.return_value = mock_cust
            with patch("django.db.transaction.atomic") as mock_tx:
                mock_tx.return_value.__enter__ = MagicMock(return_value=None)
                mock_tx.return_value.__exit__ = MagicMock(return_value=False)
                resp = OwnerCustomerLoyaltyGrantView.as_view()(
                    self._post_req({"delta": -30}), customer_id=42
                )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["loyalty_points"], 50)

    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_balance_floored_at_zero(self, _):
        """Deducting more than the current balance floors at 0, not negative."""
        mock_cust = MagicMock()
        mock_cust.loyalty_points = 30
        mock_cust.save = MagicMock()
        with patch("accounts.models.Customer") as MockCust:
            MockCust.DoesNotExist = _FakeDoesNotExist
            MockCust.objects.select_for_update.return_value.get.return_value = mock_cust
            with patch("django.db.transaction.atomic") as mock_tx:
                mock_tx.return_value.__enter__ = MagicMock(return_value=None)
                mock_tx.return_value.__exit__ = MagicMock(return_value=False)
                resp = OwnerCustomerLoyaltyGrantView.as_view()(
                    self._post_req({"delta": -9999}), customer_id=42
                )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["loyalty_points"], 0)
        self.assertEqual(mock_cust.loyalty_points, 0)
