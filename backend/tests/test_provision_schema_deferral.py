"""RISK MULTITENANCY-1 (surfaced by the e2e job): tenant provisioning must build the
physical schema OUTSIDE the provisioning transaction.

A new tenant's migrations include AddIndexConcurrently (CREATE INDEX CONCURRENTLY),
which Postgres forbids inside a transaction — so the previous
`Tenant.objects.create()` inside `transaction.atomic()` 500'd on every signup. The
restructured `provision_lead` (sales/services.py) now:
  1. creates the tenant ROW with auto_create_schema=False (save() does NOT build the
     schema in-transaction), then calls create_schema() AFTER the transaction commits;
  2. on a schema-build failure, rolls the tenant back (deletes it so the slug frees for
     retry), marks the ProvisioningJob FAILED (not SUCCESS), and never sends activation.

Provisioning hardening regressions (same harness):
  - H2: the lead row is locked and a fresh RUNNING job blocks a second provision (a
    double click used to create a second tenant + schema); a stale RUNNING job is
    superseded (marked FAILED) instead of blocking forever.
  - H3: a failed build drops the schema THIS attempt created (it used to be orphaned,
    and a retry "succeeded" on the half-migrated schema); a pre-existing schema is
    never adopted nor dropped.
  - M2: an existing account is never silently re-parented off another restaurant, and
    platform/staff accounts are never attached to a tenant.
  - M3: a reserved slug / platform-host domain is refused at provision time.

These are mock-based (SimpleTestCase, no DB), following test_tier_structure.py's
provision_lead pattern; the real end-to-end success path is exercised by the e2e job.
"""
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from sales.models import Lead, ProvisioningJob
from sales.services import (
    PROVISIONING_STALE_AFTER,
    _drop_schema_created_by_attempt,
    provision_lead,
)

SUCCESS = ProvisioningJob.Status.SUCCESS
RUNNING = ProvisioningJob.Status.RUNNING
FAILED = ProvisioningJob.Status.FAILED


def _noop_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _job_filter(*, in_flight=False, stale_jobs=(), abandoned_attempt=False):
    """side_effect for ProvisioningJob.objects.filter, keyed on the query's kwargs."""

    def _filter(**kwargs):
        qs = MagicMock()
        if kwargs.get("status") == SUCCESS:  # "already provisioned" check
            qs.exists.return_value = False
        elif "created_at__gte" in kwargs:  # in-flight RUNNING check
            qs.exists.return_value = in_flight
        elif "created_at__lt" in kwargs:  # stale RUNNING jobs to supersede
            qs.__iter__.return_value = iter(list(stale_jobs))
        elif "tenant_id" in kwargs:  # owner's current tenant = abandoned attempt of this lead?
            qs.exclude.return_value.exists.return_value = abandoned_attempt
        return qs

    return _filter


class _ProvisionHarness(SimpleTestCase):
    def _setup(
        self,
        create_schema_side_effect=None,
        *,
        slug="demo-co",
        domain="demo-co.localhost",
        schema_preexists=False,
        drop_result=True,
        existing_user=None,
        **job_filter_kwargs,
    ):
        plan = type("Plan", (), {"code": "starter", "is_active": True})()
        lead = MagicMock(id=42, plan=plan, name="Demo Co", email="owner@demo.test",
                         phone="", onboarded_at=None)

        specs = {
            "schema_context": patch("sales.services.schema_context", return_value=_noop_cm()),
            "atomic": patch("sales.services.transaction.atomic", return_value=_noop_cm()),
            "log_event": patch("sales.services._log_provisioning_event"),
            "preview": patch(
                "sales.services.preview_lead_provision",
                return_value={"resolved_slug": slug, "resolved_domain": domain},
            ),
            "Lead": patch("sales.services.Lead"),
            "Tenant": patch("sales.services.Tenant"),
            "Domain": patch("sales.services.Domain"),
            "get_user_model": patch("sales.services.get_user_model"),
            "Subscription": patch("sales.services.Subscription"),
            "ProvisioningJob": patch("sales.services.ProvisioningJob"),
            "issue_activation": patch("sales.services.issue_activation"),
            "schema_exists": patch("sales.services.schema_exists", return_value=schema_preexists),
            "drop_schema": patch(
                "sales.services._drop_schema_created_by_attempt", return_value=drop_result
            ),
        }
        m = {name: p.start() for name, p in specs.items()}
        for p in specs.values():
            self.addCleanup(p.stop)

        m["Lead"].DoesNotExist = Lead.DoesNotExist  # real exception class
        m["ProvisioningJob"].Status = ProvisioningJob.Status  # real enum values
        m["ProvisioningJob"].objects.filter.side_effect = _job_filter(**job_filter_kwargs)
        m["Tenant"].objects.filter.return_value.exists.return_value = False
        m["Domain"].objects.filter.return_value.exists.return_value = False

        User = m["get_user_model"].return_value
        User.Roles.TENANT_OWNER = "tenant_owner"
        if existing_user is None:
            User.objects.get_or_create.return_value = (MagicMock(id=7, email="owner@demo.test"), True)
        else:
            User.objects.get_or_create.return_value = (MagicMock(pk=existing_user.pk), False)
            User.objects.select_for_update.return_value.get.return_value = existing_user

        job = MagicMock(id=99, status=RUNNING)
        m["ProvisioningJob"].objects.create.return_value = job
        m["issue_activation"].return_value = (
            MagicMock(token="tok"), "admin", "workspace", "signin", "tenant", "activation", "wa", "tmpl",
        )

        tenant = m["Tenant"].return_value  # the Tenant(...) constructor result
        tenant.schema_name = slug
        if create_schema_side_effect is not None:
            tenant.create_schema.side_effect = create_schema_side_effect
        return m, tenant, job, lead

    @staticmethod
    def _logged(job):
        return " | ".join(str(c.args[0]) for c in job.append_log.call_args_list)


class ProvisionSchemaDeferralTests(_ProvisionHarness):
    def test_schema_creation_is_deferred_then_run_explicitly(self):
        m, tenant, job, lead = self._setup()
        provision_lead(lead, domain_suffix="localhost")
        # Row built without in-transaction schema creation, then schema created after.
        self.assertFalse(tenant.auto_create_schema)
        tenant.save.assert_called_once()
        tenant.create_schema.assert_called_once_with(check_if_exists=True)
        self.assertEqual(job.status, SUCCESS)
        m["drop_schema"].assert_not_called()

    def test_schema_failure_rolls_back_tenant_and_marks_job_failed(self):
        m, tenant, job, lead = self._setup(create_schema_side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            provision_lead(lead, domain_suffix="localhost")
        # Tenant row deleted (slug freed for retry); job FAILED; activation never sent.
        m["Tenant"].objects.filter.return_value.delete.assert_called_once()
        self.assertEqual(job.status, FAILED)
        m["issue_activation"].assert_not_called()


class ProvisionConcurrencyTests(_ProvisionHarness):
    """H2 — a double click / repeated admin action must not create a second tenant."""

    def test_lead_row_is_locked_before_provisioning(self):
        m, tenant, job, lead = self._setup()
        provision_lead(lead, domain_suffix="localhost")
        m["Lead"].objects.select_for_update.assert_called_once_with()
        m["Lead"].objects.select_for_update.return_value.only.return_value.get.assert_called_once_with(pk=42)

    def test_in_flight_running_job_blocks_second_provision(self):
        m, tenant, job, lead = self._setup(in_flight=True)
        with self.assertRaisesMessage(ValueError, "already in progress"):
            provision_lead(lead, domain_suffix="localhost")
        # Nothing new is created: no tenant row, no schema, no job, no activation.
        m["Tenant"].assert_not_called()
        m["Domain"].objects.create.assert_not_called()
        m["ProvisioningJob"].objects.create.assert_not_called()
        tenant.create_schema.assert_not_called()
        m["issue_activation"].assert_not_called()

    def test_in_flight_window_is_the_stale_threshold(self):
        m, tenant, job, lead = self._setup(in_flight=True)
        with self.assertRaises(ValueError):
            provision_lead(lead, domain_suffix="localhost")
        in_flight_query = next(
            c.kwargs for c in m["ProvisioningJob"].objects.filter.call_args_list
            if "created_at__gte" in c.kwargs
        )
        self.assertIs(in_flight_query["lead"], lead)
        self.assertEqual(in_flight_query["status"], RUNNING)
        expected_cutoff = timezone.now() - PROVISIONING_STALE_AFTER
        self.assertLess(abs(expected_cutoff - in_flight_query["created_at__gte"]), timedelta(seconds=30))

    def test_stale_running_job_is_superseded_not_blocking(self):
        stale = MagicMock(id=5, status=RUNNING, tenant_id=11)
        m, tenant, job, lead = self._setup(stale_jobs=[stale])
        provision_lead(lead, domain_suffix="localhost")
        self.assertEqual(stale.status, FAILED)
        stale.save.assert_called_once_with(update_fields=["status", "updated_at"])
        self.assertIn("Superseded", self._logged(stale))
        # ...and the new attempt goes through.
        tenant.create_schema.assert_called_once()
        self.assertEqual(job.status, SUCCESS)

    def test_deleted_lead_is_a_clear_error(self):
        m, tenant, job, lead = self._setup()
        m["Lead"].objects.select_for_update.return_value.only.return_value.get.side_effect = Lead.DoesNotExist
        with self.assertRaisesMessage(ValueError, "Lead no longer exists"):
            provision_lead(lead, domain_suffix="localhost")
        m["Tenant"].assert_not_called()

    def test_already_provisioned_lead_still_blocked(self):
        m, tenant, job, lead = self._setup()

        def _filter(**kwargs):
            qs = MagicMock()
            qs.exists.return_value = kwargs.get("status") == SUCCESS
            return qs

        m["ProvisioningJob"].objects.filter.side_effect = _filter
        with self.assertRaisesMessage(ValueError, "already provisioned"):
            provision_lead(lead, domain_suffix="localhost")
        m["Tenant"].assert_not_called()


class ProvisionOrphanSchemaTests(_ProvisionHarness):
    """H3 — a failed build must not leave an orphan schema a retry would adopt."""

    def test_failure_drops_schema_created_by_this_attempt(self):
        m, tenant, job, lead = self._setup(create_schema_side_effect=RuntimeError("migration boom"))
        with self.assertRaisesMessage(RuntimeError, "migration boom"):
            provision_lead(lead, domain_suffix="localhost")
        m["drop_schema"].assert_called_once_with("demo-co")
        m["Tenant"].objects.filter.return_value.delete.assert_called_once()
        self.assertEqual(job.status, FAILED)
        self.assertIn("dropped", self._logged(job))
        m["issue_activation"].assert_not_called()

    def test_preexisting_schema_is_neither_adopted_nor_dropped(self):
        m, tenant, job, lead = self._setup(schema_preexists=True)
        with self.assertRaisesMessage(ValueError, "already exists"):
            provision_lead(lead, domain_suffix="localhost")
        # Not adopted (no create_schema that would skip migrating it) and not dropped.
        tenant.create_schema.assert_not_called()
        m["drop_schema"].assert_not_called()
        # Same rollback as any other phase-2 failure.
        m["Tenant"].objects.filter.return_value.delete.assert_called_once()
        self.assertEqual(job.status, FAILED)
        m["issue_activation"].assert_not_called()

    def test_failed_drop_still_rolls_back_and_raises_original_error(self):
        m, tenant, job, lead = self._setup(
            create_schema_side_effect=RuntimeError("migration boom"), drop_result=False
        )
        with self.assertRaisesMessage(RuntimeError, "migration boom"):
            provision_lead(lead, domain_suffix="localhost")
        m["Tenant"].objects.filter.return_value.delete.assert_called_once()
        self.assertEqual(job.status, FAILED)
        self.assertIn("could not drop", self._logged(job))


class ProvisionOwnerReparentTests(_ProvisionHarness):
    """M2 — never silently move an existing account onto the new tenant."""

    def _user(self, *, tenant_id=None, role="tenant_owner", is_superuser=False, is_staff=False):
        return MagicMock(pk=7, id=7, tenant_id=tenant_id, role=role,
                         is_superuser=is_superuser, is_staff=is_staff)

    def _assert_refused(self, user, message, **setup_kwargs):
        m, tenant, job, lead = self._setup(existing_user=user, **setup_kwargs)
        with self.assertRaisesMessage(ValueError, message):
            provision_lead(lead, domain_suffix="localhost")
        # Refused before any tenant/domain row is built, and the account is untouched.
        m["Tenant"].assert_not_called()
        m["Domain"].objects.create.assert_not_called()
        user.save.assert_not_called()
        return m

    def test_owner_of_another_restaurant_is_refused(self):
        user = self._user(tenant_id=3)
        self._assert_refused(user, "already owns another restaurant")
        self.assertEqual(user.tenant_id, 3)

    def test_platform_admin_account_is_refused(self):
        self._assert_refused(self._user(role="platform_superadmin"), "platform or staff account")

    def test_superuser_account_is_refused(self):
        self._assert_refused(self._user(is_superuser=True), "platform or staff account")

    def test_staff_flag_account_is_refused(self):
        self._assert_refused(self._user(is_staff=True), "platform or staff account")

    def test_tenant_staff_account_is_refused(self):
        self._assert_refused(self._user(role="tenant_staff"), "platform or staff account")

    def test_existing_owner_without_restaurant_is_reused_under_lock(self):
        user = self._user(tenant_id=None)
        m, tenant, job, lead = self._setup(existing_user=user)
        provision_lead(lead, domain_suffix="localhost")
        User = m["get_user_model"].return_value
        User.objects.select_for_update.return_value.get.assert_called_once_with(pk=7)
        self.assertIs(user.tenant, tenant)
        user.save.assert_called_once()
        user.set_password.assert_not_called()  # an existing password is never reset

    def test_owner_of_abandoned_attempt_of_same_lead_is_reused(self):
        user = self._user(tenant_id=11)
        m, tenant, job, lead = self._setup(existing_user=user, abandoned_attempt=True)
        provision_lead(lead, domain_suffix="localhost")
        m["ProvisioningJob"].objects.filter.assert_any_call(lead=lead, tenant_id=11)
        self.assertIs(user.tenant, tenant)
        self.assertEqual(job.status, SUCCESS)


class ProvisionReservedSlugTests(_ProvisionHarness):
    """M3 — reserved slugs / platform hosts are refused even if the preview let one through."""

    def test_reserved_slug_is_refused(self):
        m, tenant, job, lead = self._setup(slug="admin", domain="admin.example.com")
        with self.assertRaisesMessage(ValueError, "reserved"):
            provision_lead(lead, domain_suffix="example.com")
        m["Tenant"].assert_not_called()

    @override_settings(PUBLIC_SCHEMA_HOSTS=["localhost", "shop.example.com"])
    def test_platform_host_domain_is_refused(self):
        m, tenant, job, lead = self._setup(slug="shop", domain="shop.example.com")
        with self.assertRaisesMessage(ValueError, "reserved"):
            provision_lead(lead, domain_suffix="example.com")
        m["Tenant"].assert_not_called()


class DropSchemaCreatedByAttemptTests(SimpleTestCase):
    """H3 — the DROP helper only ever runs a quoted, validated identifier."""

    def _conn(self):
        conn = MagicMock()
        conn.ops.quote_name.side_effect = lambda name: f'"{name}"'
        cursor = conn.cursor.return_value.__enter__.return_value
        return conn, cursor

    def test_drops_valid_schema_with_quoted_identifier(self):
        conn, cursor = self._conn()
        with patch("sales.services.connections") as connections:
            connections.__getitem__.return_value = conn
            self.assertTrue(_drop_schema_created_by_attempt("demo-co_2"))
        conn.set_schema_to_public.assert_called_once()
        cursor.execute.assert_called_once_with('DROP SCHEMA IF EXISTS "demo-co_2" CASCADE')

    def test_refuses_unsafe_or_reserved_names(self):
        for name in ['bad"name', "Upper", "a.b", "has space", "x;drop", "", "-lead",
                     "public", "pg_catalog", "pg_toast", "information_schema", "a" * 64]:
            with self.subTest(name=name), patch("sales.services.connections") as connections:
                self.assertFalse(_drop_schema_created_by_attempt(name))
                connections.__getitem__.assert_not_called()

    def test_database_error_returns_false(self):
        conn, cursor = self._conn()
        cursor.execute.side_effect = RuntimeError("db gone")
        with patch("sales.services.connections") as connections:
            connections.__getitem__.return_value = conn
            self.assertFalse(_drop_schema_created_by_attempt("demo-co"))


class StaleThresholdTests(SimpleTestCase):
    def test_stale_threshold_is_well_above_request_timeouts(self):
        # Must comfortably exceed the ~60s worker/request timeout so a live attempt is
        # never superseded mid-build.
        self.assertGreaterEqual(PROVISIONING_STALE_AFTER, timedelta(minutes=10))
