"""
Tests for delivery-code proof (DV1) + driver wallet earnings (DV2) helpers.

Unit-level (SimpleTestCase + mocks — no DB).
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from menu.views import _generate_delivery_code
from accounts.views import _credit_driver_earnings


class GenerateDeliveryCodeTests(SimpleTestCase):
    def test_is_four_digit_string(self):
        for _ in range(50):
            code = _generate_delivery_code()
            self.assertEqual(len(code), 4)
            self.assertTrue(code.isdigit())


class CreditDriverEarningsTests(SimpleTestCase):
    def _job(self, driver_id=5, payout="12.00", order_number="ORD-1", job_id=9):
        return SimpleNamespace(driver_id=driver_id, driver_payout=payout,
                               order_number=order_number, tenant_id=7, id=job_id)

    @patch("accounts.wallet_service.credit_wallet")
    def test_credits_wallet_with_earning_type(self, credit):
        from accounts.models import WalletTransaction
        _credit_driver_earnings(self._job())
        credit.assert_called_once()
        kw = credit.call_args.kwargs
        args = credit.call_args.args
        self.assertEqual(args[0], 5)                       # driver_id
        self.assertEqual(kw["tx_type"], WalletTransaction.Type.EARNING)
        self.assertEqual(kw["idempotency_key"], "earning:9")  # idempotent per job
        self.assertFalse(kw["require_verified"])           # earnings bypass phone gate

    @patch("accounts.wallet_service.credit_wallet")
    def test_no_driver_is_noop(self, credit):
        _credit_driver_earnings(self._job(driver_id=None))
        credit.assert_not_called()

    @patch("accounts.wallet_service.credit_wallet")
    def test_zero_payout_is_noop(self, credit):
        _credit_driver_earnings(self._job(payout="0"))
        credit.assert_not_called()

    @patch("accounts.wallet_service.credit_wallet", side_effect=RuntimeError("boom"))
    def test_swallows_errors(self, credit):
        # Must never raise — a failed earning credit can't block completing delivery.
        _credit_driver_earnings(self._job())
