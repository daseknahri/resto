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

These are mock-based (SimpleTestCase, no DB), following test_tier_structure.py's
provision_lead pattern; the real end-to-end success path is exercised by the e2e job.
"""
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase

from sales.models import ProvisioningJob
from sales.services import provision_lead


def _noop_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


class ProvisionSchemaDeferralTests(SimpleTestCase):
    def _setup(self, create_schema_side_effect=None):
        plan = type("Plan", (), {"code": "starter", "is_active": True})()
        lead = MagicMock(id=42, plan=plan, name="Demo Co", email="owner@demo.test",
                         phone="", onboarded_at=None)

        specs = {
            "schema_context": patch("sales.services.schema_context", return_value=_noop_cm()),
            "atomic": patch("sales.services.transaction.atomic", return_value=_noop_cm()),
            "log_event": patch("sales.services._log_provisioning_event"),
            "preview": patch(
                "sales.services.preview_lead_provision",
                return_value={"resolved_slug": "demo-co", "resolved_domain": "demo-co.localhost"},
            ),
            "Tenant": patch("sales.services.Tenant"),
            "Domain": patch("sales.services.Domain"),
            "get_user_model": patch("sales.services.get_user_model"),
            "Subscription": patch("sales.services.Subscription"),
            "ProvisioningJob": patch("sales.services.ProvisioningJob"),
            "issue_activation": patch("sales.services.issue_activation"),
        }
        m = {name: p.start() for name, p in specs.items()}
        for p in specs.values():
            self.addCleanup(p.stop)

        m["ProvisioningJob"].objects.filter.return_value.exists.return_value = False
        m["ProvisioningJob"].Status = ProvisioningJob.Status  # real enum values
        m["Tenant"].objects.filter.return_value.exists.return_value = False
        m["Domain"].objects.filter.return_value.exists.return_value = False
        m["get_user_model"].return_value.objects.get_or_create.return_value = (
            MagicMock(id=7, email="owner@demo.test"),
            True,
        )
        m["get_user_model"].return_value.Roles.TENANT_OWNER = "tenant_owner"
        job = MagicMock(id=99, status=ProvisioningJob.Status.RUNNING)
        m["ProvisioningJob"].objects.create.return_value = job
        m["issue_activation"].return_value = (
            MagicMock(token="tok"), "admin", "workspace", "signin", "tenant", "activation", "wa", "tmpl",
        )

        tenant = m["Tenant"].return_value  # the Tenant(...) constructor result
        if create_schema_side_effect is not None:
            tenant.create_schema.side_effect = create_schema_side_effect
        return m, tenant, job, lead

    def test_schema_creation_is_deferred_then_run_explicitly(self):
        m, tenant, job, lead = self._setup()
        provision_lead(lead, domain_suffix="localhost")
        # Row built without in-transaction schema creation, then schema created after.
        self.assertFalse(tenant.auto_create_schema)
        tenant.save.assert_called_once()
        tenant.create_schema.assert_called_once_with(check_if_exists=True)
        self.assertEqual(job.status, ProvisioningJob.Status.SUCCESS)

    def test_schema_failure_rolls_back_tenant_and_marks_job_failed(self):
        m, tenant, job, lead = self._setup(create_schema_side_effect=RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            provision_lead(lead, domain_suffix="localhost")
        # Tenant row deleted (slug freed for retry); job FAILED; activation never sent.
        m["Tenant"].objects.filter.return_value.delete.assert_called_once()
        self.assertEqual(job.status, ProvisioningJob.Status.FAILED)
        m["issue_activation"].assert_not_called()
