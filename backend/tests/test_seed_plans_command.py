"""
Unit tests for tenancy.management.commands.seed_plans.

The command:
  1. Upserts starter / growth / pro plans via Plan.objects.update_or_create
  2. If --with-demo: also creates/gets a superadmin user, a tenant, and a domain

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.core.management import call_command


# ══════════════════════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════════════════════

def _plan(code):
    return MagicMock(code=code)


def _plan_mgr():
    """Mock Plan.objects whose update_or_create returns (plan, True)."""
    mgr = MagicMock()
    mgr.update_or_create.side_effect = lambda code, defaults: (_plan(code), True)
    return mgr


def _user_mgr(created=True):
    user = MagicMock()
    user.pk = 1
    mgr = MagicMock()
    mgr.get_or_create.return_value = (user, created)
    return mgr, user


# ══════════════════════════════════════════════════════════════════════════════
# Without --with-demo: only plans are seeded
# ══════════════════════════════════════════════════════════════════════════════

class SeedPlansWithoutDemoTests(SimpleTestCase):
    """Running without --with-demo upserts the three plans."""

    def _run(self):
        stdout = StringIO()
        with patch("tenancy.management.commands.seed_plans.Plan") as mock_plan:
            mock_plan.objects = _plan_mgr()
            call_command("seed_plans", stdout=stdout)
        return mock_plan, stdout.getvalue()

    def test_upserts_starter_plan(self):
        mock_plan, _ = self._run()
        codes = [c.kwargs["code"] for c in mock_plan.objects.update_or_create.call_args_list]
        self.assertIn("starter", codes)

    def test_upserts_growth_plan(self):
        mock_plan, _ = self._run()
        codes = [c.kwargs["code"] for c in mock_plan.objects.update_or_create.call_args_list]
        self.assertIn("growth", codes)

    def test_upserts_pro_plan(self):
        mock_plan, _ = self._run()
        codes = [c.kwargs["code"] for c in mock_plan.objects.update_or_create.call_args_list]
        self.assertIn("pro", codes)

    def test_exactly_three_plans_upserted(self):
        mock_plan, _ = self._run()
        self.assertEqual(mock_plan.objects.update_or_create.call_count, 3)

    def test_output_mentions_seeding_complete(self):
        _, out = self._run()
        self.assertIn("complete", out.lower())

    def test_output_mentions_plans_ensured(self):
        _, out = self._run()
        self.assertIn("Plans ensured", out)

    def test_no_user_or_tenant_created_without_demo_flag(self):
        with patch("tenancy.management.commands.seed_plans.Plan") as mock_plan, \
             patch("tenancy.management.commands.seed_plans.Tenant") as mock_tenant, \
             patch("tenancy.management.commands.seed_plans.get_user_model") as mock_um:
            mock_plan.objects = _plan_mgr()
            call_command("seed_plans")
        # get_user_model should not have been called without --with-demo
        mock_um.assert_not_called()
        mock_tenant.objects.get_or_create.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# With --with-demo: user + tenant + domain also created
# ══════════════════════════════════════════════════════════════════════════════

class SeedPlansWithDemoTests(SimpleTestCase):
    """Running with --with-demo creates superadmin, tenant, and domain."""

    def _run(self, email="admin@example.com", password="admin123",
             domain="demo.localhost", user_created=True):
        stdout = StringIO()
        user_mgr, user_obj = _user_mgr(created=user_created)

        with patch("tenancy.management.commands.seed_plans.Plan") as mock_plan, \
             patch("tenancy.management.commands.seed_plans.Tenant") as mock_tenant, \
             patch("tenancy.management.commands.seed_plans.Domain") as mock_domain, \
             patch("tenancy.management.commands.seed_plans.get_user_model") as mock_um:
            mock_plan.objects = _plan_mgr()
            mock_um.return_value.objects = user_mgr
            mock_um.return_value.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"
            mock_tenant.objects.get_or_create.return_value = (MagicMock(), True)
            call_command(
                "seed_plans",
                "--with-demo",
                f"--email={email}",
                f"--password={password}",
                f"--domain={domain}",
                stdout=stdout,
            )

        return {
            "mock_plan": mock_plan,
            "mock_um": mock_um,
            "mock_tenant": mock_tenant,
            "mock_domain": mock_domain,
            "user_mgr": user_mgr,
            "user_obj": user_obj,
            "out": stdout.getvalue(),
        }

    def test_plans_still_upserted(self):
        ctx = self._run()
        self.assertEqual(ctx["mock_plan"].objects.update_or_create.call_count, 3)

    def test_get_user_model_called(self):
        ctx = self._run()
        ctx["mock_um"].assert_called_once()

    def test_user_get_or_create_called(self):
        ctx = self._run()
        ctx["user_mgr"].get_or_create.assert_called_once()

    def test_user_email_used_as_username(self):
        ctx = self._run(email="boss@demo.com")
        kw = ctx["user_mgr"].get_or_create.call_args[1]
        self.assertEqual(kw.get("username"), "boss@demo.com")

    def test_created_user_gets_password_set(self):
        ctx = self._run(user_created=True)
        ctx["user_obj"].set_password.assert_called_once()

    def test_existing_user_skips_password_set(self):
        ctx = self._run(user_created=False)
        ctx["user_obj"].set_password.assert_not_called()

    def test_tenant_get_or_create_called(self):
        ctx = self._run()
        ctx["mock_tenant"].objects.get_or_create.assert_called_once()

    def test_domain_get_or_create_called(self):
        ctx = self._run()
        ctx["mock_domain"].objects.get_or_create.assert_called_once()

    def test_domain_value_passed(self):
        ctx = self._run(domain="menu.myapp.com")
        kw = ctx["mock_domain"].objects.get_or_create.call_args[1]
        self.assertEqual(kw.get("domain"), "menu.myapp.com")

    def test_output_mentions_demo_tenant(self):
        ctx = self._run()
        self.assertIn("Demo tenant", ctx["out"])

    def test_output_mentions_superadmin_created(self):
        ctx = self._run(user_created=True)
        self.assertIn("Superadmin created", ctx["out"])

    def test_output_mentions_superadmin_already_exists(self):
        ctx = self._run(user_created=False)
        self.assertIn("already exists", ctx["out"])
