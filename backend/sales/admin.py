from django.contrib import admin
from django.contrib.auth import get_user_model

from tenancy.models import Plan, Tenant, Domain
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
from .services import issue_activation


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "status", "plan", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("name", "email", "phone", "source")
    actions = ["confirm_sale", "resend_activation"]

    def confirm_sale(self, request, queryset):
        User = get_user_model()
        default_plan = Plan.objects.filter(code="starter").first()
        for lead in queryset:
            plan = lead.plan or default_plan
            slug = lead.email.split("@")[0] if lead.email else f"tenant-{lead.id}"
            tenant, _ = Tenant.objects.get_or_create(
                slug=slug,
                defaults={
                    "schema_name": slug,
                    "name": lead.name or slug,
                    "plan": plan,
                },
            )
            Domain.objects.get_or_create(domain=f"{slug}.localhost", defaults={"tenant": tenant, "is_primary": True})
            owner_email = lead.email or f"{slug}@example.com"
            user, created = User.objects.get_or_create(
                username=owner_email,
                defaults={
                    "email": owner_email,
                    "role": User.Roles.TENANT_OWNER,
                },
            )
            if created:
                user.set_password(User.objects.make_random_password())
            user.tenant = tenant
            user.save()
            Subscription.objects.get_or_create(tenant=tenant, plan=plan)
            job = ProvisioningJob.objects.create(lead=lead, tenant=tenant, status=ProvisioningJob.Status.SUCCESS)
            job.append_log("Provisioning completed")
            lead.status = Lead.Status.LIVE
            lead.save(update_fields=["status"])
        self.message_user(request, "Sale confirmed and tenant provisioned (dev placeholder)")

    confirm_sale.short_description = "Confirm sale and provision tenant"

    def resend_activation(self, request, queryset):
        for lead in queryset:
            tenant = lead.tenant_set.first() if hasattr(lead, "tenant_set") else None
            if not tenant:
                continue
            owner = tenant.users.filter(role=get_user_model().Roles.TENANT_OWNER).first()
            if not owner:
                continue
            (
                activation,
                admin_url,
                workspace_url,
                signin_url,
                tenant_url,
                activation_url,
                whatsapp_link,
                whatsapp_message_template,
            ) = issue_activation(tenant, owner)
            job = ProvisioningJob.objects.create(lead=lead, tenant=tenant, status=ProvisioningJob.Status.SUCCESS)
            job.append_log("Resent activation")
            job.append_log(f"Activation token: {activation.token}")
            job.append_log(f"Workspace URL: {workspace_url}")
            job.append_log(f"Sign-in URL: {signin_url}")
            job.append_log(f"Django admin URL: {admin_url}")
            job.append_log(f"Tenant URL: {tenant_url}")
            job.append_log(f"Activation URL: {activation_url}")
            if whatsapp_link:
                job.append_log(f"WhatsApp link: {whatsapp_link}")
            if whatsapp_message_template:
                job.append_log("WhatsApp template refreshed")
        self.message_user(request, "Activation re-sent where possible")

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
    list_display = ("tenant", "current_plan", "target_plan", "status", "payment_method", "requested_at", "decided_at")
    list_filter = ("status", "payment_method", "target_plan", "requested_at")
    search_fields = ("tenant__slug", "requester__username", "payment_reference")
    readonly_fields = ("requested_at", "updated_at", "decided_at")


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
