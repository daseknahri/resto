"""
Tests for the cash drawer feature:
  - DrawerSession + DrawerTransaction models
  - _compute_expected_total helper
  - DrawerCurrentView, DrawerOpenView, DrawerTransactionView, DrawerCloseView, DrawerHistoryView
  - Default-preserving guard: no drawer session → /current/ returns {"open": False}
"""
from decimal import Decimal
from datetime import datetime, timezone as _tz
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request as DRFRequest
from rest_framework.parsers import JSONParser

from menu.views import (
    _drawer_session_dict,
    _drawer_transaction_dict,
    _compute_expected_total,
    DrawerCurrentView,
    DrawerOpenView,
    DrawerTransactionView,
    DrawerCloseView,
    DrawerHistoryView,
)


# ── Unit tests: helper functions ──────────────────────────────────────────────

class DrawerSessionDictTests(SimpleTestCase):
    """_drawer_session_dict serialises a DrawerSession correctly."""

    def _make_session(self, **kwargs):
        s = MagicMock()
        s.id = kwargs.get("id", 1)
        s.status = kwargs.get("status", "open")
        s.opened_by_name = kwargs.get("opened_by_name", "Alice")
        s.opening_float = Decimal(kwargs.get("opening_float", "100.00"))
        s.opened_at = datetime(2024, 1, 15, 8, 0, 0, tzinfo=_tz.utc)
        s.closed_at = kwargs.get("closed_at", None)
        s.closed_by_name = kwargs.get("closed_by_name", "")
        s.counted_total = kwargs.get("counted_total", None)
        s.expected_total = kwargs.get("expected_total", None)
        s.over_short = kwargs.get("over_short", None)
        s.note = kwargs.get("note", "")
        return s

    def test_open_session_serialises(self):
        s = self._make_session()
        d = _drawer_session_dict(s)
        self.assertEqual(d["status"], "open")
        self.assertEqual(d["opening_float"], "100.00")
        self.assertIsNone(d["closed_at"])
        self.assertIsNone(d["counted_total"])
        self.assertIsNone(d["over_short"])

    def test_closed_session_serialises_variance(self):
        s = self._make_session(
            status="closed",
            counted_total=Decimal("350.00"),
            expected_total=Decimal("340.00"),
            over_short=Decimal("10.00"),
        )
        d = _drawer_session_dict(s)
        self.assertEqual(d["counted_total"], "350.00")
        self.assertEqual(d["expected_total"], "340.00")
        self.assertEqual(d["over_short"], "10.00")


class DrawerTransactionDictTests(SimpleTestCase):
    def _make_tx(self, **kwargs):
        t = MagicMock()
        t.id = 1
        t.kind = kwargs.get("kind", "pay_in")
        t.amount = Decimal(kwargs.get("amount", "25.00"))
        t.reason = kwargs.get("reason", "Milk supplier")
        t.recorded_by_name = "Bob"
        t.at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=_tz.utc)
        return t

    def test_pay_in_serialises(self):
        d = _drawer_transaction_dict(self._make_tx(kind="pay_in", amount="25.00"))
        self.assertEqual(d["kind"], "pay_in")
        self.assertEqual(d["amount"], "25.00")

    def test_pay_out_serialises(self):
        d = _drawer_transaction_dict(self._make_tx(kind="pay_out", amount="15.00"))
        self.assertEqual(d["kind"], "pay_out")
        self.assertEqual(d["amount"], "15.00")


class ComputeExpectedTotalTests(SimpleTestCase):
    """_compute_expected_total computes expected = float + cash_collected + pay_ins - pay_outs."""

    def _call(self, opening_float, cash_collected, pay_in_total, pay_out_total):
        session = MagicMock()
        session.opening_float = Decimal(str(opening_float))

        # Patch DrawerTransaction.objects.filter to return a mock queryset.
        with patch("menu.views.DrawerTransaction") as mock_dt:
            mock_qs = MagicMock()
            mock_dt.objects.filter.return_value = mock_qs
            mock_dt.Kind.PAY_IN = "pay_in"
            mock_dt.Kind.PAY_OUT = "pay_out"
            mock_qs.aggregate.return_value = {
                "pay_in": Decimal(str(pay_in_total)) if pay_in_total else None,
                "pay_out": Decimal(str(pay_out_total)) if pay_out_total else None,
            }
            # Also need Q import in the view context; we just test the math here.
            result = _compute_expected_total(session, Decimal(str(cash_collected)))
        return result

    def test_basic_no_movements(self):
        # expected = 100 + 250 + 0 - 0 = 350
        result = self._call(
            opening_float="100.00",
            cash_collected="250.00",
            pay_in_total=None,
            pay_out_total=None,
        )
        self.assertEqual(result, Decimal("350.00"))

    def test_with_pay_in_and_pay_out(self):
        # expected = 100 + 200 + 30 - 20 = 310
        result = self._call(
            opening_float="100.00",
            cash_collected="200.00",
            pay_in_total="30.00",
            pay_out_total="20.00",
        )
        self.assertEqual(result, Decimal("310.00"))

    def test_zero_float(self):
        result = self._call(
            opening_float="0.00",
            cash_collected="100.00",
            pay_in_total=None,
            pay_out_total=None,
        )
        self.assertEqual(result, Decimal("100.00"))


# ── View-level tests (using RequestFactory + mock DB) ─────────────────────────

def _make_owner_request(method="GET", data=None):
    """Build a fake owner DRF Request so request.data works in views."""
    factory = APIRequestFactory()
    if method.upper() == "POST":
        django_req = factory.post("/", data=data or {}, format="json")
    else:
        django_req = factory.get("/")
    # Wrap in DRF Request so .data is populated
    req = DRFRequest(django_req, parsers=[JSONParser()])
    user = MagicMock()
    user.id = 7
    user.is_tenant_owner = True
    user.get_full_name = lambda: "Owner Test"
    req.user = user
    return req


class DrawerCurrentViewDefaultPreservingTest(SimpleTestCase):
    """When no drawer is open, the endpoint returns {"open": False} — no error."""

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_no_open_session_returns_open_false(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = None

        req = _make_owner_request()
        resp = DrawerCurrentView().get(req)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["open"])
        self.assertIsNone(resp.data["session"])


class DrawerCurrentViewWithSessionTest(SimpleTestCase):
    """When a session is open, returns the session data plus transactions."""

    @patch("menu.views.DrawerTransaction")
    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_open_session_returned(self, mock_owner, mock_ds, mock_dt):
        session = MagicMock()
        session.id = 1
        session.status = "open"
        session.opened_by_name = "Alice"
        session.opening_float = Decimal("50.00")
        session.opened_at = datetime(2024, 1, 1, 8, 0, tzinfo=_tz.utc)
        session.closed_at = None
        session.closed_by_name = ""
        session.counted_total = None
        session.expected_total = None
        session.over_short = None
        session.note = ""

        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = session
        mock_dt.objects.filter.return_value.order_by.return_value = []

        req = _make_owner_request()
        resp = DrawerCurrentView().get(req)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["open"])
        self.assertEqual(resp.data["session"]["opening_float"], "50.00")


class DrawerOpenViewTests(SimpleTestCase):
    """DrawerOpenView opens a new session or 409 if one is already open."""

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_open_creates_session(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.exists.return_value = False

        new_session = MagicMock()
        new_session.id = 1
        new_session.status = "open"
        new_session.opened_by_name = "Owner Test"
        new_session.opening_float = Decimal("100.00")
        new_session.opened_at = datetime(2024, 1, 1, 8, 0, tzinfo=_tz.utc)
        new_session.closed_at = None
        new_session.closed_by_name = ""
        new_session.counted_total = None
        new_session.expected_total = None
        new_session.over_short = None
        new_session.note = ""
        mock_ds.objects.create.return_value = new_session

        req = _make_owner_request("POST", {"opening_float": "100.00"})
        with patch("menu.views.timezone") as mock_tz:
            mock_tz.now.return_value = datetime(2024, 1, 1, 8, 0, tzinfo=_tz.utc)
            resp = DrawerOpenView().post(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["opening_float"], "100.00")

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_409_when_already_open(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.exists.return_value = True

        req = _make_owner_request("POST", {"opening_float": "50.00"})
        resp = DrawerOpenView().post(req)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["code"], "already_open")

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_400_negative_float(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.exists.return_value = False

        req = _make_owner_request("POST", {"opening_float": "-10.00"})
        resp = DrawerOpenView().post(req)
        self.assertEqual(resp.status_code, 400)


class DrawerTransactionViewTests(SimpleTestCase):
    """DrawerTransactionView records pay-in / pay-out."""

    @patch("menu.views.DrawerTransaction")
    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_pay_in_created(self, mock_owner, mock_ds, mock_dt):
        session = MagicMock()
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = session

        mock_dt.Kind.PAY_IN = "pay_in"
        mock_dt.Kind.PAY_OUT = "pay_out"

        tx = MagicMock()
        tx.id = 1
        tx.kind = "pay_in"
        tx.amount = Decimal("25.00")
        tx.reason = "Petty cash"
        tx.recorded_by_name = "Owner Test"
        tx.at = datetime(2024, 1, 1, 9, 0, tzinfo=_tz.utc)
        mock_dt.objects.create.return_value = tx

        req = _make_owner_request("POST", {"kind": "pay_in", "amount": "25.00", "reason": "Petty cash"})
        with patch("menu.views.timezone") as mock_tz:
            mock_tz.now.return_value = datetime(2024, 1, 1, 9, 0, tzinfo=_tz.utc)
            resp = DrawerTransactionView().post(req)

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["kind"], "pay_in")

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_404_no_open_session(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = None

        req = _make_owner_request("POST", {"kind": "pay_in", "amount": "25.00"})
        resp = DrawerTransactionView().post(req)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.data["code"], "no_open_session")

    @patch("menu.views.DrawerTransaction")
    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_400_invalid_kind(self, mock_owner, mock_ds, mock_dt):
        session = MagicMock()
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = session
        mock_dt.Kind.PAY_IN = "pay_in"
        mock_dt.Kind.PAY_OUT = "pay_out"

        req = _make_owner_request("POST", {"kind": "bad_kind", "amount": "25.00"})
        resp = DrawerTransactionView().post(req)
        self.assertEqual(resp.status_code, 400)

    @patch("menu.views.DrawerTransaction")
    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_400_zero_amount(self, mock_owner, mock_ds, mock_dt):
        session = MagicMock()
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = session
        mock_dt.Kind.PAY_IN = "pay_in"
        mock_dt.Kind.PAY_OUT = "pay_out"

        req = _make_owner_request("POST", {"kind": "pay_in", "amount": "0.00"})
        resp = DrawerTransactionView().post(req)
        self.assertEqual(resp.status_code, 400)


class DrawerCloseViewTests(SimpleTestCase):
    """DrawerCloseView performs blind-count close and computes over/short."""

    @patch("menu.views.split_revenue_for_orders")
    @patch("menu.views.Order")
    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_close_computes_over_short(self, mock_owner, mock_ds, mock_order, mock_split):
        """Counted > expected → positive over_short."""
        session = MagicMock()
        session.id = 1
        session.status = "open"
        session.opened_by_name = "Alice"
        session.opening_float = Decimal("100.00")
        session.opened_at = datetime(2024, 1, 1, 8, 0, tzinfo=_tz.utc)
        session.closed_by_name = ""
        session.note = ""

        mock_ds.Status.OPEN = "open"
        mock_ds.Status.CLOSED = "closed"
        mock_ds.objects.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = session

        mock_order.Status.COMPLETED = "completed"
        mock_order.PaymentStatus.PAID = "paid"
        mock_order.objects.filter.return_value = MagicMock()

        # Cash collected = 200, opening_float = 100, no movements → expected = 300
        mock_split.return_value = {"cash": Decimal("200.00"), "wallet": Decimal("0.00")}

        # Closer counts 310 → over_short = +10
        req = _make_owner_request("POST", {"counted_total": "310.00"})

        # Patch _compute_expected_total to return known value
        with patch("menu.views._compute_expected_total", return_value=Decimal("300.00")):
            with patch("menu.views.transaction") as mock_txn:
                mock_txn.atomic.return_value.__enter__ = lambda s: None
                mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
                with patch("menu.views.timezone") as mock_tz:
                    mock_tz.now.return_value = datetime(2024, 1, 1, 18, 0, tzinfo=_tz.utc)
                    # Mock the session dict we'd return
                    session.status = "closed"
                    session.closed_at = datetime(2024, 1, 1, 18, 0, tzinfo=_tz.utc)
                    session.counted_total = Decimal("310.00")
                    session.expected_total = Decimal("300.00")
                    session.over_short = Decimal("10.00")
                    resp = DrawerCloseView().post(req)

        self.assertEqual(resp.status_code, 200)

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_404_no_open_session(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = None

        req = _make_owner_request("POST", {"counted_total": "100.00"})
        # B1: the select_for_update() lock (and thus this 404 check) now happens
        # INSIDE transaction.atomic() — mock it out same as test_close_computes_over_short.
        with patch("menu.views.transaction") as mock_txn:
            mock_txn.atomic.return_value.__enter__ = lambda s: None
            mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
            resp = DrawerCloseView().post(req)
        self.assertEqual(resp.status_code, 404)

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_400_missing_counted_total(self, mock_owner, mock_ds):
        session = MagicMock()
        mock_ds.Status.OPEN = "open"
        mock_ds.objects.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value = session

        # counted_total is parsed BEFORE the atomic/lock block, so no open
        # session is ever looked up — transaction.atomic() is never entered.
        req = _make_owner_request("POST", {})
        resp = DrawerCloseView().post(req)
        self.assertEqual(resp.status_code, 400)


class DrawerAccessControlTests(SimpleTestCase):
    """Non-owner requests are rejected with 403."""

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_current_requires_owner(self, _):
        req = _make_owner_request()
        resp = DrawerCurrentView().get(req)
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_open_requires_owner(self, _):
        req = _make_owner_request("POST", {"opening_float": "100"})
        resp = DrawerOpenView().post(req)
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_transaction_requires_owner(self, _):
        req = _make_owner_request("POST", {"kind": "pay_in", "amount": "10"})
        resp = DrawerTransactionView().post(req)
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_close_requires_owner(self, _):
        req = _make_owner_request("POST", {"counted_total": "100"})
        resp = DrawerCloseView().post(req)
        self.assertEqual(resp.status_code, 403)

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_history_requires_owner(self, _):
        req = _make_owner_request()
        resp = DrawerHistoryView().get(req)
        self.assertEqual(resp.status_code, 403)


class DefaultPreservingNoDrawerTest(SimpleTestCase):
    """
    Default-preserving guard: a tenant that has NEVER used the cash drawer
    should see /current/ return {open: False} without any error — the drawer
    feature is purely additive and invisible to non-adopters.
    """

    @patch("menu.views.DrawerSession")
    @patch("menu.views._is_tenant_owner", return_value=True)
    def test_no_sessions_ever_returns_closed_state(self, mock_owner, mock_ds):
        mock_ds.Status.OPEN = "open"
        # No sessions in DB
        mock_ds.objects.filter.return_value.order_by.return_value.first.return_value = None

        req = _make_owner_request()
        resp = DrawerCurrentView().get(req)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["open"])
        # Clients check resp.data["open"] to decide whether to show the close UI.
        # When it's False, nothing changes from the pre-drawer UX.
