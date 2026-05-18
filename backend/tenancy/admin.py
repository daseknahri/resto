from django.contrib import admin

from sales.audit import log_admin_action
from sales.models import AdminAuditLog

from .models import Domain, FeatureFlag, Plan, Profile, Tenant


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "can_checkout", "can_whatsapp_order", "max_languages", "max_dishes", "max_staff_accounts", "is_active")
    list_filter = ("is_active", "can_checkout", "can_whatsapp_order")
    fieldsets = (
        (None, {"fields": ("name", "code", "description", "is_active")}),
        ("Features", {"fields": ("can_checkout", "can_whatsapp_order", "max_languages")}),
        ("Limits (0 = unlimited)", {"fields": ("max_dishes", "max_staff_accounts")}),
    )


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("plan", "key", "enabled")
    list_filter = ("plan", "enabled")
    search_fields = ("key",)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "schema_name", "is_active", "lifecycle_status", "payment_overdue_since")
    list_filter = ("plan", "is_active", "lifecycle_status")
    search_fields = ("name", "slug", "schema_name")
    fieldsets = (
        (None, {"fields": ("name", "slug", "schema_name", "plan", "owner", "is_active", "lifecycle_status")}),
        ("Lifecycle timestamps", {"fields": ("suspended_at", "canceled_at", "canceled_reason")}),
        ("Billing / grace period", {
            "fields": ("payment_overdue_since",),
            "description": "Set 'payment overdue since' when a subscription payment is missed. The tenant sees a warning banner for 7 days, then the account should be suspended manually.",
        }),
        ("Offboarding / deletion", {
            "fields": ("deletion_requested_at", "deletion_reason"),
            "description": "Read-only — set by the owner when they request account deletion. Review and complete offboarding manually.",
        }),
    )
    readonly_fields = ("deletion_requested_at", "deletion_reason")

    def save_model(self, request, obj, form, change):
        previous_is_active = None
        previous_lifecycle = None
        if change:
            existing = Tenant.objects.filter(pk=obj.pk).values_list("is_active", "lifecycle_status").first()
            if existing:
                previous_is_active, previous_lifecycle = existing
        if obj.is_active and obj.lifecycle_status != Tenant.LifecycleStatus.ACTIVE:
            obj.lifecycle_status = Tenant.LifecycleStatus.ACTIVE
            obj.suspended_at = None
            obj.canceled_at = None
            obj.canceled_reason = ""
        elif not obj.is_active and obj.lifecycle_status == Tenant.LifecycleStatus.ACTIVE:
            obj.lifecycle_status = Tenant.LifecycleStatus.SUSPENDED
        super().save_model(request, obj, form, change)

        if previous_is_active is True and obj.is_active is False:
            log_admin_action(
                action=AdminAuditLog.Actions.TENANT_DEACTIVATED,
                request=request,
                actor=request.user,
                tenant=obj,
                target_repr=f"tenant:{obj.slug}",
                metadata={
                    "tenant_name": obj.name,
                    "lifecycle_status": obj.lifecycle_status,
                    "previous_lifecycle_status": previous_lifecycle or "",
                },
            )
        elif previous_is_active is False and obj.is_active is True:
            log_admin_action(
                action=AdminAuditLog.Actions.TENANT_REACTIVATED,
                request=request,
                actor=request.user,
                tenant=obj,
                target_repr=f"tenant:{obj.slug}",
                metadata={
                    "tenant_name": obj.name,
                    "lifecycle_status": obj.lifecycle_status,
                    "previous_lifecycle_status": previous_lifecycle or "",
                },
            )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("tenant", "phone", "whatsapp", "language")
    search_fields = ("tenant__slug", "phone", "whatsapp")
