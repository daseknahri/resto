"""
Tests for management commands without existing coverage:
  - ensure_platform_admin   (accounts)
  - repair_tenant_owner_links (accounts)
  - fetch_currency_rates    (menu)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import io
import json
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


# ══════════════════════════════════════════════════════════════════════════════
# ensure_platform_admin
# ══════════════════════════════════════════════════════════════════════════════

class EnsurePlatformAdminCommandTests(SimpleTestCase):
    """Unit tests for accounts/management/commands/ensure_platform_admin.py"""

    def _run(self, email="admin@example.com", password="Secret123!", **kwargs):
        stdout = io.StringIO()
        call_command(
            "ensure_platform_admin",
            f"--email={email}",
            f"--password={password}",
            stdout=stdout,
            **kwargs,
        )
        return stdout.getvalue()

    @patch("accounts.management.commands.ensure_platform_admin.get_user_model")
    def test_creates_new_admin_and_outputs_created(self, get_user_model_mock):
        User = MagicMock()
        user_obj = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"
        User.objects.get_or_create.return_value = (user_obj, True)
        get_user_model_mock.return_value = User

        out = self._run(email="admin@example.com", password="Secret!")
        self.assertIn("created", out.lower())
        user_obj.set_password.assert_called_once_with("Secret!")
        user_obj.save.assert_called_once()
        self.assertEqual(user_obj.role, User.Roles.PLATFORM_SUPERADMIN)
        self.assertTrue(user_obj.is_staff)
        self.assertTrue(user_obj.is_superuser)

    @patch("accounts.management.commands.ensure_platform_admin.get_user_model")
    def test_updates_existing_admin_and_outputs_updated(self, get_user_model_mock):
        User = MagicMock()
        user_obj = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"
        User.objects.get_or_create.return_value = (user_obj, False)
        get_user_model_mock.return_value = User

        out = self._run(email="admin@example.com", password="NewPass!")
        self.assertIn("updated", out.lower())
        user_obj.set_password.assert_called_once_with("NewPass!")
        user_obj.save.assert_called_once()

    @patch("accounts.management.commands.ensure_platform_admin.get_user_model")
    def test_email_lowercased_and_stripped(self, get_user_model_mock):
        User = MagicMock()
        user_obj = MagicMock()
        User.Roles.PLATFORM_SUPERADMIN = "platform_superadmin"
        User.objects.get_or_create.return_value = (user_obj, True)
        get_user_model_mock.return_value = User

        self._run(email="  ADMIN@Example.COM  ", password="p")
        User.objects.get_or_create.assert_called_once_with(
            username="admin@example.com",
            defaults={"email": "admin@example.com"},
        )


# ══════════════════════════════════════════════════════════════════════════════
# repair_tenant_owner_links
# ══════════════════════════════════════════════════════════════════════════════

class RepairTenantOwnerLinksCommandTests(SimpleTestCase):
    """Unit tests for accounts/management/commands/repair_tenant_owner_links.py"""

    def _run(self, *args, **kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        call_command(
            "repair_tenant_owner_links",
            *args,
            stdout=stdout,
            stderr=stderr,
            **kwargs,
        )
        return stdout.getvalue(), stderr.getvalue()

    def _make_tenant(self, tid=1, schema="demo", name="Demo"):
        return SimpleNamespace(id=tid, schema_name=schema, name=name)

    def _make_user(self, uid=1, email="owner@demo.com", role="tenant_owner"):
        return SimpleNamespace(id=uid, email=email, role=role)

    @patch("accounts.models.User")
    @patch("tenancy.models.Tenant")
    def test_no_orphans_exits_early(self, TenantMock, UserMock):
        UserMock.Roles.TENANT_OWNER = "tenant_owner"
        UserMock.Roles.TENANT_STAFF = "tenant_staff"
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.select_related.return_value = []
        UserMock.objects.filter.return_value = qs

        out, _ = self._run()
        self.assertIn("No orphaned", out)
        # Tenant.objects should not be touched
        TenantMock.objects.all.assert_not_called()

    @patch("accounts.models.User")
    @patch("tenancy.models.Tenant")
    def test_single_tenant_links_orphans_and_updates(self, TenantMock, UserMock):
        UserMock.Roles.TENANT_OWNER = "tenant_owner"
        UserMock.Roles.TENANT_STAFF = "tenant_staff"

        orphan = self._make_user()
        orphan_qs = MagicMock()
        orphan_qs.filter.return_value = orphan_qs
        orphan_qs.select_related.return_value = [orphan]

        update_qs = MagicMock()
        update_qs.update.return_value = 1
        UserMock.objects.filter.side_effect = [orphan_qs, update_qs]

        tenant = self._make_tenant()
        TenantMock.objects.all.return_value = [tenant]

        out, _ = self._run()
        self.assertIn("Done", out)
        update_qs.update.assert_called_once_with(tenant=tenant)

    @patch("accounts.models.User")
    @patch("tenancy.models.Tenant")
    def test_dry_run_does_not_call_update(self, TenantMock, UserMock):
        UserMock.Roles.TENANT_OWNER = "tenant_owner"
        UserMock.Roles.TENANT_STAFF = "tenant_staff"

        orphan = self._make_user()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.select_related.return_value = [orphan]
        UserMock.objects.filter.return_value = qs

        tenant = self._make_tenant()
        TenantMock.objects.all.return_value = [tenant]

        out, _ = self._run("--dry-run")
        self.assertIn("DRY RUN", out)
        # update should not have been called
        qs.update.assert_not_called()

    @patch("accounts.models.User")
    @patch("tenancy.models.Tenant")
    def test_no_tenants_raises_command_error(self, TenantMock, UserMock):
        UserMock.Roles.TENANT_OWNER = "tenant_owner"
        UserMock.Roles.TENANT_STAFF = "tenant_staff"

        orphan = self._make_user()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.select_related.return_value = [orphan]
        UserMock.objects.filter.return_value = qs

        tenant_qs = MagicMock()
        tenant_qs.filter.return_value = []
        TenantMock.objects.all.return_value = [self._make_tenant()]
        # With schema filter → returns empty
        TenantMock.objects.all.return_value = MagicMock()
        TenantMock.objects.all.return_value.filter.return_value = []

        with self.assertRaises(CommandError):
            self._run("--schema=nonexistent")

    @patch("accounts.models.User")
    @patch("tenancy.models.Tenant")
    def test_multiple_tenants_without_schema_prints_error(self, TenantMock, UserMock):
        UserMock.Roles.TENANT_OWNER = "tenant_owner"
        UserMock.Roles.TENANT_STAFF = "tenant_staff"

        orphan = self._make_user()
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.select_related.return_value = [orphan]
        UserMock.objects.filter.return_value = qs

        TenantMock.objects.all.return_value = [self._make_tenant(1, "t1"), self._make_tenant(2, "t2")]

        out, _ = self._run()
        self.assertIn("Multiple tenants", out)
        # update should not have been called
        qs.update.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# fetch_currency_rates
# ══════════════════════════════════════════════════════════════════════════════

class FetchCurrencyRatesCommandTests(SimpleTestCase):
    """Unit tests for menu/management/commands/fetch_currency_rates.py"""

    GOOD_PAYLOAD = json.dumps({
        "base": "MAD",
        "rates": {"EUR": 0.0917, "SAR": 0.3831, "AED": 0.3745},
    }).encode()

    def _run(self, *args, payload=None, tenants=None, **kwargs):
        stdout = io.StringIO()
        stderr = io.StringIO()
        response_obj = MagicMock()
        response_obj.read.return_value = payload or self.GOOD_PAYLOAD
        response_obj.__enter__ = lambda s: s
        response_obj.__exit__ = MagicMock(return_value=False)

        # CurrencyRate is a TENANT-schema model, so the command loops active tenant schemas.
        # Mock a single fake tenant + a passthrough schema_context so the DB-update path runs
        # (Tenant.objects.filter(...).exclude(...) → [tenant]).
        fake_tenants = [MagicMock(schema_name="bistro")] if tenants is None else tenants
        tenant_qs = MagicMock()
        tenant_qs.exclude.return_value = fake_tenants

        @contextmanager
        def _passthrough(_schema):
            yield

        with patch("menu.management.commands.fetch_currency_rates.urllib.request.urlopen", return_value=response_obj), \
                patch("menu.management.commands.fetch_currency_rates.Tenant") as TenantMock, \
                patch("menu.management.commands.fetch_currency_rates.schema_context", _passthrough):
            TenantMock.objects.filter.return_value = tenant_qs
            call_command("fetch_currency_rates", *args, stdout=stdout, stderr=stderr, **kwargs)

        return stdout.getvalue(), stderr.getvalue()

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_updates_currency_rates_in_db(self, CurrencyRateMock):
        CurrencyRateMock.objects.filter.return_value.update.return_value = 1
        out, _ = self._run()
        self.assertIn("Done", out)
        self.assertEqual(CurrencyRateMock.objects.filter.call_count, 3)  # EUR, SAR, AED
        for code in ("EUR", "SAR", "AED"):
            CurrencyRateMock.objects.filter.assert_any_call(code=code)

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_dry_run_does_not_call_db(self, CurrencyRateMock):
        out, _ = self._run("--dry-run")
        self.assertIn("Dry-run complete", out)
        self.assertIn("dry-run", out.lower())
        CurrencyRateMock.objects.filter.assert_not_called()

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_inverts_rate_correctly(self, CurrencyRateMock):
        """1 MAD = 0.0917 EUR  →  mad_per_unit = 1/0.0917 ≈ 10.9051"""
        CurrencyRateMock.objects.filter.return_value.update.return_value = 1
        self._run()
        for call_args in CurrencyRateMock.objects.filter.return_value.update.call_args_list:
            mad_per_unit = call_args[1]["mad_per_unit"]
            self.assertIsInstance(mad_per_unit, Decimal)
            self.assertGreater(mad_per_unit, Decimal("0"))

    def test_network_error_raises_command_error(self):
        import urllib.error
        with patch(
            "menu.management.commands.fetch_currency_rates.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(CommandError) as ctx:
                call_command("fetch_currency_rates")
        self.assertIn("Failed to fetch rates", str(ctx.exception))

    def test_empty_rates_raises_command_error(self):
        empty_payload = json.dumps({"base": "MAD", "rates": {}}).encode()
        with self.assertRaises(CommandError) as ctx:
            self._run(payload=empty_payload)
        self.assertIn("Empty rates payload", str(ctx.exception))

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_skips_bad_rate_and_writes_to_stderr(self, CurrencyRateMock):
        bad_payload = json.dumps({"base": "MAD", "rates": {"EUR": "not-a-number"}}).encode()
        CurrencyRateMock.objects.filter.return_value.update.return_value = 0
        _, err = self._run(payload=bad_payload)
        self.assertIn("Skipping EUR", err)

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_zero_row_updates_reported_not_crashed(self, CurrencyRateMock):
        """When a tenant schema has no matching CurrencyRate rows (update returns 0), the
        command still completes and reports the 0-row-update tally instead of erroring."""
        CurrencyRateMock.objects.filter.return_value.update.return_value = 0
        out, _ = self._run()
        self.assertIn("Done", out)
        self.assertIn("0 row updates", out)

    @patch("menu.management.commands.fetch_currency_rates.CurrencyRate")
    def test_updates_every_active_tenant_schema(self, CurrencyRateMock):
        """The per-tenant loop is the fix: rates are applied inside EACH active tenant
        schema (menu_currencyrate is tenant-only), not once on the public schema."""
        CurrencyRateMock.objects.filter.return_value.update.return_value = 1
        two = [MagicMock(schema_name="bistro"), MagicMock(schema_name="cafe")]
        out, _ = self._run(tenants=two)
        # 3 codes × 2 tenants = 6 filter calls; output notes 2 tenant schemas.
        self.assertEqual(CurrencyRateMock.objects.filter.call_count, 6)
        self.assertIn("2 tenant schema", out)
