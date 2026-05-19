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
    email = models.EmailField(blank=True, db_index=True)
    name = models.CharField(max_length=80, blank=True)
    locale = models.CharField(max_length=10, default="en")
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Driver flags — set by the platform when a customer registers as a delivery driver
    is_driver = models.BooleanField(default=False, db_index=True)
    is_driver_online = models.BooleanField(default=False)
    driver_lat = models.FloatField(null=True, blank=True)
    driver_lng = models.FloatField(null=True, blank=True)
    driver_position_updated_at = models.DateTimeField(null=True, blank=True)
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

    # ── Granular staff permissions ─────────────────────────────────────────────
    # These only apply to tenant_staff users; owners always have all capabilities.
    # Defaults reflect safe, read-only posture: staff can manage orders (core
    # waiter job) but cannot view revenue or change the menu without explicit grant.
    perm_manage_orders = models.BooleanField(
        default=True,
        help_text="Staff can view and update order statuses.",
    )
    perm_view_revenue = models.BooleanField(
        default=False,
        help_text="Staff can view revenue analytics and financial summaries.",
    )
    perm_edit_menu = models.BooleanField(
        default=False,
        help_text="Staff can create, edit and delete menu items.",
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

    def effective_perm_manage_orders(self) -> bool:
        """Owners always have this; staff respect the flag."""
        return self.is_tenant_owner or self.perm_manage_orders

    def effective_perm_view_revenue(self) -> bool:
        """Owners always have this; staff respect the flag."""
        return self.is_tenant_owner or self.perm_view_revenue

    def effective_perm_edit_menu(self) -> bool:
        """Owners always have this; staff respect the flag."""
        return self.is_tenant_owner or self.perm_edit_menu


class CustomerRating(models.Model):
    """
    Owner's trust assessment of a customer — stored in the public schema so every
    restaurant on the platform can see a customer's aggregate trust score.

    One record per (customer, tenant, order) — owners can update but not spam.
    Score is 1–5 (5 = trustworthy, 1 = problematic).
    The rating is *private*: customers never see individual scores, only platform
    admins and the restaurant that rated them can see the note.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="trust_ratings",
    )
    tenant_id = models.IntegerField(db_index=True)
    order_number = models.CharField(max_length=20, blank=True, db_index=True)
    score = models.PositiveSmallIntegerField()  # 1–5
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("customer", "tenant_id", "order_number")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Trust {self.score}/5 for {self.customer} (tenant {self.tenant_id})"


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


class PlatformFlashSale(models.Model):
    """
    Platform-sponsored discount campaigns — live in the public schema.
    The platform creates these; individual restaurants opt in voluntarily.
    When a customer orders from an opted-in restaurant through the marketplace,
    the flash sale discount is applied (up to 100% of order total).
    """

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    # Percentage discount applied to the food subtotal
    discount_value = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Percentage off the food subtotal (e.g. 15.00 = 15%).",
    )
    active_from = models.DateTimeField()
    active_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    # Optional cap on total platform-wide redemptions across all restaurants
    max_redemptions = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maximum total redemptions across all opted-in restaurants. Null = unlimited.",
    )
    redemption_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-active_from",)

    def __str__(self) -> str:
        return f"{self.name} ({self.discount_value}% off)"

    def is_live(self) -> bool:
        """True if the sale is currently in its active window."""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.active_from or now > self.active_until:
            return False
        if self.max_redemptions is not None and self.redemption_count >= self.max_redemptions:
            return False
        return True


class PlatformFlashSaleOptIn(models.Model):
    """
    A restaurant's voluntary opt-in to a platform flash sale.
    Only opted-in restaurants apply the discount to marketplace orders.
    """

    flash_sale = models.ForeignKey(
        PlatformFlashSale,
        on_delete=models.CASCADE,
        related_name="opt_ins",
    )
    tenant_id = models.IntegerField(db_index=True)
    opted_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("flash_sale", "tenant_id")
        ordering = ("-opted_in_at",)

    def __str__(self) -> str:
        return f"Tenant {self.tenant_id} opted into {self.flash_sale}"


class DeliveryZone(models.Model):
    """
    Platform-defined delivery zone for a city — stored in the public schema.

    Zones are created by platform admins and used to:
    - Show restaurants which area they serve.
    - Constrain delivery availability (orders outside the zone are rejected).
    - Enable distance-based fee tiers.

    The polygon is stored as a JSON list of {lat, lng} objects forming a closed shape.
    """

    name = models.CharField(max_length=100, help_text="e.g. 'Paris 1–4 Arrondissements'")
    city = models.CharField(max_length=100, db_index=True)
    # Polygon: [{lat: 48.86, lng: 2.34}, ...]  — must have ≥ 3 points, last = first to close
    polygon = models.JSONField(
        default=list,
        help_text="List of {lat, lng} objects forming the zone boundary.",
    )
    # Approximate centre for quick distance checks
    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)
    # Rough radius in km (used as a quick pre-filter before point-in-polygon check)
    approx_radius_km = models.FloatField(default=5.0)
    is_active = models.BooleanField(default=True)
    # Distance-based fee tiers: [{"km_up_to": 3, "fee": 2.50}, {"km_up_to": 7, "fee": 4.00}, {"km_up_to": null, "fee": 6.00}]
    # Tiers are evaluated in order; first matching tier wins. null km_up_to = catch-all.
    fee_tiers = models.JSONField(
        default=list,
        blank=True,
        help_text='e.g. [{"km_up_to": 3, "fee": 2.5}, {"km_up_to": null, "fee": 5.0}]',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("city", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"

    def compute_fee(self, distance_km: float) -> float:
        """Return the delivery fee for a given distance using this zone's fee_tiers."""
        if not self.fee_tiers:
            return 0.0
        for tier in sorted(
            self.fee_tiers,
            key=lambda t: t.get("km_up_to") if t.get("km_up_to") is not None else float("inf"),
        ):
            if tier.get("km_up_to") is None or distance_km <= float(tier["km_up_to"]):
                return float(tier.get("fee", 0))
        return 0.0


class DeliveryJob(models.Model):
    """
    Represents one delivery assignment — links an order (tenant-scoped) to a driver (Customer).

    Lives in the PUBLIC schema. Uses loose references (tenant_id + order_number) instead of
    a cross-schema FK to the Order model.

    Lifecycle:
      searching → assigned → at_restaurant → picked_up → delivered
                                                        ↘ failed

    Three-way ratings are stored here (customer→driver, driver→customer, restaurant→driver).
    """

    class Status(models.TextChoices):
        SEARCHING = "searching", "Searching for driver"
        ASSIGNED = "assigned", "Driver assigned"
        AT_RESTAURANT = "at_restaurant", "At restaurant"
        PICKED_UP = "picked_up", "Picked up"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    # Cross-schema reference to the tenant order
    tenant_id = models.IntegerField(db_index=True)
    order_number = models.CharField(max_length=20, db_index=True)

    driver = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_jobs",
        limit_choices_to={"is_driver": True},
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SEARCHING,
        db_index=True,
    )

    # Addresses & coordinates
    pickup_address = models.CharField(max_length=200, blank=True)
    pickup_lat = models.FloatField(null=True, blank=True)
    pickup_lng = models.FloatField(null=True, blank=True)
    delivery_address = models.CharField(max_length=200, blank=True)
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)

    # Financials
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Driver's share (platform keeps the rest)
    driver_payout = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # Delivery zone (optional — set if order is inside a managed zone)
    zone = models.ForeignKey(
        DeliveryZone,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs",
    )

    # Timestamps
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Three-way ratings ──────────────────────────────────────────────────────
    # Customer rates the driver (speed, professionalism)
    customer_driver_rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–5
    customer_driver_note = models.CharField(max_length=200, blank=True)
    # Driver rates the customer (accessibility, behavior)
    driver_customer_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    driver_customer_note = models.CharField(max_length=200, blank=True)
    # Restaurant rates the driver (on-time pickup, communication)
    restaurant_driver_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    restaurant_driver_note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("tenant_id", "order_number")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"DeliveryJob {self.order_number} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.Status.DELIVERED, self.Status.FAILED)
