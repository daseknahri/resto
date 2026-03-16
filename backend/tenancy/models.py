from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Plan(models.Model):
    name = models.CharField(max_length=100)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    can_checkout = models.BooleanField(default=False)
    can_whatsapp_order = models.BooleanField(default=False)
    max_languages = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class FeatureFlag(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="feature_flags")
    key = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False)
    config = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = ("plan", "key")

    def __str__(self) -> str:
        return f"{self.plan.code}:{self.key}"


class Tenant(TenantMixin):
    class LifecycleStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CANCELED = "canceled", "Canceled"

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="tenants")
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_tenants",
    )
    is_active = models.BooleanField(default=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.ACTIVE,
        db_index=True,
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.CharField(max_length=255, blank=True)

    auto_create_schema = True

    def __str__(self) -> str:
        return self.name


class Domain(DomainMixin):
    pass


class Profile(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name="profile")
    tagline = models.CharField(max_length=150, blank=True)
    tagline_i18n = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    description_i18n = models.JSONField(default=dict, blank=True)
    business_hours = models.TextField(blank=True)
    business_hours_i18n = models.JSONField(default=dict, blank=True)
    business_hours_schedule = models.JSONField(default=dict, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    whatsapp = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    address_i18n = models.JSONField(default=dict, blank=True)
    google_maps_url = models.URLField(blank=True)
    reservation_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default="#0F766E")
    secondary_color = models.CharField(max_length=7, default="#F59E0B")
    language = models.CharField(max_length=5, default="en")
    logo_url = models.URLField(blank=True)
    hero_url = models.URLField(blank=True)
    is_open = models.BooleanField(default=True)
    is_menu_temporarily_disabled = models.BooleanField(default=False)
    menu_disabled_note = models.CharField(max_length=180, blank=True)
    is_menu_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Profile for {self.tenant.slug}"
