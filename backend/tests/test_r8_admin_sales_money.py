"""Run 8 G2 — A-37, A-39, A-40, A-41, A-46: sales Django-admin money hardening."""
from types import SimpleNamespace

from django.contrib import admin as django_admin
from django.test import RequestFactory, SimpleTestCase

from sales.admin import (
    AdminAuditLogAdmin,
    ProvisioningJobAdmin,
    ReservationTimelineEventAdmin,
    SubscriptionAdmin,
    TierUpgradeRequestAdmin,
)
from sales.models import (
    AdminAuditLog,
    ProvisioningJob,
    ReservationTimelineEvent,
    Subscription,
    TierUpgradeRequest,
)


def _admin(admin_cls, model):
    return admin_cls(model, django_admin.site)


def _request():
    request = RequestFactory().post("/admin/")
    request.user = SimpleNamespace(
        is_authenticated=True,
        is_active=True,
        is_staff=True,
        pk=1,
        has_module_perms=lambda app_label: True,
        has_perm=lambda perm: True,
    )
    return request


def _editable_fields(model):
    # The pk is auto-managed and never appears in an admin form.
    return {field.name for field in model._meta.fields if field.editable and not field.primary_key}


class TierUpgradeRequestAdminTests(SimpleTestCase):
    def test_decision_fields_are_readonly(self):
        admin = _admin(TierUpgradeRequestAdmin, TierUpgradeRequest)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue({"status", "approved_by", "decided_at"} <= readonly)


class AdminAuditLogAdminTests(SimpleTestCase):
    def test_audit_rows_cannot_be_added_or_deleted(self):
        admin = _admin(AdminAuditLogAdmin, AdminAuditLog)
        request = _request()
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_delete_permission(request, None))


class ProvisioningJobAdminTests(SimpleTestCase):
    def test_status_lead_tenant_are_readonly(self):
        admin = _admin(ProvisioningJobAdmin, ProvisioningJob)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue({"status", "lead", "tenant"} <= readonly)


class SubscriptionAdminTests(SimpleTestCase):
    def test_status_is_readonly(self):
        admin = _admin(SubscriptionAdmin, Subscription)
        self.assertIn("status", admin.get_readonly_fields(_request()))


class ReservationTimelineEventAdminTests(SimpleTestCase):
    def test_all_fields_are_readonly(self):
        admin = _admin(ReservationTimelineEventAdmin, ReservationTimelineEvent)
        readonly = set(admin.get_readonly_fields(_request()))
        self.assertTrue(
            _editable_fields(ReservationTimelineEvent) <= readonly,
            f"editable but not readonly: {_editable_fields(ReservationTimelineEvent) - readonly}",
        )
