import secrets
from datetime import timedelta
from decimal import Decimal

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
    loyalty_points = models.PositiveIntegerField(
        default=0,
        help_text="Accumulated loyalty points, redeemable for wallet credits at each restaurant.",
    )
    # Driver flags — is_driver marks an APPLICATION; driver_approved gates going online.
    is_driver = models.BooleanField(default=False, db_index=True)
    driver_approved = models.BooleanField(
        default=False,
        help_text="A platform admin has vetted and approved this driver. Only approved drivers can go online or accept jobs.",
    )
    driver_vehicle = models.CharField(
        max_length=120, blank=True,
        help_text="Driver's vehicle, supplied at application (e.g. 'Motorbike — 1234-AB').",
    )
    is_driver_online = models.BooleanField(default=False)
    driver_lat = models.FloatField(null=True, blank=True)
    driver_lng = models.FloatField(null=True, blank=True)
    driver_position_updated_at = models.DateTimeField(null=True, blank=True)
    # Notification preferences — customer-controlled opt-outs (default opted-in).
    notify_order_updates = models.BooleanField(
        default=True,
        help_text="Receive order status updates by email/SMS (e.g. confirmed, ready).",
    )
    notify_review_prompts = models.BooleanField(
        default=True,
        help_text="Receive the post-order 'rate your order' reminder push.",
    )
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
        LOYALTY = "loyalty", "Loyalty redemption"
        TRANSFER_OUT = "transfer_out", "Transfer sent"      # P2P gift sent (out)
        TRANSFER_IN = "transfer_in", "Transfer received"    # P2P gift received (in)
        ADJUSTMENT = "adjustment", "Adjustment"             # admin/policy correction
        EARNING = "earning", "Delivery earning"             # driver payout for a delivered job
        CASHOUT = "cashout", "Cash-out"                     # driver redeemed wallet for cash at a restaurant

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
    # Ledger-integrity fields. `amount` is always a positive magnitude; `type`
    # indicates direction (payment = out; topup/refund/bonus/loyalty = in).
    # idempotency_key makes money ops safe to retry (e.g. a re-delivered Stripe
    # webhook): a repeat with the same key reuses the original row instead of
    # double-crediting. balance_after snapshots the running balance for audit.
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default="MAD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.amount} — {self.customer}"


class DriverPayout(models.Model):
    """Records a settlement paid by the platform to a delivery driver.

    A driver *earns* driver_payout on each delivered DeliveryJob; this records what has
    been paid out to them (cash/transfer). Amount owed = sum(delivered payouts) − sum(
    these payouts). Append-only + idempotent, like the wallet ledger.
    """

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Bank transfer"

    driver = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=200, blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    actor_user_id = models.IntegerField(null=True, blank=True)
    currency = models.CharField(max_length=8, default="MAD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Payout {self.amount} to driver {self.driver_id}"


class DriverCashoutRequest(models.Model):
    """A driver redeeming wallet balance for cash at a restaurant. The driver creates a
    request (amount + a short code) once their wallet is ≥ the minimum; they show the code
    to any restaurant, whose staff confirms handing over the cash. On confirm we atomically
    debit the driver's wallet and credit that restaurant's float (the platform reimburses
    the restaurant). Mirrors WalletChargeRequest but in the opposite direction.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    driver = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="cashout_requests")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="MAD")
    code = models.CharField(max_length=12, db_index=True, help_text="Short code the driver shows the restaurant.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    # The restaurant that fulfilled the cash-out (set on confirm) + who confirmed it.
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    actor_user_id = models.IntegerField(null=True, blank=True)
    wallet_tx_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "expires_at"))]

    def __str__(self) -> str:
        return f"Cashout {self.amount} ({self.status}) driver {self.driver_id}"


class CustomerOrderRef(models.Model):
    """Public-schema mirror of a customer's order, for cross-restaurant history.

    Orders live in each tenant's own schema, so there is no single place to list a
    customer's marketplace activity. This lightweight index is kept in sync by a signal
    on Order save (menu app), letting the customer's account and the admin show orders
    across ALL restaurants without scanning every tenant schema per request.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="order_refs",
    )
    tenant_id = models.IntegerField(db_index=True)
    restaurant_name = models.CharField(max_length=200, blank=True)
    restaurant_slug = models.CharField(max_length=200, blank=True)
    order_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, blank=True)
    fulfillment_type = models.CharField(max_length=20, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="MAD")
    order_created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Compact items snapshot for re-order: [{slug, name, qty, unit_price}]
    items_snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("-order_created_at",)
        constraints = [
            models.UniqueConstraint(fields=("tenant_id", "order_number"), name="uniq_order_ref_per_tenant_order"),
        ]
        indexes = [
            models.Index(fields=["customer", "-order_created_at"], name="order_ref_customer_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"OrderRef {self.order_number} @ {self.restaurant_name} ({self.status})"


class WalletChargeRequest(models.Model):
    """A wallet charge that needs the CUSTOMER's explicit approval before money moves.

    Small charges (at or below the approval threshold) debit instantly on QR scan — the
    scan is consent enough for a small tap. Above the threshold, the owner/staff create
    one of these PENDING requests; the customer approves it in their app, and only then
    is the wallet debited. Short-lived (TTL) so a forgotten request can't be approved
    much later. Lives in the public schema (links a platform Customer to a tenant_id).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CHARGED = "charged", "Charged"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="charge_requests")
    tenant_id = models.IntegerField(db_index=True)
    restaurant_name = models.CharField(max_length=200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default="MAD")
    order_number = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    # Idempotency key for the eventual debit_wallet, generated at creation so a
    # double-tapped approval (or a retry after top-up) can't debit twice.
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    actor_user_id = models.IntegerField(null=True, blank=True)  # owner/staff who initiated
    wallet_tx_id = models.IntegerField(null=True, blank=True)   # resulting WalletTransaction id
    # The debit runs in the public schema (customer approval), which can't reach the
    # tenant-schema Order. The owner's poll (in tenant context) applies the bill update
    # once and flips this, so repeated polls don't double-count it.
    bill_synced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["customer", "status"], name="charge_req_customer_status_idx"),
        ]

    def __str__(self) -> str:
        return f"ChargeRequest {self.amount} {self.status} — {self.customer} @ {self.restaurant_name}"


class PlatformConfig(models.Model):
    """Platform-wide settings editable by a platform admin. Single row (pk=1), public schema.

    Keeps operationally-tunable values out of env vars so a platform admin can change them
    live. Fall back to the matching Django setting when a row hasn't been created yet.
    """

    # Wallet charges ABOVE this amount require customer approval; at/below debit instantly
    # on QR scan. 0 means every charge needs approval. In the platform base currency (MAD).
    wallet_charge_approval_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("50.00")
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform configuration"

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce a single row
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return "Platform configuration"


class CustomerPushSubscription(models.Model):
    """Browser Web Push subscription for a platform CUSTOMER (public schema).

    Parallels menu.PushSubscription (owner/staff, tenant schema). Used to nudge a customer
    to approve a pending wallet charge even when the app is backgrounded or closed.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField(help_text="Client public key (URL-safe base64)")
    auth = models.CharField(max_length=200, help_text="Auth secret (URL-safe base64)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Push sub for customer {self.customer_id}"


class TenantFloatTransaction(models.Model):
    """Append-only ledger for a restaurant's distributable wallet float.

    The platform funds a restaurant (FUND, +); the owner spends that float down by
    topping up customer wallets (DISTRIBUTION, -). Each distribution is paired with a
    Customer-side WalletTransaction so the two ledgers reconcile. `amount` is always a
    positive magnitude; `type` records direction. Lives in the public schema.
    """

    class Type(models.TextChoices):
        FUND = "fund", "Platform funding"          # platform -> restaurant float (in)
        DISTRIBUTION = "distribution", "Client top-up"  # restaurant float -> client (out)
        REVERSAL = "reversal", "Reversal"          # undo a distribution (in)

    tenant_id = models.IntegerField(db_index=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # For DISTRIBUTION/REVERSAL: the customer who received/returned the funds.
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_float",
    )
    # Who initiated the movement (platform admin for FUND, owner/staff for DISTRIBUTION).
    actor_user_id = models.IntegerField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=200, blank=True)
    currency = models.CharField(max_length=8, default="MAD")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_type_display()} {self.amount} — tenant {self.tenant_id}"


class WalletVoucher(models.Model):
    """Single-use wallet credit voucher.  Created by admins; redeemed by customers."""

    code = models.CharField(max_length=32, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    is_used = models.BooleanField(default=False, db_index=True)
    used_by = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redeemed_vouchers",
    )
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Voucher {self.code} ({self.amount})"

    @staticmethod
    def generate_code(length: int = 10) -> str:
        import random, string
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=length))
            if not WalletVoucher.objects.filter(code=code).exists():
                return code


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
        CANCELLED = "cancelled", "Cancelled"  # the underlying order was cancelled

    class FailureReason(models.TextChoices):
        CUSTOMER_NO_SHOW = "customer_no_show", "Customer not reachable / no-show"
        BAD_ADDRESS = "bad_address", "Address wrong or not found"
        DRIVER_UNABLE = "driver_unable", "Driver unable (vehicle, accident…)"
        OTHER = "other", "Other"

    class Resolution(models.TextChoices):
        REDISPATCHED = "redispatched", "Re-dispatched"
        REFUNDED_CANCELLED = "refunded_cancelled", "Refunded & cancelled"
        NOSHOW_PAID = "noshow_paid", "Driver paid (no-show)"

    # Statuses where a driver is actively holding the job (assigned but not yet terminal).
    ACTIVE_STATUSES = ("assigned", "at_restaurant", "picked_up")

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
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Failure / recovery (unhappy-path handling) ──────────────────────────────
    failure_reason = models.CharField(
        max_length=20, choices=FailureReason.choices, blank=True,
        help_text="Why the driver marked this delivery failed.",
    )
    failure_note = models.CharField(max_length=300, blank=True)
    # Owner has been alerted that this job is stuck (no driver) — set once by the sweep.
    owner_alerted_at = models.DateTimeField(null=True, blank=True)
    # How many times this job has been re-offered (bounds re-dispatch loops; audit).
    redispatch_count = models.PositiveSmallIntegerField(default=0)
    # How the owner/system resolved a failed job.
    resolution = models.CharField(max_length=20, choices=Resolution.choices, blank=True)
    # Proof-of-delivery code brute-force guard.
    code_attempts = models.PositiveSmallIntegerField(default=0)
    code_locked_until = models.DateTimeField(null=True, blank=True)

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
        indexes = [
            models.Index(fields=["status", "owner_alerted_at"]),
        ]

    def __str__(self) -> str:
        return f"DeliveryJob {self.order_number} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            self.Status.DELIVERED,
            self.Status.FAILED,
            self.Status.CANCELLED,
        )


class SavedAddress(models.Model):
    """A delivery address saved by a customer for quick reuse at checkout."""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="saved_addresses",
    )
    label = models.CharField(
        max_length=60,
        blank=True,
        help_text="Friendly label, e.g. 'Home', 'Work'. Optional.",
    )
    address = models.TextField(max_length=300)
    location_url = models.URLField(max_length=500, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        label = self.label or "Saved address"
        return f"{label} — {self.address[:60]}"


class NotificationLog(models.Model):
    """Durable audit trail of every outbound notification attempt (web push, SMS, email,
    WhatsApp) and its outcome. Lives in the public schema so it can be written from any
    tenant schema_context AND from platform-level (driver/customer) dispatch. Best-effort:
    writing a row must never break the notification path it records.
    """

    class Channel(models.TextChoices):
        PUSH = "push", "Web Push"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"  # not configured / no recipients

    channel = models.CharField(max_length=12, choices=Channel.choices, db_index=True)
    event = models.CharField(max_length=40, blank=True, help_text="e.g. order.new, order.ready, review_prompt, driver.dispatch")
    status = models.CharField(max_length=10, choices=Status.choices, db_index=True)
    recipient = models.CharField(max_length=120, blank=True, help_text="Phone / email / subscriber count — never sensitive payload.")
    detail = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=40, blank=True, db_index=True, help_text="Related order number, if any.")
    error = models.CharField(max_length=300, blank=True)
    # Loose tenant ref (public schema model) — null for platform-level notifications.
    tenant_id = models.IntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("tenant_id", "created_at")),
            models.Index(fields=("channel", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.channel}/{self.status} {self.event} {self.reference}".strip()
