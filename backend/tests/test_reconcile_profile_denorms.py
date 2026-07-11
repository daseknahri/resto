"""RISK DATA-5: reconcile_profile_denorms recomputes the denormalized Profile mirrors.

`Profile.rating_avg`/`rating_count`, `Profile.marketplace_promos` and
`Profile.closure_dates` are denormalized copies of per-tenant-schema data kept in
sync by signals at write time. This command is the periodic self-heal sweep: for
every ACTIVE tenant it reuses (never duplicates) the three existing recompute
functions — `menu.ratings.recompute_tenant_rating`,
`menu.promos_denorm.recompute_tenant_promos`,
`menu.closure_denorm.recompute_tenant_closures`.

Mock-based (SimpleTestCase, no DB): the Tenant queryset and the three recompute
functions are patched at their import origin (they are imported lazily inside
`handle()`, exactly like `reconcile_order_refs`), so the loop/try-except logic
runs without a database.
"""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase


class ReconcileProfileDenormsTests(SimpleTestCase):
    def _tenants(self, n=2):
        return [
            SimpleNamespace(id=i, schema_name=f"t{i}", slug=f"t{i}")
            for i in range(1, n + 1)
        ]

    def _run(self, tenants, rating_side_effect=None, promos_side_effect=None,
              closures_side_effect=None):
        Tenant = MagicMock()
        Tenant.objects.filter.return_value = tenants
        Tenant.LifecycleStatus.ACTIVE = "active"

        rating_mock = MagicMock(side_effect=rating_side_effect)
        promos_mock = MagicMock(side_effect=promos_side_effect)
        closures_mock = MagicMock(side_effect=closures_side_effect)

        out = StringIO()
        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.ratings.recompute_tenant_rating", rating_mock), \
             patch("menu.promos_denorm.recompute_tenant_promos", promos_mock), \
             patch("menu.closure_denorm.recompute_tenant_closures", closures_mock):
            call_command("reconcile_profile_denorms", stdout=out)

        return {
            "Tenant": Tenant,
            "rating_mock": rating_mock,
            "promos_mock": promos_mock,
            "closures_mock": closures_mock,
            "out": out.getvalue(),
        }

    def test_only_active_tenants_are_queried(self):
        tenants = self._tenants(2)
        ctx = self._run(tenants)
        ctx["Tenant"].objects.filter.assert_called_once_with(lifecycle_status="active")

    def test_calls_all_three_recompute_functions_once_per_tenant(self):
        tenants = self._tenants(3)
        ctx = self._run(tenants)

        self.assertEqual(ctx["rating_mock"].call_count, 3)
        self.assertEqual(ctx["promos_mock"].call_count, 3)
        self.assertEqual(ctx["closures_mock"].call_count, 3)
        # Each recompute is invoked with the tenant instance itself.
        for tenant in tenants:
            ctx["rating_mock"].assert_any_call(tenant)
            ctx["promos_mock"].assert_any_call(tenant)
            ctx["closures_mock"].assert_any_call(tenant)

        self.assertIn("3 tenant(s) reconciled", ctx["out"])
        self.assertNotIn("failed", ctx["out"])

    def test_exception_in_one_tenant_does_not_abort_the_others(self):
        tenants = self._tenants(2)  # t1, t2

        def _boom(tenant):
            if tenant.slug == "t1":
                raise RuntimeError("boom")

        ctx = self._run(tenants, rating_side_effect=_boom)

        # t1's rating recompute raised — its promos/closures calls are skipped
        # (the whole tenant is wrapped in one try/except) and it is counted failed.
        ctx["rating_mock"].assert_any_call(tenants[0])
        ctx["promos_mock"].assert_any_call(tenants[1])
        ctx["closures_mock"].assert_any_call(tenants[1])
        self.assertNotIn(((tenants[0],), {}), ctx["promos_mock"].call_args_list)
        self.assertNotIn(((tenants[0],), {}), ctx["closures_mock"].call_args_list)

        # t2 still fully processed despite t1's failure.
        self.assertEqual(ctx["rating_mock"].call_count, 2)
        self.assertEqual(ctx["promos_mock"].call_count, 1)
        self.assertEqual(ctx["closures_mock"].call_count, 1)

        self.assertIn("1 tenant(s) reconciled", ctx["out"])
        self.assertIn("1 failed", ctx["out"])

    def test_no_tenants_reports_zero_reconciled(self):
        ctx = self._run([])
        self.assertEqual(ctx["rating_mock"].call_count, 0)
        self.assertIn("0 tenant(s) reconciled", ctx["out"])
        self.assertNotIn("failed", ctx["out"])
