"""Wave I — WALLET-2 follow-up: server-side top-up-status endpoint.

Covered invariants:
  - Missing/blank session_id -> 400 (no DB touch, no Stripe call).
  - Unauthenticated -> 401 (IsCustomer denies; same 401-as-not-403 contract as
    the other customer-only endpoints).
  - Ledger is the truth: a TOPUP row with reference "stripe:<session_id>" for
    this customer -> "confirmed" with the SETTLED ledger amount + balance,
    without ever calling Stripe.
  - Another customer's credit is invisible: same session id, other customer
    -> "unknown" (ledger is scoped to the caller AND the Stripe ownership
    check fails closed).
  - No credit yet: Stripe session open/unpaid -> "pending"; paid but the
    webhook hasn't landed -> "pending" (keep waiting, never claim confirmed
    from Stripe alone); expired -> "failed"; Stripe error/unknown id -> 200
    "unknown", never a 500.
  - PSP off + no ledger row -> "unknown" (Stripe is never consulted).
  - Intent success_url carries session_id={CHECKOUT_SESSION_ID} so the
    returning page can ask about the session it just paid for.
  - Throttle: scope "customer_topup_status", 120/hour per customer; the
    121st poll in an hour is 429.

DB-backed classes skip locally (no local Postgres) via the _dbprobe pattern
from test_admin_wallet_bonus_readback.py; they run in the DB stage.
"""

import itertools
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

import _dbprobe
from accounts.models import Customer, WalletTransaction

_DB_AVAILABLE = _dbprobe.db_available()

_PSP_ON = dict(
    PSP_TOPUP_ENABLED=True,
    PSP_STRIPE_SECRET_KEY="sk_test_dummy",
    PSP_STRIPE_WEBHOOK_SECRET="whsec_test_dummy",
    PSP_SITE_URL="https://example.com",
    DEBUG=True,
)

_PSP_OFF = dict(
    PSP_TOPUP_ENABLED=False,
    PSP_STRIPE_SECRET_KEY="",
    PSP_STRIPE_WEBHOOK_SECRET="",
    PSP_SITE_URL="",
)

_phone_seq = itertools.count(600910010)


def _uphone():
    return "+212" + str(next(_phone_seq))


def _customer(balance="0"):
    return Customer.objects.create(phone=_uphone(), wallet_balance=Decimal(balance))


def _credit_row(customer, session_id, amount="150.00"):
    return WalletTransaction.objects.create(
        customer=customer,
        type=WalletTransaction.Type.TOPUP,
        amount=Decimal(amount),
        reference=f"stripe:{session_id}",
        currency="MAD",
        balance_after=Decimal(customer.wallet_balance),
    )


def _stripe_session(session_id="cs_test_1", customer_id="42", status="open",
                    payment_status="unpaid"):
    return {
        "id": session_id,
        "status": status,
        "payment_status": payment_status,
        "metadata": {"customer_id": str(customer_id), "amount": "150.00"},
        "client_reference_id": str(customer_id),
    }


def _stripe_mock(session=None, retrieve_error=None):
    mock_stripe = MagicMock()
    mock_stripe.api_key = ""
    if retrieve_error is not None:
        mock_stripe.checkout.Session.retrieve.side_effect = retrieve_error
    else:
        mock_stripe.checkout.Session.retrieve.return_value = session
    return mock_stripe


def _get_status(customer, session_id=None, view=None):
    from accounts.views import CustomerTopUpStatusView

    view = view or CustomerTopUpStatusView.as_view()
    factory = APIRequestFactory()
    url = "/api/customer/topup/status/"
    if session_id is not None:
        url += f"?session_id={session_id}"
    req = factory.get(url)
    req.session = {}
    if customer is not None:
        force_authenticate(req, user=customer)
    return view(req)


class StatusValidationTests(SimpleTestCase):
    """Param/auth validation runs before any ledger or Stripe touch."""

    def setUp(self):
        cache.clear()

    @override_settings(**_PSP_ON)
    def test_missing_session_id_is_400(self):
        resp = _get_status(Customer(id=1), session_id=None)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("session_id", resp.data.get("detail", ""))

    @override_settings(**_PSP_ON)
    def test_blank_session_id_is_400(self):
        resp = _get_status(Customer(id=1), session_id="   ")
        self.assertEqual(resp.status_code, 400)

    @override_settings(**_PSP_ON)
    def test_unauthenticated_is_401(self):
        resp = _get_status(None, session_id="cs_test_1")
        self.assertEqual(resp.status_code, 401)

    def test_throttle_scope_and_rate(self):
        from accounts.throttles import CustomerTopUpStatusThrottle

        throttle = CustomerTopUpStatusThrottle()
        self.assertEqual(throttle.scope, "customer_topup_status")
        self.assertEqual(throttle.get_rate(), "120/hour")


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class StatusLedgerTests(TestCase):
    """Ledger-first answers + Stripe fallback, on a real DB."""

    def setUp(self):
        cache.clear()
        self.customer = _customer(balance="150.00")

    @override_settings(**_PSP_ON)
    def test_confirmed_from_ledger_without_calling_stripe(self):
        _credit_row(self.customer, "cs_test_1", amount="150.00")
        # Stripe would explode if consulted — proving the ledger answers alone.
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.retrieve.side_effect = AssertionError(
            "ledger hit must not call Stripe"
        )
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "confirmed")
        self.assertEqual(resp.data["amount"], "150.00")
        self.assertEqual(resp.data["currency"], "MAD")
        self.assertEqual(resp.data["balance"], "150.00")
        self.assertIn("credited_at", resp.data)

    @override_settings(**_PSP_ON)
    def test_other_customers_credit_is_invisible(self):
        other = _customer(balance="150.00")
        _credit_row(other, "cs_other", amount="150.00")
        session = _stripe_session("cs_other", customer_id=other.id)
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_other")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")

    @override_settings(**_PSP_ON)
    def test_pending_for_open_unpaid_session(self):
        session = _stripe_session("cs_test_1", customer_id=self.customer.id,
                                  status="open", payment_status="unpaid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["payment_status"], "unpaid")
        self.assertEqual(resp.data["balance"], "150.00")

    @override_settings(**_PSP_ON)
    def test_paid_but_uncredited_is_pending_not_confirmed(self):
        """Stripe says paid but the webhook hasn't landed: keep waiting."""
        session = _stripe_session("cs_test_1", customer_id=self.customer.id,
                                  status="complete", payment_status="paid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["payment_status"], "paid")

    @override_settings(**_PSP_ON)
    def test_expired_session_is_failed(self):
        session = _stripe_session("cs_test_1", customer_id=self.customer.id,
                                  status="expired", payment_status="unpaid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "failed")

    @override_settings(**_PSP_ON)
    def test_stripe_error_is_unknown_not_500(self):
        mock = _stripe_mock(retrieve_error=Exception("stripe down"))
        with patch.dict("sys.modules", {"stripe": mock}):
            resp = _get_status(self.customer, "cs_nope")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")

    @override_settings(**_PSP_ON)
    def test_session_owned_by_another_customer_is_unknown(self):
        session = _stripe_session("cs_test_1", customer_id=999999)
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")

    @override_settings(**_PSP_OFF)
    def test_psp_off_without_ledger_row_is_unknown(self):
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.retrieve.side_effect = AssertionError(
            "PSP off must not call Stripe"
        )
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class StatusThrottleTests(TestCase):
    """Throttle: 120/hour per customer on the view."""

    def setUp(self):
        cache.clear()
        self.customer = _customer(balance="0")

    @override_settings(**_PSP_OFF)
    def test_120_polls_ok_121st_is_429(self):
        for i in range(120):
            resp = _get_status(self.customer, "cs_throttle")
            self.assertEqual(resp.status_code, 200, f"poll {i + 1} should succeed")
        resp = _get_status(self.customer, "cs_throttle")
        self.assertEqual(resp.status_code, 429)


class IntentSuccessUrlTests(SimpleTestCase):
    """The intent's success_url carries the session id back to /account."""

    def setUp(self):
        cache.clear()

    @override_settings(**_PSP_ON)
    def test_success_url_carries_session_id_placeholder(self):
        from accounts.views import CustomerTopUpIntentView

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.checkout.Session.create.return_value = mock_session
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "100"}, format="json")
        req.session = {}
        force_authenticate(req, user=Customer(id=1))
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("enabled"))
        kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        self.assertIn("session_id={CHECKOUT_SESSION_ID}", kwargs["success_url"])
        self.assertTrue(kwargs["success_url"].startswith("https://example.com/account?topup=success"))
        self.assertEqual(kwargs["cancel_url"], "https://example.com/account?topup=cancelled")
