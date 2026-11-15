from django.contrib import admin
from django.contrib import messages
from django.contrib.admin import helpers
from django.shortcuts import render

from .audit import log_admin_action
from .models import (
    ActivationToken,
    AdminAuditLog,
    Deal,
    Lead,
    ProvisioningJob,
    ReservationReminder,
    ReservationTimelineEvent,
    Subscription,
    TierUpgradeRequest,
)
from .redaction import mask_token_in
from .services import provision_lead, resend_activation_for_lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "status", "plan", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("name", "email", "phone", "source")
    actions = ["confirm_sale", "resend_activation"]

    def confirm_sale(self, request, queryset):
        """Provision each selected lead through the canonical provisioning service.

        Delegates to sales.services.provision_lead so the admin action behaves exactly
        like the platform-console flow (slug/domain resolution, plan validation, owner
        account, subscription, activation token + audit log) instead of duplicating it.

        A-47: provisioning creates tenants and issues activation links, so the
        action does NOT run on the first "Go" click. It first renders an
        intermediate confirmation page listing the selected leads; provisioning
        runs only when the admin confirms on that page (POST confirm=yes).
        """
        if request.POST.get("confirm") != "yes":
            # Minimal context on purpose: admin_site.each_context() builds
            # the app list, which calls every registered admin's permission
            # methods — including PlatformConfigAdmin.has_add_permission,
            # which reads the DB. The confirm page needs no app list.
            context = {
                "title": "Confirm provisioning",
                "site_title": self.admin_site.site_title,
                "site_header": self.admin_site.site_header,
                "site_url": self.admin_site.site_url,
                "has_permission": True,
                "leads": queryset,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "opts": self.model._meta,
            }
            return render(request, "admin/sales/lead/confirm_provision.html", context)
        provisioned = 0
        for lead in queryset:
            try:
                provision_lead(lead)
                provisioned += 1
            except ValueError as exc:
                # Expected, actionable failures (no plan, already provisioned, slug taken).
                self.message_user(request, f"{lead.name}: {exc}", level=messages.WARNING)
            except Exception as exc:  # noqa: BLE001 — surface unexpected errors to the admin
                self.message_user(request, f"{lead.name}: provisioning failed — {exc}", level=messages.ERROR)
        if provisioned:
            self.message_user(request, f"Provisioned {provisioned} tenant(s) and issued activation links.")

    confirm_sale.short_description = "Confirm sale and provision tenant"

    def resend_activation(self, request, queryset):
        """Resend through the same service as the platform console's resend
        (sales.services.resend_activation_for_lead): it finds the tenant via the
        lead's successful ProvisioningJob, refuses an owner who already activated,
        and logs only the MASKED token."""
        resent = 0
        for lead in queryset:
            try:
                result = resend_activation_for_lead(lead)
            except ValueError as exc:
                # Expected, actionable: not provisioned yet / owner already activated.
                self.message_user(request, f"{lead.name}: {exc}", level=messages.WARNING)
                continue
            except Exception as exc:  # noqa: BLE001 — surface unexpected errors to the admin
                self.message_user(request, f"{lead.name}: activation resend failed — {exc}", level=messages.ERROR)
                continue
            log_admin_action(
                action=AdminAuditLog.Actions.ACTIVATION_RESENT,
                request=request,
                tenant=result.tenant,
                lead=lead,
                target_repr=f"tenant:{result.tenant.slug}",
                metadata={
                    "activation_url": mask_token_in(result.activation_url, result.activation_token.token),
                    "source": "django_admin",
                },
            )
            resent += 1
        if resent:
            self.message_user(request, f"Activation re-sent for {resent} lead(s).")

    resend_activation.short_description = "Resend activation for selected leads"


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("lead", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("tenant", "plan", "status", "start_date", "end_date")
    list_filter = ("status", "plan")
    # A-41: status is owned by the subscription enforcement / billing flow —
    # hand-editing it here would bypass enforce_subscriptions.
    readonly_fields = ("status",)


@admin.register(TierUpgradeRequest)
class TierUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "current_plan", "target_plan", "status", "payment_method", "invoice_amount", "invoice_currency", "requested_at", "decided_at")
    list_filter = ("status", "payment_method", "target_plan", "requested_at")
    search_fields = ("tenant__slug", "requester__username", "payment_reference")
    # A-37: the decision lives in the decision endpoint (payment verification,
    # decision audit, decided_by enforcement). Saving status="approved" in the
    # admin would skip all of that, so status/approved_by/decided_at are
    # read-only here; decisions happen only via the endpoint.
    readonly_fields = ("status", "approved_by", "decided_at", "requested_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("tenant", "requester", "current_plan", "target_plan", "status", "approved_by", "decided_at")}),
        ("Payment", {"fields": ("payment_method", "payment_reference", "invoice_amount", "invoice_currency")}),
        ("Notes", {"fields": ("customer_note", "admin_note")}),
        ("Timestamps", {"fields": ("requested_at", "updated_at")}),
    )


@admin.register(ProvisioningJob)
class ProvisioningJobAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "tenant", "status", "created_at")
    list_filter = ("status",)
    # A-40: a failed job must not be flippable to "success" by hand — status,
    # lead and tenant are the provisioning record, owned by the service.
    readonly_fields = ("lead", "tenant", "status", "log")


@admin.register(ActivationToken)
class ActivationTokenAdmin(admin.ModelAdmin):
    list_display = ("tenant", "user", "expires_at", "used_at")
    list_filter = ("expires_at", "used_at")
    readonly_fields = ("token",)


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "tenant", "lead", "target_repr")
    list_filter = ("action", "created_at")
    search_fields = ("actor__username", "tenant__slug", "lead__name", "target_repr")
    readonly_fields = ("action", "actor", "tenant", "lead", "target_repr", "ip_address", "metadata", "created_at")
    # A-39: the audit trail is evidence — rows must not be addable or
    # deletable from the panel (the log is what A-34/A-35/A-37 rely on).
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReservationTimelineEvent)
class ReservationTimelineEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "lead", "tenant", "action", "actor", "previous_status", "new_status")
    list_filter = ("action", "created_at", "tenant")
    search_fields = ("lead__name", "note", "actor__username", "tenant__slug")
    # A-46: status history is evidence — every field readonly.
    readonly_fields = ("lead", "tenant", "actor", "action", "note", "previous_status", "new_status", "created_at")


@admin.register(ReservationReminder)
class ReservationReminderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "lead", "tenant", "channel", "status", "phone", "actor")
    list_filter = ("channel", "status", "created_at", "tenant")
    search_fields = ("lead__name", "phone", "message", "failure_reason", "tenant__slug")
    readonly_fields = ("created_at", "updated_at")
