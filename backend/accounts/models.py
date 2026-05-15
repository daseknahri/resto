import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    """Platform-level customer identity — lives in the public schema, shared across all tenants."""

    # Phone is optional so Google-only customers can exist without a phone number.
    phone = models.CharField(max_length=30, unique=True, null=True, blank=True, db_index=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    # Google OAuth sub (unique identifier from Google's JWT). Null for phone-only customers.
    google_sub = models.CharField(max_length=200, unique=True, null=True, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=80, blank=True)
    locale = models.CharField(max_length=10, default="en")
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name or self.phone or self.email or f"Customer #{self.pk}"


class WalletTransaction(models.Model):
    """Records every credit movement on a customer's wallet (top-up, payment, refund, bonus)."""

    class Type(models.TextChoices):
        TOPUP = "topup", "Top-up"
        PAYMENT = "payment", "Payment"
        REFUND = "refund", "Refund"
        BONUS = "bonus", "Bonus"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # reference: order_number for payments/refunds, external ref for top-ups
    reference = models.CharField(max_length=100, blank=True)
    # tenant_id: which restaurant this payment was for (null for top-ups and bonuses)
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.amount} — {self.customer}"


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
