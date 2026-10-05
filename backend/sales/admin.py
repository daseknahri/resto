from django.contrib import admin

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
from django.contrib import messages

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
        """
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


@admin.register(TierUpgradeRequest)
class TierUpgradeRequestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "current_plan", "target_plan", "status", "payment_method", "invoice_amount", "invoice_currency", "requested_at", "decided_at")
    list_filter = ("status", "payment_method", "target_plan", "requested_at")
    search_fields = ("tenant__slug", "requester__username", "payment_reference")
    readonly_fields = ("requested_at", "updated_at", "decided_at")
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
    readonly_fields = ("log",)


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


@admin.register(ReservationTimelineEvent)
class ReservationTimelineEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "lead", "tenant", "action", "actor", "previous_status", "new_status")
    list_filter = ("action", "created_at", "tenant")
    search_fields = ("lead__name", "note", "actor__username", "tenant__slug")
    readonly_fields = ("created_at",)


@admin.register(ReservationReminder)
class ReservationReminderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "lead", "tenant", "channel", "status", "phone", "actor")
    list_filter = ("channel", "status", "created_at", "tenant")
    search_fields = ("lead__name", "phone", "message", "failure_reason", "tenant__slug")
    readonly_fields = ("created_at", "updated_at")
