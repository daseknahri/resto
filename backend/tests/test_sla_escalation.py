"""
Unit tests for the server-side SLA-escalation feature.

Covers:
  - menu.push.push_sla_escalation: builds the right title/body/url and enqueues
  - escalate_stale_pending_orders management command: dry-run, stamps DB,
    skips already-stamped, default vs configured SLA, push-exception resilience
  - allowlist registration
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone


# ── push helper ──────────────────────────────────────────────────────────────

class TestPushSlaEscalation(SimpleTestCase):
    """Exercises menu.push.push_sla_escalation in isolation (enqueue is mocked)."""

    def test_enqueues_with_title_body_url(self):
        from menu.push import push_sla_escalation

        with patch("accounts.tasks.enqueue") as mock_enqueue, \
             patch("accounts.tasks.web_push_tenant") as mock_task:
            push_sla_escalation(schema_name="acme", order_number="ORD-42", waited_minutes=17)

        mock_enqueue.assert_called_once()
        args = mock_enqueue.call_args.args
        # enqueue(web_push_tenant, schema_name, title, body, url)
        self.assertIs(args[0], mock_task)
        self.assertEqual(args[1], "acme")
        title, body, url = args[2], args[3], args[4]
        self.assertIn("ORD-42", title)
        self.assertIn("ORD-42", body)
        self.assertIn("17", body)
        self.assertIn("confirm", body.lower())
        # deep-links to OwnerOrders filtered by order number
        self.assertEqual(url, "/owner/orders?q=ORD-42")


# ── management command ───────────────────────────────────────────────────────

CMD = "menu.management.commands.escalate_stale_pending_orders"


class TestEscalateStalePendingOrdersCommand(SimpleTestCase):
    """Exercises the escalate_stale_pending_orders command logic (no real DB)."""

    def _run_command(self, **kwargs):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("escalate_stale_pending_orders", stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def _make_tenant(self, slug="test", name="Test Restaurant", schema_name="test",
                     pending_sla_minutes=None):
        t = MagicMock()
        t.slug = slug
        t.name = name
        t.schema_name = schema_name
        t.profile = MagicMock()
        t.profile.pending_sla_minutes = pending_sla_minutes
        return t

    def _make_order(self, order_number="ORD-1", minutes_ago=30):
        o = MagicMock()
        o.order_number = order_number
        o.created_at = timezone.now() - timedelta(minutes=minutes_ago)
        return o

    def _wire(self, mock_t, mock_ctx, mock_order_cls, tenant, orders, claim=1):
        mock_t.objects.filter.return_value.exclude.return_value.select_related.return_value = [tenant]
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_order_cls.Status.PENDING = "pending"
        (mock_order_cls.objects.filter.return_value
         .only.return_value.order_by.return_value) = orders
        # The atomic claim: Order.objects.filter(pk=..., sla_notified_at__isnull=True).update(...)
        # returns the number of rows it won (1 = we own the escalation, 0 = lost the race).
        mock_order_cls.objects.filter.return_value.update.return_value = claim

    def test_dry_run_does_not_claim_or_push(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            output = self._run_command(dry_run=True)

        mock_order_cls.objects.filter.return_value.update.assert_not_called()
        mock_push.assert_not_called()
        self.assertIn("DRY RUN", output)

    def test_claims_sla_notified_at_and_pushes(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            self._run_command()

        # Claimed via a conditional UPDATE (not a blind save): scoped to this pk AND
        # still-unstamped, stamping sla_notified_at + updated_at (update() skips auto_now).
        order.save.assert_not_called()
        self.assertEqual(
            mock_order_cls.objects.filter.call_args.kwargs,
            {"pk": order.pk, "sla_notified_at__isnull": True},
        )
        claim_update = mock_order_cls.objects.filter.return_value.update
        claim_update.assert_called_once()
        self.assertEqual(set(claim_update.call_args.kwargs), {"sla_notified_at", "updated_at"})
        self.assertIsNotNone(claim_update.call_args.kwargs["sla_notified_at"])
        mock_push.assert_called_once()

    def test_lost_claim_skips_push(self):
        """Another overlapping run already claimed the order (update() -> 0): no duplicate push."""
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order], claim=0)
            output = self._run_command()

        mock_order_cls.objects.filter.return_value.update.assert_called_once()
        mock_push.assert_not_called()
        self.assertIn("already escalated", output)
        self.assertIn("0 order(s)", output)

    def test_overlapping_runs_push_once(self):
        """Two runs see the same stale order; only the first claim wins, so one push total."""
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            # First run wins the row; the second (overlapping) run finds it already stamped.
            mock_order_cls.objects.filter.return_value.update.side_effect = [1, 0]
            self._run_command()
            self._run_command()

        self.assertEqual(mock_push.call_count, 1)

    def test_push_exception_still_stamps(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation", side_effect=RuntimeError("boom")):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            self._run_command()  # must not raise

        # The claim (stamp) was taken before the failing push, so it is not retried.
        mock_order_cls.objects.filter.return_value.update.assert_called_once()

    def test_only_pending_unstamped_queried(self):
        """The query filters status=PENDING + sla_notified_at IS NULL + created_at<=cutoff."""
        tenant = self._make_tenant()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation"):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [])
            self._run_command()

        filter_kwargs = mock_order_cls.objects.filter.call_args.kwargs
        self.assertEqual(filter_kwargs.get("status"), "pending")
        self.assertTrue(filter_kwargs.get("sla_notified_at__isnull"))
        self.assertIn("created_at__lte", filter_kwargs)

    def test_default_sla_when_unset(self):
        """Unset pending_sla_minutes => default cutoff (10 min before now)."""
        from menu.management.commands.escalate_stale_pending_orders import (
            DEFAULT_PENDING_SLA_MINUTES,
        )
        tenant = self._make_tenant(pending_sla_minutes=None)

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation"):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [])
            now = timezone.now()
            self._run_command()

        cutoff = mock_order_cls.objects.filter.call_args.kwargs["created_at__lte"]
        delta_min = (now - cutoff).total_seconds() / 60
        self.assertAlmostEqual(delta_min, DEFAULT_PENDING_SLA_MINUTES, delta=1)

    def test_configured_sla_used(self):
        """A configured pending_sla_minutes drives the cutoff window."""
        tenant = self._make_tenant(pending_sla_minutes=25)

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation"):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [])
            now = timezone.now()
            self._run_command()

        cutoff = mock_order_cls.objects.filter.call_args.kwargs["created_at__lte"]
        delta_min = (now - cutoff).total_seconds() / 60
        self.assertAlmostEqual(delta_min, 25, delta=1)

    def test_zero_sla_falls_back_to_default(self):
        """A 0 (falsy) configured value is treated as unset => platform default, never
        an instant escalation on every fresh order."""
        from menu.management.commands.escalate_stale_pending_orders import (
            DEFAULT_PENDING_SLA_MINUTES,
        )
        tenant = self._make_tenant(pending_sla_minutes=0)

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation"):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [])
            now = timezone.now()
            self._run_command()

        cutoff = mock_order_cls.objects.filter.call_args.kwargs["created_at__lte"]
        delta_min = (now - cutoff).total_seconds() / 60
        self.assertAlmostEqual(delta_min, DEFAULT_PENDING_SLA_MINUTES, delta=1)

    def test_no_tenants_exits_cleanly(self):
        with patch(f"{CMD}.Tenant") as mock_t:
            mock_t.objects.filter.return_value.exclude.return_value.select_related.return_value = []
            output = self._run_command()
        self.assertIn("Done", output)
        self.assertIn("0 order(s)", output)

    def test_output_contains_order_number(self):
        tenant = self._make_tenant()
        order = self._make_order(order_number="ORD-XYZ")

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation"):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            output = self._run_command()

        self.assertIn("ORD-XYZ", output)

    def test_waited_minutes_passed_to_push(self):
        tenant = self._make_tenant()
        order = self._make_order(minutes_ago=42)

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            self._run_command()

        waited = mock_push.call_args.kwargs["waited_minutes"]
        self.assertGreaterEqual(waited, 41)
        self.assertLessEqual(waited, 43)


# ── allowlist guard ──────────────────────────────────────────────────────────

class TestSlaEscalationScheduled(SimpleTestCase):
    def test_command_scheduled_as_cron_task(self):
        # RISK ASYNC-2: the command is wired to Beat via its dedicated cron.* task.
        from django.conf import settings
        tasks = {e["task"] for e in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertIn("cron.escalate_stale_pending_orders", tasks)
