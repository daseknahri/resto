"""
Unit tests for CustomerOrderRef.vertical tagging + backfill (P1a).

The signal that sets `vertical` runs inside a tenant DB transaction, so it's
covered by the broader DB-backed order tests; here we unit-test the backfill
command's derivation/update logic with mocks (no DB), mirroring the project's
SimpleTestCase pattern, plus the taxonomy contract the signal relies on.

See KEPOLI_ACCOUNT_ARCHITECTURE.md P1.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts import verticals as V


class TestBackfillOrderRefVertical(SimpleTestCase):
    def _run(self, **kwargs):
        from accounts.management.commands.backfill_order_ref_vertical import Command

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
    @patch("accounts.models.CustomerOrderRef")
    def test_no_rows_runs_clean(self, mock_ref, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        mock_ref.objects.filter.return_value.values_list.return_value.distinct.return_value = []
        out = self._run()
        self.assertIn("No order refs need backfilling", out)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.CustomerOrderRef")
    def test_maps_business_type_to_vertical_and_updates(self, mock_ref, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        # Two tenants need backfilling: 1 (pharmacy) and 2 (restaurant).
        mock_ref.objects.filter.return_value.values_list.return_value.distinct.return_value = [1, 2]
        mock_profile.objects.filter.return_value.values_list.return_value = [
            (1, "pharmacy"),
            (2, "restaurant"),
        ]
        # Per-tenant filtered querysets (one per tenant id), each reports a count.
        qs1, qs2 = MagicMock(), MagicMock()
        qs1.count.return_value = 3
        qs2.count.return_value = 5
        # filter() is called many times; route the per-tenant update filters.
        def _filter(*args, **kwargs):
            if kwargs.get("tenant_id") == 1:
                return qs1
            if kwargs.get("tenant_id") == 2:
                return qs2
            # the distinct() discovery call
            m = MagicMock()
            m.values_list.return_value.distinct.return_value = [1, 2]
            return m
        mock_ref.objects.filter.side_effect = _filter

        out = self._run()

        qs1.update.assert_called_once_with(vertical=V.PHARMACY)
        qs2.update.assert_called_once_with(vertical=V.FOOD)
        self.assertIn("Backfilled 8 order ref(s)", out)

    @patch("django_tenants.utils.schema_context")
    @patch("tenancy.models.Profile")
    @patch("accounts.models.CustomerOrderRef")
    def test_dry_run_does_not_write(self, mock_ref, mock_profile, mock_ctx):
        self._ctx(mock_ctx)
        qs = MagicMock()
        qs.count.return_value = 2

        def _filter(*args, **kwargs):
            if kwargs.get("tenant_id") == 9:
                return qs
            m = MagicMock()
            m.values_list.return_value.distinct.return_value = [9]
            return m
        mock_ref.objects.filter.side_effect = _filter
        mock_profile.objects.filter.return_value.values_list.return_value = [(9, "grocery")]

        out = self._run(dry_run=True)
        qs.update.assert_not_called()
        self.assertIn("(dry)", out)


class TestBackfillNotScheduled(SimpleTestCase):
    def test_backfill_is_not_a_cron_task(self):
        # backfill is a one-shot ops command (not Beat-scheduled), so it has no
        # dedicated cron.* task — the broker cannot trigger it (RISK ASYNC-2).
        from django.conf import settings
        import accounts.tasks as tasks

        scheduled = {e["task"] for e in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertNotIn("cron.backfill_order_ref_vertical", scheduled)
        self.assertFalse(hasattr(tasks, "backfill_order_ref_vertical"))
