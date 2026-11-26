"""Wave M M-07 tests: reconcile_topups command + kepoli.E003 check.

All Stripe calls are mocked (patch.dict sys.modules) — no live calls.
"""
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


def _stripe_session(*, paid=True, customer_id="7", amount_total=5000):
    return {
        "id": "cs_test_123",
        "payment_status": "paid" if paid else "unpaid",
        "amount_total": amount_total,
        "metadata": {"customer_id": customer_id},
    }


def _stripe_module(session):
    mock = MagicMock()
    mock.checkout.Session.retrieve.return_value = session
    return mock


class ReconcileTopupsTests(SimpleTestCase):
    def _run(self, session, *, topup_exists=False, session_id="cs_test_123"):
        stdout = StringIO()
        with patch.dict(sys.modules, {"stripe": _stripe_module(session)}), \
                patch("accounts.models.WalletTransaction") as WT, \
                patch("accounts.models.CustomerTopUpAttempt") as Attempt, \
                patch("accounts.wallet_service.credit_wallet") as credit:
            WT.Type.TOPUP = "topup"
            WT.objects.filter.return_value.exists.return_value = topup_exists
            Attempt.Status.CREDITED = "credited"
            with override_settings(PSP_STRIPE_SECRET_KEY="sk_test_x"):
                call_command("reconcile_topups", session_id, stdout=stdout)
        return stdout.getvalue(), credit, WT, Attempt

    def test_paid_without_topup_credits_once(self):
        out, credit, WT, Attempt = self._run(_stripe_session())
        credit.assert_called_once()
        _, kwargs = credit.call_args
        self.assertEqual(kwargs["customer_id"], "7")
        self.assertEqual(str(kwargs["amount"]), "50.00")
        self.assertEqual(kwargs["idempotency_key"], "reconciled:cs_test_123")
        self.assertEqual(kwargs["reference"], "stripe:cs_test_123")
        self.assertIn("reconciled", out)
        Attempt.objects.filter.assert_called()

    def test_second_run_is_noop_when_topup_row_exists(self):
        out, credit, WT, Attempt = self._run(_stripe_session(), topup_exists=True)
        credit.assert_not_called()
        self.assertIn("already credited", out)

    def test_unpaid_session_never_credits(self):
        out, credit, WT, Attempt = self._run(_stripe_session(paid=False))
        credit.assert_not_called()
        self.assertIn("not paid", out)

    def test_missing_sdk_is_a_clean_error(self):
        # sys.modules["stripe"] = None makes `import stripe` raise ImportError
        # even when the real SDK is installed on disk.
        with patch.dict(sys.modules, {"stripe": None}), \
                patch("accounts.models.WalletTransaction"), \
                patch("accounts.wallet_service.credit_wallet") as credit:
            with self.assertRaises(CommandError):
                call_command("reconcile_topups", "cs_test_123", stdout=StringIO())
        credit.assert_not_called()

    def test_missing_secret_is_a_clean_error(self):
        with patch.dict(sys.modules, {"stripe": _stripe_module(_stripe_session())}), \
                patch("accounts.wallet_service.credit_wallet") as credit:
            with override_settings(PSP_STRIPE_SECRET_KEY=""):
                with self.assertRaises(CommandError):
                    call_command("reconcile_topups", "cs_test_123", stdout=StringIO())
        credit.assert_not_called()

    def test_list_uncredited_lists_only_missing_rows(self):
        from types import SimpleNamespace
        attempts = [
            SimpleNamespace(session_id="cs_a", customer_id=1, amount="10.00", status="created"),
            SimpleNamespace(session_id="cs_b", customer_id=2, amount="20.00", status="created"),
        ]
        stdout = StringIO()
        with patch("accounts.models.WalletTransaction") as WT, \
                patch("accounts.models.CustomerTopUpAttempt") as Attempt:
            WT.Type.TOPUP = "topup"
            Attempt.Status.CREATED = "created"
            Attempt.objects.filter.return_value.order_by.return_value.__getitem__.return_value = attempts
            # cs_a already has a TOPUP row; cs_b does not.
            WT.objects.filter.return_value.exists.side_effect = [True, False]
            call_command("reconcile_topups", "--list-uncredited", stdout=stdout)
        out = stdout.getvalue()
        self.assertIn("cs_b", out)
        self.assertNotIn("cs_a", out)
        self.assertIn("1 uncredited", out)


class PspSiteUrlCheckTests(SimpleTestCase):
    def test_enabled_without_https_url_is_error(self):
        from config.checks import psp_site_url_configured
        with override_settings(DEBUG=False, PSP_TOPUP_ENABLED=True, PSP_SITE_URL="menu.example.com"):
            issues = psp_site_url_configured(None)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, "kepoli.E003")

    def test_enabled_with_https_url_is_clean(self):
        from config.checks import psp_site_url_configured
        with override_settings(DEBUG=False, PSP_TOPUP_ENABLED=True, PSP_SITE_URL="https://menu.example.com"):
            self.assertEqual(psp_site_url_configured(None), [])

    def test_disabled_is_clean(self):
        from config.checks import psp_site_url_configured
        with override_settings(DEBUG=False, PSP_TOPUP_ENABLED=False, PSP_SITE_URL="not-a-url"):
            self.assertEqual(psp_site_url_configured(None), [])

    def test_debug_is_clean(self):
        from config.checks import psp_site_url_configured
        with override_settings(DEBUG=True, PSP_TOPUP_ENABLED=True, PSP_SITE_URL="not-a-url"):
            self.assertEqual(psp_site_url_configured(None), [])
