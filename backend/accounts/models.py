import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Roles(models.TextChoices):
        PLATFORM_SUPERADMIN = "platform_superadmin", "Platform Superadmin"
        TENANT_OWNER = "tenant_owner", "Tenant Owner"
        TENANT_STAFF = "tenant_staff", "Tenant Staff"

    role = models.CharField(
        max_length=32,
        choices=Roles.choices,
        default=Roles.TENANT_OWNER,
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="Tenant the user belongs to; null for platform staff.",
    )

    @property
    def is_platform_admin(self) -> bool:
        return self.role == self.Roles.PLATFORM_SUPERADMIN

    @property
    def is_tenant_owner(self) -> bool:
        return self.role == self.Roles.TENANT_OWNER

    @property
    def is_tenant_staff(self) -> bool:
        return self.role == self.Roles.TENANT_STAFF


class PasswordResetToken(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, user, hours_valid: int = 2):
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        return cls.objects.create(
            user=user,
            token=secrets.token_hex(24),
            expires_at=timezone.now() + timedelta(hours=hours_valid),
        )

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def is_valid(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at

    def __str__(self):
        return f"Password reset for {self.user.username}"
