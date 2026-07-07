"""Unit tests for the reconcile_driver_earnings management command.

Mock-based (SimpleTestCase, no DB): patches DeliveryJob / WalletTransaction / the credit
function and drives the real LocMemCache for the consecutive-failure streak logic.
"""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch, MagicMock

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase


def _job(job_id, driver_id=10, payout="15.00", order="A1"):
    j = MagicMock()
    j.id = job_id
    j.driver_id = driver_id
    j.driver_payout = Decimal(payout)
    j.order_number = order
    return j


class ReconcileDriverEarningsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _run(self, *args, candidates=None, have=None, now_have=None):
        """Run the command with the models + credit patched.

        candidates: jobs the DELIVERED scan returns.
        have: idempotency_keys that already exist BEFORE crediting.
        now_have: keys that exist AFTER crediting (omit if the second query won't run).
        Returns (stdout_text, credit_mock).
        """
        candidates = candidates or []
        values_list_returns = [list(have or [])]
        if now_have is not None:
            values_list_returns.append(list(now_have))

        with patch("accounts.models.DeliveryJob") as DJ, \
                patch("accounts.models.WalletTransaction") as WT, \
                patch("accounts.views._credit_driver_earnings") as credit:
            DJ.Status.DELIVERED = "delivered"
            DJ.objects.filter.return_value.order_by.return_value.__getitem__.return_value = candidates
            WT.objects.filter.return_value.values_list.side_effect = values_list_returns
            out = StringIO()
            call_command("reconcile_driver_earnings", *args, stdout=out)
        return out.getvalue(), credit

    def test_credits_only_missing_jobs(self):
        jobs = [_job(1), _job(2), _job(3)]
        # job 1 already has its earning; 2 and 3 are missing and both succeed after credit.
        out, credit = self._run(
            candidates=jobs, have=["earning:1"], now_have=["earning:2", "earning:3"],
        )
        credited_ids = {c.args[0].id for c in credit.call_args_list}
        self.assertEqual(credited_ids, {2, 3})
        self.assertIn("credited=2", out)
        self.assertIn("still_failing=0", out)

    def test_all_credited_is_noop(self):
        jobs = [_job(1), _job(2)]
        out, credit = self._run(candidates=jobs, have=["earning:1", "earning:2"])
        credit.assert_not_called()
        self.assertIn("all credited", out)

    def test_dry_run_does_not_credit(self):
        jobs = [_job(1), _job(2)]
        out, credit = self._run("--dry-run", candidates=jobs, have=[])
        credit.assert_not_called()
        self.assertIn("dry-run", out)
        self.assertIn("missing=2", out)

    def test_no_candidates(self):
        out, credit = self._run(candidates=[])
        credit.assert_not_called()
        self.assertIn("no delivered jobs", out)

    def test_alerts_after_threshold_on_persistent_failure(self):
        job = _job(2)
        # Pre-seed the streak so this run is the 3rd consecutive failure (alert-after=3).
        cache.set("earning_reconcile_fail:2", 2, 60)
        with patch("accounts.management.commands.reconcile_driver_earnings.payments_logger") as plog:
            out, credit = self._run(
                "--alert-after", "3", candidates=[job], have=[], now_have=[],
            )
            self.assertTrue(plog.error.called)
        credit.assert_called_once()
        self.assertIn("still_failing=1", out)
        self.assertEqual(cache.get("earning_reconcile_fail:2"), 3)

    def test_no_alert_before_threshold(self):
        job = _job(2)
        with patch("accounts.management.commands.reconcile_driver_earnings.payments_logger") as plog:
            self._run("--alert-after", "3", candidates=[job], have=[], now_have=[])
            plog.error.assert_not_called()
        # First failure recorded, but below the alert threshold.
        self.assertEqual(cache.get("earning_reconcile_fail:2"), 1)
