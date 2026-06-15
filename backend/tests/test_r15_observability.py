"""R15 — observability hardening contract tests.

Two additive observability items (no behaviour change to the money paths themselves):

  FIX 1. [payments logger] Money-mutation failures (wallet/charge/commission/cash-out/
     float) must emit on a DEDICATED "payments" logger so a payment-failure rate can be
     alerted on separately from the general ERROR firehose. Asserts the logger is
     configured AND is actually invoked at representative money-failure sites:
       * wallet_service.debit_wallet → InsufficientFunds  (warning on "payments")
       * wallet_service.{credit,debit,transfer}_… idempotency-key collision (error)
       * accounts.views._credit_driver_earnings swallowed failure (exception on "payments")

  FIX 2. [request_id → Sentry tag] RequestLoggingMiddleware must stamp the per-request
     request_id onto the Sentry scope (so a Sentry 5xx pivots to its log line), guarded so
     it is a NO-OP — never a crash — when sentry_sdk is absent / Sentry isn't initialised.

House style: SimpleTestCase + MagicMock + assertLogs, no real DB.
"""
from __future__ import annotations

import logging
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1.a — the "payments" logger is configured (named logger, reaches Sentry)
# ═════════════════════════════════════════════════════════════════════════════

class PaymentsLoggerConfigTests(SimpleTestCase):
    def test_payments_logger_is_configured_in_settings(self):
        from django.conf import settings
        loggers = settings.LOGGING["loggers"]
        self.assertIn("payments", loggers, "a dedicated 'payments' logger must exist")
        cfg = loggers["payments"]
        # Has a handler so the SDK's callHandlers patch fires → still reaches Sentry.
        self.assertTrue(cfg.get("handlers"), "payments logger must have a handler")
        # INFO so error/warning money events always emit (not silenced to a higher floor).
        self.assertEqual(cfg.get("level"), "INFO")

    def test_payments_logger_not_disabled(self):
        """A getLogger('payments') call must yield a logger that emits (not NullHandler/off)."""
        self.assertFalse(logging.getLogger("payments").disabled)


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1.b — wallet_service emits on "payments" at money-failure branches
# ═════════════════════════════════════════════════════════════════════════════

class WalletServicePaymentsLoggingTests(SimpleTestCase):
    """The genuine money-failure branches in the central ledger log to 'payments'.

    No DB: the ledger functions are @transaction.atomic, so Atomic.__enter__/__exit__ are
    neutralised to no-ops (no real connection), and the customer/idempotency lookups are
    mocked so the failure branch is reached deterministically — all without a database.
    """

    def setUp(self):
        # Neutralise the @transaction.atomic decorator's DB touch so the function body
        # runs and reaches its failure branch without a real connection.
        p = patch.multiple(
            "django.db.transaction.Atomic",
            __enter__=lambda self: None,
            __exit__=lambda self, *exc: False,
        )
        p.start()
        self.addCleanup(p.stop)

    def test_debit_insufficient_funds_logs_to_payments(self):
        from accounts import wallet_service as ws
        from accounts.wallet_service import debit_wallet, InsufficientFunds

        cust = SimpleNamespace(wallet_balance=Decimal("5.00"))
        with patch.object(ws, "_find_idempotent", return_value=None), \
             patch.object(ws.Customer, "objects") as mock_objs:
            mock_objs.select_for_update.return_value.get.return_value = cust
            with self.assertLogs("payments", level="WARNING") as cm:
                with self.assertRaises(InsufficientFunds):
                    debit_wallet(42, "10.00", reference="ORD-1", tenant_id=7)
        joined = "\n".join(cm.output)
        self.assertIn("insufficient", joined.lower())
        self.assertIn("customer_id=42", joined)  # attributable by id, no PII/balance

    def test_debit_idempotency_collision_logs_to_payments(self):
        from accounts import wallet_service as ws
        from accounts.wallet_service import debit_wallet, WalletError

        # Existing tx resolves to a DIFFERENT customer → collision branch.
        existing = SimpleNamespace(customer_id=999)
        with patch.object(ws, "_find_idempotent", return_value=existing):
            with self.assertLogs("payments", level="ERROR") as cm:
                with self.assertRaises(WalletError):
                    debit_wallet(42, "10.00", idempotency_key="evil-key")
        joined = "\n".join(cm.output)
        self.assertIn("collision", joined.lower())
        self.assertIn("evil-key", joined)

    def test_credit_idempotency_collision_logs_to_payments(self):
        from accounts import wallet_service as ws
        from accounts.wallet_service import credit_wallet, WalletError

        existing = SimpleNamespace(customer_id=999)
        with patch.object(ws, "_find_idempotent", return_value=existing):
            with self.assertLogs("payments", level="ERROR") as cm:
                with self.assertRaises(WalletError):
                    credit_wallet(42, "10.00", idempotency_key="evil-key")
        self.assertIn("collision", "\n".join(cm.output).lower())

    def test_float_transfer_collision_logs_to_payments(self):
        from accounts import wallet_service as ws
        from accounts.wallet_service import transfer_to_customer, WalletError

        existing = SimpleNamespace(tenant_id=999)
        with patch.object(ws, "_find_idempotent_float", return_value=existing):
            with self.assertLogs("payments", level="ERROR") as cm:
                with self.assertRaises(WalletError):
                    transfer_to_customer(7, 42, "10.00", idempotency_key="evil-key")
        self.assertIn("collision", "\n".join(cm.output).lower())

    def test_p2p_transfer_collision_logs_to_payments(self):
        from accounts import wallet_service as ws
        from accounts.wallet_service import transfer_between_customers, WalletError

        existing = SimpleNamespace(customer_id=999)
        with patch.object(ws, "_find_idempotent", return_value=existing):
            with self.assertLogs("payments", level="ERROR") as cm:
                with self.assertRaises(WalletError):
                    transfer_between_customers(42, 43, "10.00", idempotency_key="evil-key")
        self.assertIn("collision", "\n".join(cm.output).lower())


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1.c — a SWALLOWED money failure (driver earning) emits on "payments"
# ═════════════════════════════════════════════════════════════════════════════

class DriverEarningSwallowedFailureLoggingTests(SimpleTestCase):
    """_credit_driver_earnings swallows errors so a delivery still completes, but the
    failure must be alertable + reconcilable → it now logs on the 'payments' channel."""

    def test_credit_failure_is_logged_to_payments_not_swallowed_silently(self):
        from accounts import views as av

        job = SimpleNamespace(
            id=55, driver_id=8, tenant_id=3, order_number="ORD-9",
            driver_payout=Decimal("12.00"),
        )
        # _credit_driver_earnings imports credit_wallet from wallet_service at call time;
        # force the money mutation to blow up. The function must catch + log, never raise.
        with patch("accounts.wallet_service.credit_wallet", side_effect=RuntimeError("db down")):
            with self.assertLogs("payments", level="ERROR") as cm:
                av._credit_driver_earnings(job)  # must NOT raise
        joined = "\n".join(cm.output)
        self.assertIn("job_id=55", joined)
        self.assertIn("driver_id=8", joined)


# ═════════════════════════════════════════════════════════════════════════════
# FIX 2 — middleware stamps request_id onto the Sentry scope, guarded
# ═════════════════════════════════════════════════════════════════════════════

class RequestIdSentryTagTests(SimpleTestCase):
    """RequestLoggingMiddleware sets the request_id Sentry tag when sentry_sdk is present,
    and is a no-op (no crash) when it is absent."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _run(self, request):
        from config.middleware import RequestLoggingMiddleware
        mw = RequestLoggingMiddleware(lambda req: HttpResponse("ok"))
        return mw(request)

    def test_sets_request_id_tag_when_sentry_present(self):
        fake_sentry = MagicMock()
        request = self.factory.get("/api/health/", HTTP_X_REQUEST_ID="req-abc-123")
        with patch.dict(sys.modules, {"sentry_sdk": fake_sentry}):
            resp = self._run(request)
        self.assertEqual(resp.status_code, 200)
        fake_sentry.set_tag.assert_any_call("request_id", "req-abc-123")
        # The middleware also exposes the id on the request + response header.
        self.assertEqual(request.request_id, "req-abc-123")
        self.assertEqual(resp["X-Request-ID"], "req-abc-123")

    def test_no_crash_when_sentry_absent(self):
        """import sentry_sdk → ImportError must be swallowed; the request still succeeds."""
        request = self.factory.get("/api/health/", HTTP_X_REQUEST_ID="req-xyz")
        # sys.modules['sentry_sdk'] = None makes `import sentry_sdk` raise ImportError.
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            resp = self._run(request)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(request.request_id, "req-xyz")

    def test_no_crash_when_set_tag_raises(self):
        """Even if Sentry is imported but set_tag blows up (e.g. not initialised), the
        guard must keep the request alive."""
        fake_sentry = MagicMock()
        fake_sentry.set_tag.side_effect = RuntimeError("sentry not initialised")
        request = self.factory.get("/api/health/")
        with patch.dict(sys.modules, {"sentry_sdk": fake_sentry}):
            resp = self._run(request)
        self.assertEqual(resp.status_code, 200)

    def test_tag_set_for_generated_request_id_when_header_absent(self):
        fake_sentry = MagicMock()
        request = self.factory.get("/api/health/")
        with patch.dict(sys.modules, {"sentry_sdk": fake_sentry}):
            self._run(request)
        # A request_id is generated when no X-Request-ID header is present; the tag uses it.
        fake_sentry.set_tag.assert_any_call("request_id", request.request_id)
        self.assertTrue(request.request_id)
