"""
Unit tests for WalletTransaction.vertical backfill (P1b).

The auto-derive inside credit_wallet/debit_wallet runs against the DB
(select_for_update) and is covered by the DB-backed wallet tests; here we
unit-test the backfill command's classification logic with mocks (no DB),
mirroring the project's SimpleTestCase pattern.

See KEPOLI_ACCOUNT_ARCHITECTURE.md P1.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts import verticals as V


class TestBackfillWalletVertical(SimpleTestCase):
    def _run(self, **kwargs):
        from accounts.management.commands.backfill_wallet_vertical import Command

        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        cmd.handle(**{"dry_run": False, **kwargs})
        return cmd.stdout.getvalue()

    def _ctx(self, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.WalletTransaction")
    def test_cashout_tagged_driver_and_tenant_rows_mapped(self, mock_wt, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        mock_wt.Type.CASHOUT = "cashout"

        cashout_qs = MagicMock()
        cashout_qs.count.return_value = 2
        earning_qs = MagicMock()
        earning_qs.count.return_value = 0

        base_qs = MagicMock()
        base_qs.exclude.return_value = base_qs  # .exclude(type=CASHOUT) chains on base
        base_qs.values_list.return_value.distinct.return_value = [5]
        tenant5_qs = MagicMock()
        tenant5_qs.count.return_value = 4
        base_qs.filter.return_value = tenant5_qs

        # First filter() call = CASHOUT rows; second filter() = the tenant-attributed base.
        mock_wt.objects.filter.side_effect = [cashout_qs, earning_qs, base_qs]
        mock_profile.objects.filter.return_value.values_list.return_value = [(5, "grocery")]

        out = self._run()

        cashout_qs.update.assert_called_once_with(vertical=V.DRIVER)
        tenant5_qs.update.assert_called_once_with(vertical=V.SHOPS)
        self.assertIn("Backfilled 6", out)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.WalletTransaction")
    def test_delivery_earning_tagged_driver(self, mock_wt, mock_profile, mock_ctx):
        # A delivery EARNING carries tenant_id but belongs to the DRIVER vertical
        # (the driver's income), NOT the originating tenant's consumer vertical.
        self._ctx(mock_ctx)
        mock_wt.Type.CASHOUT = "cashout"
        mock_wt.Type.EARNING = "earning"

        cashout_qs = MagicMock()
        cashout_qs.count.return_value = 0
        earning_qs = MagicMock()
        earning_qs.count.return_value = 3
        base_qs = MagicMock()
        base_qs.exclude.return_value = base_qs
        base_qs.values_list.return_value.distinct.return_value = []  # no other tenant rows

        mock_wt.objects.filter.side_effect = [cashout_qs, earning_qs, base_qs]
        mock_profile.objects.filter.return_value.values_list.return_value = []

        out = self._run()

        earning_qs.update.assert_called_once_with(vertical=V.DRIVER)
        self.assertIn("Backfilled 3", out)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.WalletTransaction")
    def test_unresolved_tenant_left_null(self, mock_wt, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        mock_wt.Type.CASHOUT = "cashout"
        cashout_qs = MagicMock()
        cashout_qs.count.return_value = 0
        earning_qs = MagicMock()
        earning_qs.count.return_value = 0
        base_qs = MagicMock()
        base_qs.exclude.return_value = base_qs
        base_qs.values_list.return_value.distinct.return_value = [9]
        tenant9_qs = MagicMock()
        base_qs.filter.return_value = tenant9_qs
        mock_wt.objects.filter.side_effect = [cashout_qs, earning_qs, base_qs]
        # No business_type for tenant 9 → skipped (left NULL/global).
        mock_profile.objects.filter.return_value.values_list.return_value = []

        self._run()
        tenant9_qs.update.assert_not_called()

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.WalletTransaction")
    def test_dry_run_writes_nothing(self, mock_wt, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        mock_wt.Type.CASHOUT = "cashout"
        cashout_qs = MagicMock()
        cashout_qs.count.return_value = 1
        earning_qs = MagicMock()
        earning_qs.count.return_value = 0
        base_qs = MagicMock()
        base_qs.exclude.return_value = base_qs
        base_qs.values_list.return_value.distinct.return_value = [3]
        tenant3_qs = MagicMock()
        tenant3_qs.count.return_value = 2
        base_qs.filter.return_value = tenant3_qs
        mock_wt.objects.filter.side_effect = [cashout_qs, earning_qs, base_qs]
        mock_profile.objects.filter.return_value.values_list.return_value = [(3, "restaurant")]

        out = self._run(dry_run=True)
        cashout_qs.update.assert_not_called()
        tenant3_qs.update.assert_not_called()
        self.assertIn("(dry)", out)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.WalletTransaction")
    def test_delivery_earning_tagged_driver(self, mock_wt, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        mock_wt.Type.CASHOUT = "cashout"
        mock_wt.Type.EARNING = "earning"
        cashout_qs = MagicMock()
        cashout_qs.count.return_value = 0
        earning_qs = MagicMock()
        earning_qs.count.return_value = 3  # delivery earnings to retag
        base_qs = MagicMock()
        base_qs.exclude.return_value = base_qs
        base_qs.values_list.return_value.distinct.return_value = []
        mock_wt.objects.filter.side_effect = [cashout_qs, earning_qs, base_qs]
        mock_profile.objects.filter.return_value.values_list.return_value = []

        self._run()
        earning_qs.update.assert_called_once_with(vertical=V.DRIVER)
