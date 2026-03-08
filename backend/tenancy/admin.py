from django.contrib import admin

from sales.audit import log_admin_action
from sales.models import AdminAuditLog

from .models import Domain, FeatureFlag, Plan, Profile, Tenant


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "can_checkout", "can_whatsapp_order", "max_languages", "is_active")
    list_filter = ("is_active", "can_checkout", "can_whatsapp_order")


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("plan", "key", "enabled")
    list_filter = ("plan", "enabled")
    search_fields = ("key",)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "schema_name", "is_active")
    list_filter = ("plan", "is_active")
    search_fields = ("name", "slug", "schema_name")

    def save_model(self, request, obj, form, change):
        previous_is_active = None
        if change:
            previous_is_active = Tenant.objects.filter(pk=obj.pk).values_list("is_active", flat=True).first()
        super().save_model(request, obj, form, change)

        if previous_is_active is True and obj.is_active is False:
            log_admin_action(
                action=AdminAuditLog.Actions.TENANT_DEACTIVATED,
                request=request,
                actor=request.user,
                tenant=obj,
                target_repr=f"tenant:{obj.slug}",
                metadata={"tenant_name": obj.name},
            )
        elif previous_is_active is False and obj.is_active is True:
            log_admin_action(
                action=AdminAuditLog.Actions.TENANT_REACTIVATED,
                request=request,
                actor=request.user,
                tenant=obj,
                target_repr=f"tenant:{obj.slug}",
                metadata={"tenant_name": obj.name},
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
