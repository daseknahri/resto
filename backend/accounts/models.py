import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    """Platform-level customer identity — lives in the public schema, shared across all tenants."""

    # Phone is optional so Google-only customers can exist without a phone number.
    phone = models.CharField(max_length=30, unique=True, null=True, blank=True, db_index=True)
    # Last 9 digits of phone, stripped of non-digit chars — powers btree-indexed
    # exact-match search (avoids a full-table icontains scan on large customer sets).
    # Auto-maintained by the save() override.
    phone_digits = models.CharField(max_length=9, blank=True, default="", db_index=True)
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
    # Structured vehicle type for ride-hailing dispatch. Ride dispatch targets ONLY "car".
    VEHICLE_TYPE_MOTORBIKE = "motorbike"
    VEHICLE_TYPE_CAR = "car"
    VEHICLE_TYPE_BICYCLE = "bicycle"
    VEHICLE_TYPE_CHOICES = [
        (VEHICLE_TYPE_MOTORBIKE, "Motorbike"),
        (VEHICLE_TYPE_CAR, "Car"),
        (VEHICLE_TYPE_BICYCLE, "Bicycle"),
    ]
    driver_vehicle_type = models.CharField(
        max_length=12, blank=True, default="",
        choices=VEHICLE_TYPE_CHOICES,
        help_text="Structured vehicle type for ride dispatch (motorbike|car|bicycle).",
    )
    driver_licence_url = models.URLField(blank=True)
    driver_insurance_url = models.URLField(blank=True)
    driver_licence_expiry = models.DateField(
        null=True,
        blank=True,
        help_text="Expiry date of the uploaded driving licence. Admin-set when approving docs.",
    )
    driver_insurance_expiry = models.DateField(
        null=True,
        blank=True,
        help_text="Expiry date of the uploaded car insurance. Admin-set when approving docs.",
    )
    driver_car_approved = models.BooleanField(
        default=False,
        help_text=(
            "Admin verified licence+insurance; gates RIDE offers only — deliveries unaffected."
        ),
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
    notify_promotions = models.BooleanField(
        default=True,
        help_text="Receive occasional offers/announcements from restaurants you've ordered from.",
    )
    # ── Courier sender-handover opt-in (Wave 4 — Uber Connect parity) ─────────
    # Off by default → existing senders/couriers see the unchanged package
    # vocabulary ('Package picked up — on its way' for both arrived & in_progress
    # and the generic ride-worded courier buttons). When a customer opts in, the
    # package flow surfaces the distinct sender-side milestones: 'Courier arriving
    # for pickup' (arrived) vs 'Package collected — on the way' (in_progress, the
    # collected/handed-to-courier moment), and the courier's arrived→in_progress
    # button reads 'Confirm pickup'. Behaviour-preserving: this only re-labels the
    # SAME state machine; no transition or dispatch behaviour changes.
    package_handover_milestone = models.BooleanField(
        default=False,
        help_text=(
            "Opt-in: show the distinct sender-side 'collected / handed to courier' "
            "package milestone and package-specific (non-ride) status vocabulary. "
            "Off preserves today's collapsed 'picked up' labelling."
        ),
    )
    # ── Referral programme ────────────────────────────────────────────────────
    # referral_code: unique share code the customer gives to friends.
    # Auto-populated on first save (see save() override below).
    referral_code = models.CharField(
        max_length=12, unique=True, null=True, blank=True, db_index=True,
        help_text="Unique shareable code. Auto-generated; null until the customer record is first saved.",
    )
    # referred_by: which existing customer recruited this one.
    # Cleared (SET_NULL) rather than cascaded if the referrer is ever deleted.
    referred_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="referrals",
        help_text="Customer who referred this one.",
    )
    # referral_reward_given: True once the referral reward has been issued for this
    # customer (i.e., on their first qualifying paid order). Prevents double-credit.
    referral_reward_given = models.BooleanField(
        default=False,
        help_text="Reward already issued for this customer being a referral — never re-issue.",
    )
    # ── Loyalty depth (C3) ───────────────────────────────────────────────────
    # lifetime_loyalty_points: cumulative total ever earned (never decremented
    # when points are redeemed). Used for tier progression — a customer who spends
    # their points doesn't lose their tier status.
    lifetime_loyalty_points = models.PositiveIntegerField(
        default=0,
        help_text="Total loyalty points ever earned (never decremented). Used for tier calculation.",
    )
    birthday = models.DateField(
        null=True, blank=True,
        help_text="Customer's date of birth (YYYY-MM-DD). Day+month used for annual birthday reward.",
    )
    # Stores the calendar year the birthday bonus was last awarded.
    # Prevents awarding the bonus twice in the same calendar year.
    loyalty_birthday_rewarded_year = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Year the birthday loyalty bonus was last awarded. Guards against double-credit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name or self.phone or self.email or f"Customer #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            import uuid as _uuid
            self.referral_code = _uuid.uuid4().hex[:8].upper()
        # Keep phone_digits in sync — used for btree-indexed search.
        _raw = self.phone or ""
        _digits = "".join(c for c in _raw if c.isdigit())
        self.phone_digits = _digits[-9:] if _digits else ""
        super().save(*args, **kwargs)


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
    # Consumer vertical (food/shops/pharmacy/rides/courier/driver) this money
    # movement belongs to — REPORTING METADATA for per-service spend views only;
    # the balance is one global pool (the wallet is never partitioned). Null for
    # global rows (top-up, P2P transfer, admin adjustment). See accounts/verticals.py.
    vertical = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Consumer vertical this money movement belongs to (reporting only; "
            "the balance stays one global pool). Null for global rows (P1b)."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            # OPS-4 C: refund aggregate (OPS-2 cancel-refund EXISTS check + OPS-3 statement)
            # filters on (tenant_id, type, created_at) — keep PKs server-side.
            models.Index(
                fields=("tenant_id", "type", "created_at"),
                name="wallettx_tid_type_cat_idx",
            ),
        ]

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
    # Consumer vertical (food/shops/pharmacy/...) derived from the tenant's
    # business_type at index time, so "my orders" can scope per service (P1a).
    # Blank on legacy rows until the backfill runs. See accounts/verticals.py.
    vertical = models.CharField(
        max_length=16,
        blank=True,
        default="",
        db_index=True,
        help_text=(
            "Consumer vertical (food/shops/pharmacy/...) derived from the "
            "tenant's business_type at index time. Blank until backfilled (P1a)."
        ),
    )

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
    # ── Ride-hailing fare config ──────────────────────────────────────────────────
    ride_base_fare = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("8.00"))
    ride_per_km = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("3.50"))
    ride_minimum_fare = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("12.00"))
    # Platform commission on ride earnings (0 = driver keeps 100%).
    ride_commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    # Per-minute surcharge (0 = disabled — fully backward compatible).
    ride_per_minute = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
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
        # A voucher code is a bearer money-token: whoever knows it can credit a
        # wallet. It MUST be drawn from a CSPRNG, not the stdlib Mersenne-Twister
        # PRNG (predictable once enough draws leak). Use the secrets module like
        # the rest of the codebase (password reset tokens, ride/cash-out codes).
        # Same uppercase+digit alphabet and length so the UX / validation shape
        # is unchanged.
        import secrets, string
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(chars) for _ in range(length))
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
    perm_void = models.BooleanField(
        default=True,
        help_text=(
            "Staff can void order items and trigger the resulting partial wallet "
            "refund. Default True preserves existing behaviour; set False for "
            "waiters who should handle orders but not reverse them."
        ),
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

    def effective_perm_void(self) -> bool:
        """Owners always have this; staff respect the flag."""
        return self.is_tenant_owner or self.perm_void


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
    # Platform's cut of the delivery fee (delivery_fee = driver_payout + platform_commission).
    # Snapshot at job creation from the restaurant's delivery_commission_pct; default 0.
    platform_commission = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # The RATE (0–100 percent) that was applied when platform_commission was computed.
    # Stored separately so audits can detect if the rate changed after job creation.
    # decimal_places=4 supports sub-percent rates such as 12.57% or 0.75%.
    delivery_commission_rate_applied = models.DecimalField(
        max_digits=7, decimal_places=4, default=0
    )
    # Snapshot of the tenant's business_type at job creation. Avoids a cross-schema
    # Profile query every time a single-job endpoint serializes the job.
    business_type = models.CharField(max_length=40, blank=True, default="restaurant")

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
    # When the food is expected to be ready for pickup — the owner's prep ETA entered
    # at confirm time, mirrored from the order so the assigned driver can time their
    # arrival (pre-dispatch). Null = unknown / not yet estimated.
    food_ready_at = models.DateTimeField(null=True, blank=True)

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

    # ── Ranked-offer dispatch ───────────────────────────────────────────────────
    # The job is offered to the nearest free driver first (exclusively) for a short
    # window; on decline/timeout it cascades to the next nearest. When the cascade is
    # exhausted (or nobody is rankable) it opens to the whole pool (broadcast). See
    # accounts/dispatch.py.
    offered_to = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="offered_delivery_jobs", limit_choices_to={"is_driver": True},
        help_text="Driver currently holding the exclusive offer (None once open to the pool).",
    )
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    # Driver ids who declined or let the offer lapse — never re-offered this job.
    declined_by = models.JSONField(default=list, blank=True)
    # How many exclusive offers have been made (bounds the cascade; audit).
    offer_round = models.PositiveSmallIntegerField(default=0)
    # True once the job falls back to the open pool any free driver can claim.
    is_open_pool = models.BooleanField(default=False)

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


class RideRequest(models.Model):
    """A ride-hailing / package-delivery request — lives in the PUBLIC schema, accounts app.

    kind='ride'    — passenger ride (default, all existing behaviour unchanged).
    kind='package' — courier delivery; uses the same fare model as rides (MVP decision).

    Lifecycle (immediate):
      searching → accepted → arrived → in_progress → completed
                ↘ cancelled (from searching/accepted/arrived)

    Lifecycle (scheduled):
      scheduled → searching (released by sweep_ride_requests rule d when scheduled_for <= now+10min)
               ↘ cancelled (rider cancels before release)

    Mirrors DeliveryJob conventions: public schema, loose references, ratings stored here.
    """

    class Kind(models.TextChoices):
        RIDE = "ride", "Ride"
        PACKAGE = "package", "Package"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        SEARCHING = "searching", "Searching for driver"
        ACCEPTED = "accepted", "Driver accepted"
        ARRIVED = "arrived", "Driver arrived"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    VALID_TRANSITIONS = {
        "scheduled": {"searching", "cancelled"},
        "searching": {"accepted", "cancelled"},
        "accepted": {"arrived", "cancelled", "searching"},
        "arrived": {"in_progress", "cancelled"},
        "in_progress": {"completed"},
    }

    TERMINAL_STATUSES = {"completed", "cancelled"}

    class PaymentMethod(models.TextChoices):
        WALLET = "wallet", "Wallet"
        CASH = "cash", "Cash"

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
        default=Kind.RIDE,
        db_index=True,
    )

    # Package-specific fields (blank for rides)
    recipient_name = models.CharField(max_length=80, blank=True)
    recipient_phone = models.CharField(max_length=50, blank=True)
    package_note = models.CharField(max_length=200, blank=True)

    rider = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="rides",
    )
    driver = models.ForeignKey(
        Customer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="driven_rides",
        limit_choices_to={"is_driver": True},
    )

    pickup_lat = models.FloatField()
    pickup_lng = models.FloatField()
    dropoff_lat = models.FloatField()
    dropoff_lng = models.FloatField()
    pickup_address = models.CharField(max_length=255, blank=True)
    dropoff_address = models.CharField(max_length=255, blank=True)

    distance_km = models.FloatField()
    fare = models.DecimalField(max_digits=8, decimal_places=2)

    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.WALLET,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SEARCHING,
        db_index=True,
    )

    # Scheduled-trip fields (migration 0038).
    # scheduled_for: the rider-requested departure time (None for immediate trips).
    # dispatched_at: when the trip actually entered the SEARCHING pool.
    #   Immediate trips: set to now() at create time.
    #   Scheduled trips: left None at create; set to now() when sweep releases them.
    #   Pre-0038 rows have dispatched_at=None — the sweep falls back to created_at
    #   for them via a Q-OR branch (dispatched_at <= cutoff | null & created_at <= cutoff).
    scheduled_for = models.DateTimeField(null=True, blank=True, db_index=True)
    # Indexed: sweep rules (a)/(b) filter on dispatched_at every cycle.
    dispatched_at = models.DateTimeField(null=True, blank=True, db_index=True)
    predispatch_reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Stamped when the ~30-min pre-dispatch reminder is sent to the rider. "
            "Null = not yet sent. Used to prevent double-sending."
        ),
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Ratings: rider rates the driver; driver rates the rider (1–5).
    rider_driver_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    driver_rider_rating = models.PositiveSmallIntegerField(null=True, blank=True)

    # True once the wallet debit for this ride succeeded.
    paid_with_wallet = models.BooleanField(default=False)

    # ── Optional post-completion courier tip (migration 0063) ─────────────────
    # The SENDER (rider) may add an optional tip to the courier AFTER a package is
    # delivered (status='completed'). The tip is debited from the sender's wallet
    # and credited to the courier's wallet (reuses wallet_service, DRIVER vertical).
    # Default 0 → no tip; existing trips are entirely unaffected. A non-zero value
    # means the tip has been paid: the tip endpoint is idempotent (tip once) and
    # refuses a second tip once this is > 0.
    tip_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    # ── Package proof-of-delivery handover code (migration 0040) ──────────────
    # Generated at create time ONLY for kind='package' (6 random digits, zero-padded).
    # The sender shares this with the recipient out-of-band; the driver must enter it
    # when marking the trip completed. Never exposed in driver offer/active payloads or
    # admin lists — only in the rider's own active-trip serialization.
    delivery_code = models.CharField(max_length=6, blank=True, default="")
    code_attempts = models.PositiveSmallIntegerField(default=0)
    code_locked_until = models.DateTimeField(null=True, blank=True)

    # ── Recipient public-tracking token (migration 0061) ──────────────────────
    # Generated at create time ONLY for kind='package' — an opaque, URL-safe,
    # unguessable token (NOT sequential, NOT the pk). The recipient (who has no
    # account) receives a tokenized public link (/track/<token>) by SMS at
    # dispatch; the public no-auth track view resolves the trip by this token and
    # returns a recipient-safe projection. Empty for rides. Indexed for O(1)
    # lookup. Never exposed in driver/admin payloads.
    recipient_track_token = models.CharField(
        max_length=43, blank=True, default="", db_index=True
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["driver", "status"]),
        ]

    def __str__(self) -> str:
        return f"RideRequest #{self.pk} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES


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


class WinbackNudge(models.Model):
    """
    Durable dedupe record for the win-back automation cron.

    One row per (tenant, customer) nudge that was actually sent. The command
    checks this table before sending to ensure at most one nudge per 90 days,
    surviving cache flushes and process restarts.

    Lives in the public schema (accounts app) so it can be queried from any
    schema_context. Intentionally loose FKs (IntegerField) to avoid cross-schema
    FK constraint issues with django-tenants.
    """

    tenant_id = models.IntegerField(
        db_index=True,
        help_text="FK to tenancy.Tenant (loose — no FK constraint for cross-schema safety).",
    )
    customer_id = models.BigIntegerField(
        db_index=True,
        help_text="FK to accounts.Customer.",
    )
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-sent_at",)
        indexes = [
            models.Index(
                fields=("tenant_id", "customer_id", "sent_at"),
                name="winbacknudge_tenant_cust_sent",
            ),
        ]

    def __str__(self) -> str:
        return f"WinbackNudge tenant={self.tenant_id} customer={self.customer_id} @ {self.sent_at}"


class CustomerTenantOptOut(models.Model):
    """Per-(customer, tenant) promotional email opt-out for marketplace customers.

    A customer who clicks "unsubscribe" on Restaurant A's promo email should
    stop receiving Restaurant A's promos, NOT all restaurants'. This model
    stores the per-tenant opt-out so send_campaign_email_sync and
    send_winback_nudges can suppress promos per-restaurant.

    Lives in the public schema (accounts app). IntegerField tenant_id avoids
    cross-schema FK issues with django-tenants.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="tenant_optouts",
    )
    tenant_id = models.IntegerField(
        db_index=True,
        help_text="FK to tenancy.Tenant (loose — no FK constraint for cross-schema safety).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("customer", "tenant_id")]
        indexes = [
            models.Index(fields=("customer", "tenant_id"), name="cust_tenant_optout_idx"),
        ]

    def __str__(self) -> str:
        return f"CustomerTenantOptOut customer={self.customer_id} tenant={self.tenant_id}"


class CustomerServiceProfile(models.Model):
    """Per-(customer, vertical) profile — the "account for each service" (P2).

    A thin scoping record so each service surface (food / shops / pharmacy /
    rides / courier / driver) can carry its own preferences without bloating the
    global ``Customer`` row. Lazily created on first use; all fields
    nullable/defaulted, so a MISSING row means "use the customer's global
    defaults" (non-breaking).

    Lives in the public schema (accounts app). See KEPOLI_ACCOUNT_ARCHITECTURE.md L2.
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="service_profiles",
    )
    vertical = models.CharField(
        max_length=16,
        db_index=True,
        help_text="Consumer vertical this profile scopes (see accounts.verticals).",
    )
    # Per-service notification preferences. Default True (opt-out model). When no
    # row exists, the customer's global Customer.notify_* booleans apply. The
    # global flag stays the hard master switch — a per-vertical False only adds
    # suppression for this vertical (suppress-if-either; never re-enables).
    notify_updates = models.BooleanField(default=True)
    notify_promotions = models.BooleanField(default=True)
    # Default delivery/pickup address for THIS service (e.g. home for food, a
    # different drop for courier). Null → fall back to the customer's last-used.
    default_address = models.ForeignKey(
        "SavedAddress",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "vertical"),
                name="customerserviceprofile_customer_vertical_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=("customer", "vertical"), name="cust_service_profile_idx"),
        ]

    def __str__(self) -> str:
        return f"CustomerServiceProfile customer={self.customer_id} vertical={self.vertical}"

    @classmethod
    def get_or_create_for(cls, customer_id, vertical):
        """Lazily fetch (or create) the profile for (customer_id, vertical).

        Guards the vertical so a stray string can't create a junk row that would
        then leak into the services/prefs responses."""
        from .verticals import ALL_VERTICALS

        if vertical not in ALL_VERTICALS:
            raise ValueError(f"Unknown vertical: {vertical!r}")
        obj, _ = cls.objects.get_or_create(customer_id=customer_id, vertical=vertical)
        return obj


class CustomerEmailSuppression(models.Model):
    """Hard-bounce / spam-complaint suppression list for outbound marketing email.

    Fed by an ESP webhook (POST /api/public/email/suppression/). An email on this
    list is excluded from every outbound marketing audience (win-back nudges,
    owner campaigns) regardless of the customer's ``notify_promotions`` flag.

    Lives in the public schema (accounts app) so every audience query can reach
    it with a single cross-schema check.

    Note: this table suppresses by EMAIL ADDRESS, not customer_id. An address
    can bounce before or after a customer record is created, and the same address
    might appear on multiple Customer rows (if a customer re-registers).
    """

    class Reason(models.TextChoices):
        BOUNCE = "bounce", "Hard bounce"
        COMPLAINT = "complaint", "Spam complaint"
        MANUAL = "manual", "Manually suppressed"

    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="The suppressed email address (lower-cased by save).",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.BOUNCE)
    suppressed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    raw_event = models.JSONField(null=True, blank=True, help_text="Raw ESP webhook payload for audit.")

    class Meta:
        ordering = ("-suppressed_at",)

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"CustomerEmailSuppression({self.email}, {self.reason})"


class UserTOTPDevice(models.Model):
    """Per-user TOTP MFA device — lives in the public schema (accounts app).

    Lifecycle:
      1. POST /api/mfa/setup/   → row created/reset with confirmed=False, secret generated.
      2. POST /api/mfa/confirm/ → user supplies a TOTP code; on success confirmed=True +
                                  backup_codes (hashed, single-use) are generated and
                                  returned ONCE in plaintext.
      3. POST /api/mfa/verify/  → second-factor step of the login flow (only reached when
                                  a confirmed device exists OR the user's role is in
                                  MFA_REQUIRED_ROLES).

    Security notes:
      * secret is a pyotp base32 string — never logged or serialised in list endpoints.
      * backup_codes stores SHA-256 hashes (via make_password) of single-use codes;
        plaintext codes are returned only at confirm time and never stored.
      * confirmed=False devices do NOT trigger the MFA login gate; only confirmed ones do.
    """

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="totp_device",
    )
    # pyotp.random_base32() secret — base32, never stored in logs.
    secret = models.CharField(max_length=64)
    # False until the user completes the confirm step by verifying a live TOTP code.
    confirmed = models.BooleanField(default=False)
    # JSON list of make_password()-hashed single-use backup codes.
    # Never store plaintext codes here — plaintext is returned ONCE at confirm time only.
    backup_codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set only after a successful confirm.
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "User TOTP device"

    def __str__(self) -> str:
        state = "confirmed" if self.confirmed else "pending"
        return f"TOTPDevice({self.user_id}, {state})"

    # ── Backup code helpers ────────────────────────────────────────────────────

    @staticmethod
    def _hash_backup_code(plaintext: str) -> str:
        """Hash a plaintext backup code for storage (make_password uses PBKDF2)."""
        return make_password(plaintext)

    def verify_backup_code(self, plaintext: str) -> bool:
        """Return True and REMOVE the matched hash if plaintext matches any stored hash.

        Single-use: the matching hash is deleted on success so the code can never
        be replayed.  The instance is saved in-place; callers must not re-save.
        """
        for i, stored_hash in enumerate(list(self.backup_codes)):
            if check_password(plaintext, stored_hash):
                new_codes = list(self.backup_codes)
                new_codes.pop(i)
                self.backup_codes = new_codes
                self.save(update_fields=["backup_codes"])
                return True
        return False


class CustomerNotification(models.Model):
    """Persistent, customer-facing in-app notification (the inbox / notification center).

    Lives in the PUBLIC schema so it can be written from any tenant ``schema_context``
    AND from platform-level (ride/courier/wallet) dispatch — exactly like
    ``CustomerPushSubscription`` and ``NotificationLog``. This MIRRORS the existing
    fire-and-forget Web Push events (same title/body/url) so a missed/denied/backgrounded
    push is no longer lost forever: the inbox is the durable source of truth and push is
    just one delivery channel (the Careem/Grab pattern).

    Distinct from ``NotificationLog`` — that is a server-side AUDIT table (delivery
    outcome, subscriber counts); this is the CUSTOMER-FACING feed they read in the app.

    Loose ``customer_id`` (no FK constraint) for cross-schema safety with django-tenants,
    matching the convention used by ``WinbackNudge`` / ``NotificationLog``.
    """

    # Coarse cross-vertical grouping for icon/colour + per-vertical filtering later.
    class Vertical(models.TextChoices):
        FOOD = "food", "Food"
        SHOPS = "shops", "Shops"
        PHARMACY = "pharmacy", "Pharmacy"
        RIDE = "ride", "Ride"
        COURIER = "courier", "Courier"
        WALLET = "wallet", "Wallet"
        GENERAL = "general", "General"

    customer_id = models.BigIntegerField(
        db_index=True,
        help_text="FK to accounts.Customer (loose — no FK constraint for cross-schema safety).",
    )
    # Machine event key mirroring the push event (e.g. delivery.delivered, ride.accepted,
    # review_prompt, charge_request) — useful for client-side icon mapping / dedupe.
    type = models.CharField(max_length=40, blank=True, db_index=True)
    vertical = models.CharField(
        max_length=12, choices=Vertical.choices, default=Vertical.GENERAL, db_index=True
    )
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=400, blank=True)
    # In-app deep link (relative path) the row navigates to on tap, e.g. /orders/ORD-1.
    url = models.CharField(max_length=300, blank=True)
    # Null until the customer reads it; powers the unread badge + mark-read.
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            # Inbox list + unread-count are always scoped to one customer, newest-first.
            models.Index(fields=("customer_id", "created_at"), name="custnotif_cust_created"),
            models.Index(fields=("customer_id", "read_at"), name="custnotif_cust_read"),
        ]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def __str__(self) -> str:
        state = "read" if self.read_at else "unread"
        return f"CustomerNotification(cust={self.customer_id}, {self.type}, {state})"
