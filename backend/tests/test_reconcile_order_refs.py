"""RISK DATA-1: reconcile_order_refs detects orphaned public order-refs.

Public DeliveryJob / CustomerOrderRef / CustomerRating reference a tenant order by a loose
(tenant_id, order_number) with no FK, so a removed Order orphans them. The command reports
orphans, escalates money-carrying DeliveryJob orphans to the `payments` log (NEVER deleting
them), and under --fix deletes only the safe CustomerOrderRef mirror orphans.

Mock-based (SimpleTestCase, no DB): the tenant loop, per-model managers, schema_context,
and the tenant-schema Order read are patched, so the decision logic runs without a database.
"""
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase


def _noop_cm():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _model_with(pass1_ons, detail_rows=None, deleted=None):
    """A model mock whose `.objects.filter(tenant_id=..)` → `.values_list(flat)` yields
    `pass1_ons`, and whose `.objects.filter(tenant_id=.., order_number__in=S)` yields a qs
    over the `detail_rows` in S: `.values_list()` returns them, `.count()` their number, and
    `.delete()` appends them to `deleted` (so the test can assert what was removed)."""
    m = MagicMock()

    def _filter(**kw):
        qs = MagicMock()
        if "order_number__in" in kw:
            in_set = set(kw["order_number__in"])
            rows = [r for r in (detail_rows or []) if (r[1] if isinstance(r, tuple) else r) in in_set]
            qs.values_list.return_value = rows
            qs.count.return_value = len(rows)

            def _delete():
                if deleted is not None:
                    deleted.extend((r[1] if isinstance(r, tuple) else r) for r in rows)
                return (len(rows), {})

            qs.delete.side_effect = _delete
        else:
            qs.values_list.return_value = list(pass1_ons)
        return qs

    m.objects.filter.side_effect = _filter
    return m


class ReconcileOrderRefsTests(SimpleTestCase):
    def _run(self, *args, existing=("ORD-OK",)):
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1")
        dj_deleted, mirror_deleted = [], []
        dj_detail = [
            (10, "ORD-GONE", 5, Decimal("50.00"), "delivered"),   # orphan WITH payout (money)
            (11, "ORD-OK", 6, Decimal("30.00"), "delivered"),     # not orphaned
        ]
        DeliveryJob = _model_with(["ORD-GONE", "ORD-OK"], detail_rows=dj_detail, deleted=dj_deleted)
        CustomerOrderRef = _model_with(["ORD-GONE", "ORD-OK"], detail_rows=["ORD-GONE", "ORD-OK"], deleted=mirror_deleted)
        CustomerRating = _model_with(["ORD-GONE"], detail_rows=["ORD-GONE"])
        Order = MagicMock()
        Order.objects.filter.return_value.values_list.return_value = list(existing)
        Tenant = MagicMock()
        Tenant.objects.all.return_value = [tenant]

        out = StringIO()
        with patch("tenancy.models.Tenant", Tenant), \
             patch("accounts.models.DeliveryJob", DeliveryJob), \
             patch("accounts.models.CustomerOrderRef", CustomerOrderRef), \
             patch("accounts.models.CustomerRating", CustomerRating), \
             patch("menu.models.Order", Order), \
             patch("accounts.management.commands.reconcile_order_refs.schema_context", return_value=_noop_cm()), \
             patch("accounts.management.commands.reconcile_order_refs.payments_logger") as plog:
            call_command("reconcile_order_refs", *args, stdout=out)
        return {"dj_deleted": dj_deleted, "mirror_deleted": mirror_deleted, "plog": plog, "out": out.getvalue()}

    def test_money_orphan_escalated_and_never_deleted(self):
        ctx = self._run()  # detect-only (no --fix)
        # The orphaned delivery job with a payout is escalated to the payments channel …
        self.assertTrue(ctx["plog"].error.called)
        self.assertIn("ORD-GONE", ctx["plog"].error.call_args[0])
        # … and is NEVER deleted (money record).
        self.assertEqual(ctx["dj_deleted"], [])
        # detect-only mode touches nothing.
        self.assertEqual(ctx["mirror_deleted"], [])

    def test_fix_deletes_only_the_mirror_orphan(self):
        ctx = self._run("--fix")
        # Only the orphaned CustomerOrderRef mirror row is deleted (ORD-OK kept).
        self.assertEqual(ctx["mirror_deleted"], ["ORD-GONE"])
        # DeliveryJob money orphan STILL never deleted, even with --fix, and still escalated.
        self.assertEqual(ctx["dj_deleted"], [])
        self.assertTrue(ctx["plog"].error.called)

    def test_non_money_orphan_not_escalated(self):
        # An orphan whose delivery job has zero payout must NOT hit the payments channel.
        tenant = SimpleNamespace(id=1, schema_name="t1", slug="t1")
        DeliveryJob = _model_with(["ORD-GONE"], detail_rows=[(10, "ORD-GONE", 5, Decimal("0.00"), "cancelled")])
        CustomerOrderRef = _model_with([], detail_rows=[])
        CustomerRating = _model_with([], detail_rows=[])
        Order = MagicMock()
        Order.objects.filter.return_value.values_list.return_value = []  # ORD-GONE doesn't exist
        Tenant = MagicMock()
        Tenant.objects.all.return_value = [tenant]
        with patch("tenancy.models.Tenant", Tenant), \
             patch("accounts.models.DeliveryJob", DeliveryJob), \
             patch("accounts.models.CustomerOrderRef", CustomerOrderRef), \
             patch("accounts.models.CustomerRating", CustomerRating), \
             patch("menu.models.Order", Order), \
             patch("accounts.management.commands.reconcile_order_refs.schema_context", return_value=_noop_cm()), \
             patch("accounts.management.commands.reconcile_order_refs.payments_logger") as plog:
            call_command("reconcile_order_refs", stdout=StringIO())
        plog.error.assert_not_called()

    def test_no_orphans_when_all_orders_exist(self):
        ctx = self._run(existing=("ORD-GONE", "ORD-OK"))  # every referenced order exists
        self.assertFalse(ctx["plog"].error.called)
        self.assertEqual(ctx["dj_deleted"], [])
        self.assertEqual(ctx["mirror_deleted"], [])
