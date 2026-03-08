from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from sales.audit import log_admin_action
from sales.models import AdminAuditLog

from .models import PasswordResetToken, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Roles", {"fields": ("role", "tenant")}),
    )
    list_display = ("username", "email", "role", "tenant", "is_active")
    list_filter = ("role", "is_active")

    def save_model(self, request, obj, form, change):
        previous_role = None
        if change:
            previous_role = User.objects.filter(pk=obj.pk).values_list("role", flat=True).first()
        super().save_model(request, obj, form, change)
        if previous_role and previous_role != obj.role:
            log_admin_action(
                action=AdminAuditLog.Actions.USER_ROLE_CHANGED,
                request=request,
                actor=request.user,
                tenant=obj.tenant,
                target_repr=f"user:{obj.id}",
                metadata={
                    "username": obj.username,
                    "previous_role": previous_role,
                    "new_role": obj.role,
                },
            )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "used_at", "created_at")
    search_fields = ("user__username", "user__email", "token")
    list_filter = ("used_at",)
