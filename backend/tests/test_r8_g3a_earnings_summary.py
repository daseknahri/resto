"""Run 8 G3a — A2-09: driver_earnings_summary exposes ledger_owed + cashout_total.

ledger_owed is the delivery-ledger cap (earned − paid) that record_driver_payout
enforces; cashout_total is what the driver already took via self-service
cash-outs (which write no DriverPayout row, so `paid` never sees them). The
admin payout form prefills/caps on min(ledger_owed, wallet_balance).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.driver_service import driver_earnings_summary


def _agg(value, extra=None):
    m = MagicMock()
    d = {"s": value}
    if extra:
        d.update(extra)
    m.aggregate.return_value = d
    return m


class DriverEarningsSummaryLedgerTests(SimpleTestCase):
    @patch("accounts.models.Customer.objects")
    @patch("accounts.models.RideRequest.objects")
    @patch("accounts.models.WalletTransaction.objects")
    @patch("accounts.models.DriverPayout.objects")
    @patch("accounts.models.DeliveryJob.objects")
    def test_summary_exposes_ledger_owed_and_cashout_total(
        self, mock_job_objs, mock_payout_objs, mock_tx_objs, mock_ride_objs, mock_cust_objs
    ):
        # DeliveryJob.filter is called 3×: summary earned, summary today, _owed earned.
        mock_job_objs.filter.side_effect = [
            _agg(Decimal("100")),
            _agg(Decimal("10"), {"n": 1}),
            _agg(Decimal("100")),
        ]
        # DriverPayout.filter is called 2×: summary paid, _owed paid.
        mock_payout_objs.filter.side_effect = [_agg(Decimal("40")), _agg(Decimal("40"))]
        # WalletTransaction.filter is called 2×: ride earnings, cash-outs.
        mock_tx_objs.filter.side_effect = [_agg(Decimal("5")), _agg(Decimal("15"))]
        mock_ride_objs.filter.return_value.count.return_value = 2
        mock_cust_objs.filter.return_value.values_list.return_value.first.return_value = Decimal("45")

        s = driver_earnings_summary(7)

        self.assertEqual(s["earned"], Decimal("100"))
        self.assertEqual(s["paid"], Decimal("40"))
        self.assertEqual(s["wallet_balance"], Decimal("45"))
        # ledger_owed = earned − paid (delivery ledger), NOT the wallet balance.
        self.assertEqual(s["ledger_owed"], Decimal("60"))
        # cashout_total = Σ CASHOUT rows — explains earned − paid (60) > wallet (45).
        self.assertEqual(s["cashout_total"], Decimal("15"))
