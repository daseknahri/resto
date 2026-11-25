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
import json
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
    # Wave K F-12: a real post-credit state has the balance bumped WITH the
    # TX (atomic in credit_wallet). The old fixture left wallet_balance at
    # its pre-credit value, so the balance assertion could not catch a
    # balance-computation bug.
    row = WalletTransaction.objects.create(
        customer=customer,
        type=WalletTransaction.Type.TOPUP,
        amount=Decimal(amount),
        reference=f"stripe:{session_id}",
        currency="MAD",
        balance_after=Decimal(customer.wallet_balance) + Decimal(amount),
    )
    customer.wallet_balance = customer.wallet_balance + Decimal(amount)
    customer.save(update_fields=["wallet_balance"])
    return row


def _stripe_session(session_id="cs_test_1", customer_id="42", status="open",
                    payment_status="unpaid"):
    return {
        "id": session_id,
        "status": status,
        "payment_status": payment_status,
        "metadata": {"customer_id": str(customer_id), "amount": "150.00"},
        "client_reference_id": str(customer_id),
    }


class InvalidRequestError(Exception):
    """Stand-in for stripe.error.InvalidRequestError (the mocked stripe
    module has no real error classes, so the view classifies by name)."""


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
        self.assertEqual(resp.data["retryable"], False)
        self.assertEqual(resp.data["amount"], "150.00")
        self.assertEqual(resp.data["currency"], "MAD")
        self.assertEqual(resp.data["balance"], "300.00")
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
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_ON)
    def test_pending_for_open_unpaid_session(self):
        session = _stripe_session("cs_test_1", customer_id=self.customer.id,
                                  status="open", payment_status="unpaid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["retryable"], True)
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
        self.assertEqual(resp.data["retryable"], True)
        self.assertEqual(resp.data["payment_status"], "paid")

    @override_settings(**_PSP_ON)
    def test_expired_session_is_failed(self):
        session = _stripe_session("cs_test_1", customer_id=self.customer.id,
                                  status="expired", payment_status="unpaid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "failed")
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_ON)
    def test_stripe_error_is_unknown_not_500(self):
        mock = _stripe_mock(retrieve_error=Exception("stripe down"))
        with patch.dict("sys.modules", {"stripe": mock}):
            resp = _get_status(self.customer, "cs_nope")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")
        self.assertEqual(resp.data["retryable"], True)

    @override_settings(**_PSP_ON)
    def test_session_owned_by_another_customer_is_unknown(self):
        session = _stripe_session("cs_test_1", customer_id=999999)
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_OFF)
    def test_confirmed_despite_psp_off(self):
        """Wave K F-12: ledger-first ordering — a credited top-up answers
        confirmed even with PSP off (the invariant the old suite never
        locked in; a reorder of the two checks would silently break it)."""
        _credit_row(self.customer, "cs_test_1", amount="150.00")
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.retrieve.side_effect = AssertionError(
            "ledger hit must not call Stripe"
        )
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "confirmed")
        self.assertEqual(resp.data["retryable"], False)
        self.assertEqual(resp.data["balance"], "300.00")

    @override_settings(**_PSP_ON)
    def test_client_reference_id_fallback_match(self):
        """Wave K F-12: metadata empty + client_reference_id match -> pending."""
        session = {
            "id": "cs_test_1", "status": "open", "payment_status": "unpaid",
            "metadata": {},
            "client_reference_id": str(self.customer.id),
        }
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "pending")
        self.assertEqual(resp.data["retryable"], True)

    @override_settings(**_PSP_ON)
    def test_client_reference_id_fallback_mismatch(self):
        """Wave K F-12: metadata empty + client_reference_id mismatch -> unknown."""
        session = {
            "id": "cs_test_1", "status": "open", "payment_status": "unpaid",
            "metadata": {},
            "client_reference_id": "999999",
        }
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_ON)
    def test_no_such_session_is_terminal_unknown(self):
        """Wave K F-03: 'No such checkout.session' never resolves — retryable False."""
        mock = _stripe_mock(retrieve_error=InvalidRequestError("No such checkout.session: 'cs_nope'"))
        with patch.dict("sys.modules", {"stripe": mock}):
            resp = _get_status(self.customer, "cs_nope")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_ON)
    def test_stripe_sdk_missing_is_terminal_unknown(self):
        """Wave K F-03: Stripe SDK missing — unknown, never retryable."""
        with patch.dict("sys.modules", {"stripe": None}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "unknown")
        self.assertEqual(resp.data["retryable"], False)

    @override_settings(**_PSP_ON)
    def test_failed_attempt_row_is_failed_without_calling_stripe(self):
        """Wave K F-05: a webhook-marked failed attempt answers "failed"
        (Stripe never consulted, PSP flag irrelevant)."""
        from accounts.models import CustomerTopUpAttempt
        CustomerTopUpAttempt.objects.create(
            customer=self.customer, session_id="cs_test_1", amount=Decimal("150.00"),
            status=CustomerTopUpAttempt.Status.FAILED,
        )
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.retrieve.side_effect = AssertionError(
            "failed attempt must not call Stripe"
        )
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = _get_status(self.customer, "cs_test_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "failed")
        self.assertEqual(resp.data["payment_status"], "unpaid")
        self.assertEqual(resp.data["retryable"], False)

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
        self.assertEqual(resp.data["retryable"], False)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class StatusThrottleTests(TestCase):
    """Wave K F-01: only the Stripe-retrieve path counts against the bucket."""

    def setUp(self):
        cache.clear()
        self.customer = _customer(balance="0")

    @override_settings(**_PSP_OFF)
    def test_psp_off_unknown_is_never_throttled(self):
        """The cheap PSP-off answer is not a Stripe call — 121 polls, all 200."""
        for i in range(121):
            resp = _get_status(self.customer, "cs_throttle")
            self.assertEqual(resp.status_code, 200, f"poll {i + 1} should succeed")
            self.assertEqual(resp.data["status"], "unknown")

    @override_settings(**_PSP_ON)
    def test_ledger_confirmed_is_never_throttled(self):
        """A ledger-confirmed answer is never throttled — 121 polls, all 200 confirmed."""
        _credit_row(self.customer, "cs_throttle", amount="150.00")
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.retrieve.side_effect = AssertionError(
            "ledger hit must not call Stripe"
        )
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            for i in range(121):
                resp = _get_status(self.customer, "cs_throttle")
                self.assertEqual(resp.status_code, 200, f"poll {i + 1} should succeed")
                self.assertEqual(resp.data["status"], "confirmed")

    @override_settings(**_PSP_ON)
    def test_stripe_path_polls_still_throttle_at_121(self):
        """Only the Stripe-retrieve path counts — 120 pending polls OK, 121st is 429."""
        session = _stripe_session("cs_throttle", customer_id=self.customer.id,
                                  status="open", payment_status="unpaid")
        with patch.dict("sys.modules", {"stripe": _stripe_mock(session)}):
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


def _get_attempts(customer, view=None):
    from accounts.views import CustomerTopUpAttemptsView

    view = view or CustomerTopUpAttemptsView.as_view()
    factory = APIRequestFactory()
    req = factory.get("/api/customer/topup/attempts/")
    req.session = {}
    if customer is not None:
        force_authenticate(req, user=customer)
    return view(req)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class TopUpAttemptsTests(TestCase):
    """Wave K F-08: intent persists an attempt row; the list endpoint surfaces it."""

    def setUp(self):
        cache.clear()
        self.customer = _customer(balance="150.00")

    def _post_intent(self, customer, amount="100"):
        from accounts.views import CustomerTopUpIntentView

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        mock_session.id = "cs_test_1"
        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.checkout.Session.create.return_value = mock_session
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": amount}, format="json")
        req.session = {}
        force_authenticate(req, user=customer)
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            return CustomerTopUpIntentView.as_view()(req)

    @override_settings(**_PSP_ON)
    def test_intent_persists_attempt_row(self):
        resp = self._post_intent(self.customer)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("enabled"))
        from accounts.models import CustomerTopUpAttempt

        row = CustomerTopUpAttempt.objects.get(session_id="cs_test_1")
        self.assertEqual(row.customer_id, self.customer.id)
        self.assertEqual(str(row.amount), "100.00")
        self.assertEqual(row.currency, "MAD")
        self.assertEqual(row.status, CustomerTopUpAttempt.Status.CREATED)

    @override_settings(**_PSP_ON)
    def test_attempts_list_returns_own_attempts_newest_first(self):
        from accounts.models import CustomerTopUpAttempt

        other = _customer(balance="0")
        CustomerTopUpAttempt.objects.create(
            customer=self.customer, session_id="cs_old", amount=Decimal("50.00")
        )
        CustomerTopUpAttempt.objects.create(
            customer=self.customer, session_id="cs_new", amount=Decimal("100.00"),
            status=CustomerTopUpAttempt.Status.CREDITED,
        )
        CustomerTopUpAttempt.objects.create(
            customer=other, session_id="cs_other", amount=Decimal("25.00")
        )
        resp = _get_attempts(self.customer)
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["attempts"]
        self.assertEqual([r["session_id"] for r in rows], ["cs_new", "cs_old"])
        self.assertEqual(rows[0]["status"], "credited")
        self.assertEqual(rows[0]["amount"], "100.00")
        self.assertEqual(rows[1]["status"], "created")

    @override_settings(**_PSP_OFF)
    def test_attempts_list_works_with_psp_off(self):
        from accounts.models import CustomerTopUpAttempt

        CustomerTopUpAttempt.objects.create(
            customer=self.customer, session_id="cs_off", amount=Decimal("75.00")
        )
        resp = _get_attempts(self.customer)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["attempts"]), 1)

    def test_attempts_unauthenticated_is_401(self):
        resp = _get_attempts(None)
        self.assertEqual(resp.status_code, 401)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="needs Postgres")
class WebhookAttemptRowTests(TestCase):
    """Wave K F-05/F-08: the webhook marks the local attempt row credited/failed."""

    _PSP_WEBHOOK = dict(
        PSP_TOPUP_ENABLED=True,
        PSP_STRIPE_SECRET_KEY="sk_test_dummy",
        PSP_STRIPE_WEBHOOK_SECRET="",  # unsigned JSON path (DEBUG-only)
        PSP_SITE_URL="https://example.com",
        DEBUG=True,
    )

    def setUp(self):
        cache.clear()
        self.customer = _customer(balance="150.00")

    def _post_webhook(self, event):
        from accounts.views import CustomerTopUpWebhookView

        payload = json.dumps(event).encode()
        factory = APIRequestFactory()
        req = factory.post(
            "/api/customer/topup/webhook/", data=payload, content_type="application/json"
        )
        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.error.SignatureVerificationError = Exception
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            return CustomerTopUpWebhookView.as_view()(req)

    def _attempt(self, session_id="cs_test_abc", amount="150.00"):
        from accounts.models import CustomerTopUpAttempt

        return CustomerTopUpAttempt.objects.create(
            customer=self.customer, session_id=session_id, amount=Decimal(amount)
        )

    @override_settings(**_PSP_WEBHOOK)
    def test_completed_event_marks_attempt_credited(self):
        self._attempt()
        event = {"id": "evt_k1", "type": "checkout.session.completed",
                 "data": {"object": {"id": "cs_test_abc", "payment_status": "paid",
                                     "amount_total": 15000,
                                     "metadata": {"customer_id": str(self.customer.id),
                                                  "amount": "150.00"}}}}
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("ok"))
        from accounts.models import CustomerTopUpAttempt

        row = CustomerTopUpAttempt.objects.get(session_id="cs_test_abc")
        self.assertEqual(row.status, CustomerTopUpAttempt.Status.CREDITED)
        # Real credit_wallet, real DB: the ledger row exists and the balance moved.
        self.assertTrue(WalletTransaction.objects.filter(
            customer=self.customer, reference="stripe:cs_test_abc").exists())
        self.customer.refresh_from_db()
        self.assertEqual(str(self.customer.wallet_balance), "300.00")

    @override_settings(**_PSP_WEBHOOK)
    def test_async_payment_failed_marks_attempt_failed_and_never_credits(self):
        self._attempt()
        event = {"id": "evt_k2", "type": "checkout.session.async_payment_failed",
                 "data": {"object": {"id": "cs_test_abc", "payment_status": "unpaid",
                                     "amount_total": 15000,
                                     "metadata": {"customer_id": str(self.customer.id)}}}}
        resp = self._post_webhook(event)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("ok"))
        from accounts.models import CustomerTopUpAttempt

        row = CustomerTopUpAttempt.objects.get(session_id="cs_test_abc")
        self.assertEqual(row.status, CustomerTopUpAttempt.Status.FAILED)
        self.assertFalse(WalletTransaction.objects.filter(
            customer=self.customer, reference="stripe:cs_test_abc").exists())
