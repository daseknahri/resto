from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SuperCategory(models.Model):
    name = models.CharField(max_length=150)
    name_i18n = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.CharField(
        max_length=280,
        blank=True,
        help_text="Short tagline shown on the menu-selector card (e.g. 'Served 11 am – 3 pm').",
    )
    description_i18n = models.JSONField(default=dict, blank=True)
    image_url = models.URLField(
        blank=True,
        help_text="Cover image displayed on the menu-selector card.",
    )
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    is_temporarily_disabled = models.BooleanField(default=False)
    disabled_note = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    super_category = models.ForeignKey(
        SuperCategory,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=150)
    name_i18n = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    description_i18n = models.JSONField(default=dict, blank=True)
    image_url = models.URLField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class Dish(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="dishes")
    name = models.CharField(max_length=200)
    name_i18n = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=210, unique=True)
    description = models.TextField(blank=True)
    description_i18n = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    image_url = models.URLField(blank=True)
    position = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    allergens = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allergen keys present in this dish (e.g. ['gluten', 'eggs']).",
    )
    is_published = models.BooleanField(default=True)
    is_available = models.BooleanField(
        default=True,
        help_text=(
            "Temporary daily availability. False = sold out (still visible on menu "
            "but cannot be ordered). Use is_published=False to permanently hide the dish."
        ),
    )
    stock_qty = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text=(
            "Remaining stock count. null = unlimited. When an order is placed, "
            "the qty is decremented atomically. Reaching 0 automatically sets "
            "is_available=False so the dish shows as sold-out on the menu."
        ),
    )
    availability_schedule = models.JSONField(
        default=None,
        null=True,
        blank=True,
        help_text=(
            "Optional time-based availability window. "
            "Schema: {days: ['mon','tue',...], time_start: 'HH:MM', time_end: 'HH:MM'}. "
            "null = always available. Empty days list = any day."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class OptionGroup(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="option_groups")
    name = models.CharField(max_length=150)
    name_i18n = models.JSONField(default=dict, blank=True)
    min_select = models.PositiveIntegerField(default=1)
    max_select = models.PositiveIntegerField(default=1)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return f"{self.dish.name} / {self.name}"


class DishOption(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="options")
    group = models.ForeignKey(
        OptionGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="options",
    )
    name = models.CharField(max_length=150)
    name_i18n = models.JSONField(default=dict, blank=True)
    price_delta = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    is_required = models.BooleanField(default=False)
    max_select = models.PositiveIntegerField(default=1)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return f"{self.name} (+{self.price_delta})"


class TableLink(models.Model):
    label = models.CharField(max_length=40)
    slug = models.SlugField(max_length=55, unique=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "label", "id")

    def __str__(self) -> str:
        return self.label


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class FulfillmentType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        DELIVERY = "delivery", "Delivery"
        TABLE = "table", "Table"

    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    # Platform-level customer link — null for anonymous orders, populated when the customer
    # has a platform account. Anonymous fields below are retained for backward compatibility.
    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name = models.CharField(max_length=80, blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)
    customer_note = models.TextField(blank=True)
    fulfillment_type = models.CharField(max_length=20, choices=FulfillmentType.choices, blank=True)
    table_label = models.CharField(max_length=40, blank=True)
    table_slug = models.SlugField(max_length=55, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_location_url = models.URLField(max_length=500, blank=True)
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Delivery fee snapshot captured at order placement time.",
    )
    currency = models.CharField(max_length=8, default="USD")
    wallet_amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount deducted from the customer's wallet at order placement.",
    )
    # Order source — 'direct' (QR/subdomain), 'marketplace' (platform unified checkout)
    class Source(models.TextChoices):
        DIRECT = "direct", "Direct"
        MARKETPLACE = "marketplace", "Marketplace"

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.DIRECT,
        db_index=True,
        help_text="Whether this order originated from a direct QR/menu visit or the platform marketplace.",
    )
    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Platform commission for marketplace orders (10% of food subtotal).",
    )
    promotion_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Discount amount applied by a promotion at order placement time.",
    )
    applied_promotion_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Snapshot of the promotion name that was applied to this order.",
    )
    owner_note = models.TextField(blank=True)
    estimated_ready_minutes = models.PositiveIntegerField(null=True, blank=True)
    tip_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Optional gratuity added by the customer at checkout.",
    )
    points_earned = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Loyalty points credited to the customer for this order. Null = loyalty not active at placement time.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    status_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.order_number} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish_slug = models.SlugField(max_length=210)
    dish_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=120, blank=True)
    options = models.JSONField(default=list, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.qty}x {self.dish_name}"


class AnalyticsEvent(models.Model):
    event_type = models.CharField(max_length=48, db_index=True)
    path = models.CharField(max_length=320, blank=True)
    category_slug = models.SlugField(max_length=160, blank=True)
    dish_slug = models.SlugField(max_length=210, blank=True)
    source = models.CharField(max_length=48, blank=True)
    session_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("event_type", "created_at")),
            models.Index(fields=("category_slug", "created_at")),
            models.Index(fields=("dish_slug", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


class ClosureDate(models.Model):
    """
    A specific calendar date on which the restaurant is closed.
    Any date listed here will cause get_is_open_now (in tenancy/serializers.py)
    to return False regardless of the weekly business-hours schedule.
    """

    date = models.DateField(
        unique=True,
        db_index=True,
        help_text="The calendar date on which the restaurant is closed (YYYY-MM-DD).",
    )
    label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional reason / holiday name shown to the owner (e.g. 'Christmas Day').",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("date",)

    def __str__(self) -> str:
        suffix = f" — {self.label}" if self.label else ""
        return f"Closure {self.date}{suffix}"


class Rating(models.Model):
    """
    Customer rating for a completed order — tenant-scoped (stored per restaurant schema).

    One rating per order, enforced by the OneToOneField.  Score is 1–5.
    Comment is optional.  No auth required — any caller who knows the order
    number and the order is completed can post a rating.
    """

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="rating",
    )
    # Platform-level customer link — populated when the customer has an account.
    # Enables per-customer rating history without exposing anonymous ratings.
    customer = models.ForeignKey(
        "accounts.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restaurant_ratings",
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Rating {self.score}/5 for {self.order.order_number}"


class WaitlistEntry(models.Model):
    """
    Customer waitlist entry for a fully-booked time slot.
    Tenant-scoped — stored per restaurant schema.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        NOTIFIED = "notified", "Notified"
        CONVERTED = "converted", "Converted"
        EXPIRED = "expired", "Expired"

    booked_for = models.DateTimeField(
        help_text="The desired date/time slot the customer is waiting for.",
        db_index=True,
    )
    party_size = models.PositiveSmallIntegerField(default=1)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True,
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Waitlist: {self.name} for {self.booked_for} (party of {self.party_size})"


class Promotion(models.Model):
    """
    Restaurant-level promotion (discount applied automatically at checkout).

    Promotions are tenant-scoped. The best (highest discount) currently-active
    promotion is applied when a customer places an order. The discount amount is
    snapshotted on the Order and the use_count is incremented atomically inside
    the order-placement transaction.

    Types:
      - percentage   → discount_value % off the food subtotal
      - fixed        → discount_value fixed amount off the food subtotal
      - free_delivery → waive the delivery fee entirely
    """

    class Type(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage off"
        FIXED = "fixed", "Fixed amount off"
        FREE_DELIVERY = "free_delivery", "Free delivery"

    name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)
    promo_type = models.CharField(max_length=20, choices=Type.choices, default=Type.PERCENTAGE)
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Percentage (0–100) for percentage type; fixed amount for fixed type. Ignored for free_delivery.",
    )
    min_order_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Minimum food subtotal required to apply this promotion.",
    )
    days = models.JSONField(
        default=list,
        blank=True,
        help_text="Days active: ['mon','tue',...]. Empty list = every day.",
    )
    time_start = models.CharField(
        max_length=5,
        blank=True,
        help_text="HH:MM — start of active time window. Blank = all day.",
    )
    time_end = models.CharField(
        max_length=5,
        blank=True,
        help_text="HH:MM — end of active time window. Blank = all day.",
    )
    active_from = models.DateField(
        null=True,
        blank=True,
        help_text="Start date (inclusive). Null = no start boundary.",
    )
    active_until = models.DateField(
        null=True,
        blank=True,
        help_text="End date (inclusive). Null = no end boundary.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of orders this promotion applies to. Null = unlimited.",
    )
    use_count = models.PositiveIntegerField(default=0)
    code = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
        help_text=(
            "Optional customer-redeemable code (e.g. WELCOME10). "
            "When set, the promotion is NOT applied automatically — the customer must enter it at checkout. "
            "Leave blank for auto-applied promotions."
        ),
    )
    is_platform_flash = models.BooleanField(
        default=False,
        help_text="True if created by the platform as a flash sale campaign.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.promo_type})"


class PushSubscription(models.Model):
    """
    Browser Web Push subscription for a tenant owner/staff member.
    Stored in the tenant schema so each restaurant's subscriptions are isolated.
    Subscriptions are registered from the owner dashboard and used to send
    native OS notifications when a new order arrives, even when the tab is closed.
    """

    # Loose integer reference to accounts.User — avoids cross-app FK at model level.
    user_id = models.IntegerField(db_index=True, help_text="accounts.User pk")
    # W3C Push API subscription fields
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField(help_text="Client public key (URL-safe base64)")
    auth = models.CharField(max_length=200, help_text="Auth secret (URL-safe base64)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"PushSubscription user={self.user_id} {self.endpoint[:60]}"


class LoyaltyConfig(models.Model):
    """
    Per-tenant loyalty programme configuration.
    Only one row should exist per tenant schema (enforced in the view layer).
    """

    enabled = models.BooleanField(
        default=False,
        help_text="Whether the loyalty programme is active for this restaurant.",
    )
    points_per_unit = models.PositiveIntegerField(
        default=10,
        help_text="Loyalty points earned per 1 unit of currency spent (e.g. 10 = 10 pts per $1).",
    )
    redeem_threshold = models.PositiveIntegerField(
        default=100,
        help_text="Minimum points balance required before a customer can redeem.",
    )
    points_value = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default="0.0100",
        help_text="Currency value of one loyalty point (e.g. 0.01 = 1 pt is worth $0.01).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Loyalty Config"

    def __str__(self) -> str:
        return f"LoyaltyConfig (enabled={self.enabled}, {self.points_per_unit}pts/unit)"


class CurrencyRate(models.Model):
    """
    Platform-wide exchange rates anchored to MAD (Moroccan Dirham).

    mad_per_unit: how many MAD equal 1 unit of this currency.
      e.g.  EUR → 10.90  means 1 EUR = 10.90 MAD
            MAD →  1.00  (always 1, the base currency)

    To convert a MAD price to display currency:
        display_price = mad_price / mad_per_unit

    Updated daily via the `fetch_currency_rates` management command,
    or manually through the Django admin.
    """

    code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 code, e.g. EUR")
    name = models.CharField(max_length=60)
    symbol = models.CharField(max_length=10, help_text="Display symbol, e.g. €")
    mad_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        help_text="How many MAD equal 1 unit of this currency (1 for MAD itself).",
    )
    is_active = models.BooleanField(default=True, help_text="Shown to customers when active.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Currency Rate"
        verbose_name_plural = "Currency Rates"

    def __str__(self) -> str:
        return f"{self.code} — 1 {self.code} = {self.mad_per_unit} MAD"
