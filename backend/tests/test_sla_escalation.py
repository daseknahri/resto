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

    def _wire(self, mock_t, mock_ctx, mock_order_cls, tenant, orders):
        mock_t.objects.filter.return_value.exclude.return_value = [tenant]
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_order_cls.Status.PENDING = "pending"
        (mock_order_cls.objects.filter.return_value
         .only.return_value.order_by.return_value) = orders

    def test_dry_run_does_not_save_or_push(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            output = self._run_command(dry_run=True)

        order.save.assert_not_called()
        mock_push.assert_not_called()
        self.assertIn("DRY RUN", output)

    def test_stamps_sla_notified_at_and_pushes(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation") as mock_push:
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            self._run_command()

        order.save.assert_called_once()
        update_fields = order.save.call_args.kwargs.get("update_fields", [])
        self.assertIn("sla_notified_at", update_fields)
        self.assertIsNotNone(order.sla_notified_at)
        mock_push.assert_called_once()

    def test_push_exception_still_stamps(self):
        tenant = self._make_tenant()
        order = self._make_order()

        with patch(f"{CMD}.Tenant") as mock_t, \
             patch(f"{CMD}.schema_context") as mock_ctx, \
             patch("menu.models.Order") as mock_order_cls, \
             patch("menu.push.push_sla_escalation", side_effect=RuntimeError("boom")):
            self._wire(mock_t, mock_ctx, mock_order_cls, tenant, [order])
            self._run_command()  # must not raise

        order.save.assert_called_once()

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
            mock_t.objects.filter.return_value.exclude.return_value = []
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

class TestAllowlistContainsSlaEscalation(SimpleTestCase):
    def test_command_in_allowlist(self):
        from accounts.tasks import _MANAGEMENT_COMMAND_ALLOWLIST
        self.assertIn("escalate_stale_pending_orders", _MANAGEMENT_COMMAND_ALLOWLIST)
