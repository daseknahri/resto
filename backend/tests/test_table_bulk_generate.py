"""
Tests for TableBulkGenerateView
POST /api/owner/tables/bulk-generate/
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import TableBulkGenerateView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 1
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    return u


def _tenant(tid=1):
    return SimpleNamespace(id=tid, is_active=True)


def _tx_cm():
    """Return a no-op context manager for patching transaction.atomic."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TableBulkGenerateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TableBulkGenerateView.as_view()

    def _post(self, body, user=None, tenant=None):
        user = user or _owner()
        req = self.factory.post(
            "/api/owner/tables/bulk-generate/",
            body,
            format="json",
        )
        force_authenticate(req, user=user)
        req.user = user
        req.tenant = tenant or _tenant()
        return self.view(req)

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_returns_403(self):
        anon = MagicMock()
        anon.is_authenticated = False
        req = self.factory.post(
            "/api/owner/tables/bulk-generate/",
            {"prefix": "T", "count": 2},
            format="json",
        )
        req.user = anon
        req.tenant = _tenant()
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_tenant_returns_403(self):
        wrong_user = _owner(tenant_id=99)
        # Even with a valid body, wrong tenant → 403
        # Patch at serializer level to avoid DB. If auth passes we'd need more mocking,
        # so we just confirm 403 is returned before any work happens.
        resp = self._post(
            {"prefix": "Table", "count": 2},
            user=wrong_user,
            tenant=_tenant(tid=1),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Input validation ──────────────────────────────────────────────────────

    def test_invalid_prefix_returns_400(self):
        """Prefix with special chars not in the allowed set must return 400."""
        resp = self._post({"prefix": "T@ble!", "count": 2})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_count_exceeds_max_returns_400(self):
        """count > 120 (the max_value) must return 400."""
        resp = self._post({"prefix": "Table", "count": 200})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_count_zero_returns_400(self):
        """count < 1 (min_value=1) must return 400."""
        resp = self._post({"prefix": "Table", "count": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("menu.views.transaction")
    @patch("menu.views.TableLinkSerializer")
    def test_creates_correct_count_of_tables(self, mock_ts_class, mock_tx):
        """View returns 201 with created_count equal to the requested count."""
        mock_tx.atomic.return_value = _tx_cm()

        mock_inst = MagicMock()
        mock_inst.data = {"id": 1, "slug": "table-1", "label": "Table 1"}
        mock_ts_class.return_value = mock_inst

        resp = self._post({"prefix": "Table", "start": 1, "count": 5})

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["created_count"], 5)
        self.assertEqual(len(resp.data["created"]), 5)

    @patch("menu.views.transaction")
    @patch("menu.views.TableLinkSerializer")
    def test_labels_use_prefix_and_start_offset(self, mock_ts_class, mock_tx):
        """Each row_serializer must be constructed with label = f'{prefix} {start+offset}'."""
        mock_tx.atomic.return_value = _tx_cm()
        mock_inst = MagicMock()
        mock_inst.data = {}
        mock_ts_class.return_value = mock_inst

        self._post({"prefix": "VIP", "start": 3, "count": 2})

        # Inspect the data= kwargs of the write-serializer calls (every other call)
        write_calls = [
            c for c in mock_ts_class.call_args_list
            if c.kwargs.get("data") is not None
        ]
        labels = [c.kwargs["data"]["label"] for c in write_calls]
        self.assertEqual(labels, ["VIP 3", "VIP 4"])

    @patch("menu.views.transaction")
    @patch("menu.views.TableLinkSerializer")
    def test_default_prefix_is_table(self, mock_ts_class, mock_tx):
        """Omitting prefix uses the default 'Table'."""
        mock_tx.atomic.return_value = _tx_cm()
        mock_inst = MagicMock()
        mock_inst.data = {}
        mock_ts_class.return_value = mock_inst

        resp = self._post({"count": 1})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        write_calls = [
            c for c in mock_ts_class.call_args_list
            if c.kwargs.get("data") is not None
        ]
        self.assertTrue(write_calls[0].kwargs["data"]["label"].startswith("Table"))
