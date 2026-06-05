from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Plan(models.Model):
    name = models.CharField(max_length=100)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    can_checkout = models.BooleanField(default=False)
    can_whatsapp_order = models.BooleanField(default=False)
    max_languages = models.PositiveIntegerField(default=1)
    # 0 = unlimited
    max_dishes = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of dishes allowed. 0 means unlimited.",
    )
    max_staff_accounts = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of staff accounts allowed. 0 means unlimited.",
    )
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
    # Days a tenant keeps working after a subscription payment lapses, before the
    # account is suspended. Single source of truth for the grace window.
    GRACE_PERIOD_DAYS = 7

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
    # Distributable wallet float. The platform funds this; the owner spends it down
    # by topping up customer wallets (prepaid, closed-loop). Cash is reconciled
    # offline. Movements are recorded in accounts.TenantFloatTransaction.
    float_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=LifecycleStatus.choices,
        default=LifecycleStatus.ACTIVE,
        db_index=True,
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.CharField(max_length=255, blank=True)
    payment_overdue_since = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when subscription payment is overdue. Tenant enters a 7-day grace period; after that the account should be suspended.",
    )
    deletion_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when the owner requests account deletion. Admin should review and complete the offboarding.",
    )
    deletion_reason = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional reason provided by the owner when requesting deletion.",
    )

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
    timezone = models.CharField(
        max_length=64, blank=True,
        help_text="IANA timezone (e.g. 'Africa/Casablanca') used to evaluate the business-hours "
                  "schedule for auto open/close. Blank falls back to the platform default.",
    )
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
    delivery_enabled = models.BooleanField(
        default=True,
        help_text="When False, the delivery fulfillment option is hidden from the customer checkout.",
    )
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text=(
            "Flat delivery fee. Used as a fallback when distance pricing is not "
            "configured (delivery_per_km = 0) or the customer's coordinates are unknown."
        ),
    )
    # ── Distance-based pricing (base + per-km) ──────────────────────────────
    # When delivery_per_km > 0 AND both the restaurant and the customer have
    # coordinates, the delivery fee is computed as
    #   fee = delivery_base_fee + delivery_per_km × distance_km
    # (distance = straight-line km from the restaurant to the delivery address).
    # Otherwise the flat delivery_fee above is used.
    delivery_base_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Base fee added before the per-km charge in distance-based pricing.",
    )
    delivery_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text=(
            "Per-kilometre delivery rate. 0 = disable distance pricing and use the "
            "flat delivery_fee instead."
        ),
    )
    delivery_free_over = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=(
            "Order subtotal at or above which delivery is free (0 = never free). "
            "Applies to both flat and distance-based pricing."
        ),
    )
    delivery_minimum_order = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Minimum order total required to unlock the delivery option (0 = no minimum).",
    )
    delivery_zone_description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Short description of the delivery area shown to customers (e.g. '5 km radius — city centre only').",
    )
    platform_delivery_enabled = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, each delivery order automatically creates a job for the "
            "platform driver network. Leave off if the restaurant handles its own delivery."
        ),
    )
    receipt_message = models.CharField(
        max_length=300,
        blank=True,
        help_text="Optional thank-you note shown to the customer on their order confirmation page.",
    )
    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=(
            "VAT/TVA rate as a percentage (e.g. 20.00 = 20%). Menu prices are treated "
            "as VAT-inclusive: the charged total is unchanged, and this rate is used "
            "only to break the VAT amount out on orders, receipts and invoices. "
            "0 = no VAT line shown."
        ),
    )
    vat_label = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Label for the tax line on receipts (e.g. 'VAT', 'TVA'). Defaults to 'VAT' when blank.",
    )
    MENU_THEME_CHOICES = [
        ("dark", "Dark (default)"),
        ("light", "Light"),
        ("warm", "Warm"),
    ]
    menu_theme = models.CharField(
        max_length=20,
        choices=MENU_THEME_CHOICES,
        default="dark",
        help_text="Visual colour theme for the public-facing menu page.",
    )
    sms_notifications_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, customers receive an SMS when their order status changes to 'ready'. Requires Twilio credentials in environment.",
    )
    cod_enabled = models.BooleanField(
        default=False,
        help_text="Allow trusted repeat customers to pay cash on handover for pickup/delivery instead of prepaying from their wallet.",
    )
    cod_min_paid_orders = models.PositiveSmallIntegerField(
        default=3,
        help_text="Number of completed & paid orders a customer must have before cash-on-handover is offered to them.",
    )
    auto_confirm_reservations = models.BooleanField(
        default=False,
        help_text="Automatically confirm (status → won) new reservation requests that are far enough in advance.",
    )
    auto_confirm_min_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text="Minimum hours in advance a reservation must be booked to qualify for auto-confirm. 0 = always auto-confirm regardless of timing.",
    )
    max_covers_per_slot = models.PositiveSmallIntegerField(
        default=0,
        help_text="Maximum number of covers (guests) per time slot. 0 = unlimited — capacity management disabled.",
    )
    SLOT_DURATION_CHOICES = [
        (30, "30 minutes"),
        (60, "1 hour"),
        (90, "1.5 hours"),
        (120, "2 hours"),
    ]
    slot_duration_minutes = models.PositiveSmallIntegerField(
        default=60,
        choices=SLOT_DURATION_CHOICES,
        help_text="Duration of each reservation time slot in minutes. Used when max_covers_per_slot > 0.",
    )
    reservation_reminders_enabled = models.BooleanField(
        default=False,
        help_text="When enabled, customers receive an email (and SMS if configured) ~2 hours before their confirmed reservation.",
    )
    MENU_CARD_LAYOUT_CHOICES = [
        ("row",     "Row (image-right compact card — Wolt/Deliveroo style)"),
        ("card",    "Card (image-top grid card)"),
        ("compact", "Compact (name + price + add button, single line)"),
    ]
    menu_card_layout = models.CharField(
        max_length=10,
        choices=MENU_CARD_LAYOUT_CHOICES,
        default="row",
        help_text="Controls how dish items appear on the public menu page.",
    )
    # ── Platform directory & marketplace ─────────────────────────────────────
    directory_opt_in = models.BooleanField(
        default=False,
        help_text="Show this restaurant in the platform's public directory. Off by default.",
    )
    cuisine_type = models.CharField(
        max_length=60,
        blank=True,
        help_text="Cuisine category shown in the directory (e.g. Italian, Moroccan, Japanese).",
    )
    city = models.CharField(
        max_length=80,
        blank=True,
        help_text="City shown in the directory.",
    )
    # Coordinates for distance-aware marketplace sorting.
    lat = models.FloatField(
        null=True,
        blank=True,
        help_text="Latitude of the restaurant (decimal degrees). Used for distance sorting in the marketplace.",
    )
    lng = models.FloatField(
        null=True,
        blank=True,
        help_text="Longitude of the restaurant (decimal degrees). Used for distance sorting in the marketplace.",
    )
    # 1 = budget (€), 2 = mid-range (€€), 3 = premium (€€€)
    PRICE_TIER_CHOICES = [(1, "€"), (2, "€€"), (3, "€€€")]
    price_tier = models.PositiveSmallIntegerField(
        default=2,
        choices=PRICE_TIER_CHOICES,
        help_text="General price range indicator shown in the marketplace.",
    )
    # Freeform dietary / feature tags (e.g. ['vegetarian', 'halal', 'gluten-free'])
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Dietary and feature tags used for marketplace filtering.",
    )

    # ── Delivery zone & radius ─────────────────────────────────────────────────
    delivery_zone_id = models.IntegerField(
        null=True, blank=True, db_index=True,
        help_text="ID of the DeliveryZone this restaurant is assigned to (public schema).",
    )
    delivery_radius_km = models.FloatField(
        null=True, blank=True,
        help_text="Maximum delivery distance in km from the restaurant's coordinates.",
    )

    is_open = models.BooleanField(default=True)
    is_menu_temporarily_disabled = models.BooleanField(default=False)
    menu_disabled_note = models.CharField(max_length=180, blank=True)
    is_menu_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Profile for {self.tenant.slug}"
