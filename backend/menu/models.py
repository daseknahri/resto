from decimal import Decimal

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
    is_temporarily_disabled = models.BooleanField(
        default=False,
        help_text=(
            "Temporarily hide this category and all its dishes from the customer menu "
            "without permanently unpublishing it — useful for mid-service pauses "
            "(e.g. a section is sold out for the evening). Set back to False to restore."
        ),
    )
    course = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Course number for dine-in sequencing (0 = no course / fire immediately; "
            "1–4 = starter → main → cheese → dessert). Dishes inherit this at order time."
        ),
    )
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
    currency = models.CharField(max_length=8, default="MAD")
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
    low_stock_threshold = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            "Stock level at or below which this dish appears in the low-stock alert list. "
            "Defaults to 3. Ignored when stock_qty is null (unlimited)."
        ),
    )
    cost_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text=(
            "Operator-set cost / COGS per unit. Optional. Used to compute food-cost% "
            "on the owner dashboard. Leave blank for items whose cost is not tracked."
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
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Retail product attributes (sku, barcode, brand, unit). "
            "Empty for restaurant dishes. Kepoli Phase 1 seam — see KEPOLI_ARCHITECTURE.md."
        ),
    )
    stock_auto_zeroed = models.BooleanField(
        default=False,
        help_text=(
            "Set to True when the automatic checkout stock decrement drives stock_qty to 0. "
            "Cleared when stock becomes positive again (restock/void/cancel) or when the "
            "owner explicitly writes stock_qty via the Inventory API. "
            "The 5 AM auto_reset_availability cron only re-enables dishes where this is "
            "True, avoiding unwanted re-enabling of intentionally zeroed dishes."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class ComboComponent(models.Model):
    """A fixed component of a combo dish.

    A combo IS a Dish (price, category, image, stock_qty, i18n names all inherited)
    that has one or more fixed component dishes (e.g. a burger + fries + drink combo).
    "Choose your drink" style choices use the EXISTING OptionGroup/DishOption mechanism
    on the combo dish itself — no per-component choice modelling is needed here.

    Constraints:
    - A component may NOT itself have combo_components (no nesting). Validated in the
      serializer's validate_combo_components; the DB on_delete=PROTECT on the component FK
      surfaces as a clear 409 "dish is part of combo X" if you try to delete a component dish.
    - Max 8 components per combo (validated in DishSerializer).
    """

    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="combo_components",
        help_text="The combo dish that owns this component.",
    )
    component = models.ForeignKey(
        Dish,
        on_delete=models.PROTECT,
        related_name="part_of_combos",
        help_text="The component dish included in this combo.",
    )
    qty = models.PositiveSmallIntegerField(
        default=1,
        help_text="How many units of this component are included per combo ordered.",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        unique_together = ("dish", "component")

    def __str__(self) -> str:
        return f"{self.dish.name} → {self.component.name} ×{self.qty}"


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


class TableSection(models.Model):
    """A floor zone grouping tables (e.g. 'Terrace', 'Main hall').

    Waiters are assigned to sections (via SectionServer); a dine-in order for a
    table in a section is routed to that section's servers. Tenant-scoped.
    """

    name = models.CharField(max_length=60)
    color = models.CharField(
        max_length=9,
        blank=True,
        help_text="Optional hex colour for the floor UI, e.g. #f59e0b.",
    )
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name", "id")

    def __str__(self) -> str:
        return self.name


class TableLink(models.Model):
    label = models.CharField(max_length=40)
    slug = models.SlugField(max_length=55, unique=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # Floor section this table belongs to — drives which waiter sees its orders.
    section = models.ForeignKey(
        "menu.TableSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tables",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "label", "id")

    def __str__(self) -> str:
        return self.label


class SectionServer(models.Model):
    """Assignment of a staff member (waiter) to a floor section.

    ``user_id`` is a loose reference to accounts.User (public schema), matching
    Order.handled_by_user_id — avoids a tenant→public cross-app FK.
    """

    section = models.ForeignKey(
        "menu.TableSection",
        on_delete=models.CASCADE,
        related_name="servers",
    )
    user_id = models.IntegerField(
        db_index=True,
        help_text="accounts.User pk of the assigned waiter.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("section", "user_id")


class WaiterCall(models.Model):
    """A dine-in customer's request for staff attention, raised from a table QR.

    Lives in the tenant schema (one restaurant's calls never mix with another's).
    Broadcast in real time to the owner/staff WebSocket group on create, and again
    on acknowledge so every staff device clears it together.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"

    table_label = models.CharField(max_length=40, blank=True)
    table_slug = models.SlugField(max_length=55, blank=True)
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional reason chosen by the customer (e.g. 'Bill', 'Water').",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"WaiterCall({self.table_label or self.table_slug}, {self.status})"


class StaffMessage(models.Model):
    """A message on the restaurant's shared internal staff channel (owner + staff).

    Tenant-scoped, persisted for history, and broadcast in real time to the
    owner/staff WebSocket group so every device sees it instantly.
    """

    author = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    author_name = models.CharField(max_length=80, blank=True)
    body = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"StaffMessage({self.author_name}: {self.body[:30]})"


class Order(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"  # advance order, not yet released to the kitchen
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"  # delivery only
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class FulfillmentType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        DELIVERY = "delivery", "Delivery"
        TABLE = "table", "Table"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"

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
    # Last 9 digits of customer_phone, stored for btree-indexed exact-match search.
    # Auto-maintained by the pre_save signal in menu/signals.py.
    customer_phone_digits = models.CharField(max_length=9, blank=True, default="")
    customer_note = models.TextField(blank=True)
    fulfillment_type = models.CharField(max_length=20, choices=FulfillmentType.choices, blank=True)
    table_label = models.CharField(max_length=40, blank=True)
    table_slug = models.SlugField(max_length=55, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_location_url = models.URLField(max_length=500, blank=True)
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)
    # Proof of delivery — a short code generated for delivery orders. The customer shows
    # it to the driver, who must enter it to mark the delivery complete. Optional photo URL.
    delivery_code = models.CharField(max_length=12, blank=True, db_index=True)
    delivery_proof_photo_url = models.URLField(max_length=500, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Delivery fee snapshot captured at order placement time.",
    )
    currency = models.CharField(max_length=8, default="MAD")
    wallet_amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Amount deducted from the customer's wallet at order placement.",
    )
    # Payment state — deliberately distinct from the kitchen `status`. Pickup &
    # delivery are expected to pay up front (wallet at placement, or staff marks
    # cash collected); dine-in (table) runs as an open tab that is settled when
    # the customer leaves. UNPAID until fully covered.
    payment_status = models.CharField(
        max_length=12,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order's bill was fully settled (paid).",
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
        help_text="Platform commission for marketplace orders (rate × food subtotal).",
    )
    # Snapshot of the marketplace commission RATE (a fraction, 0.10 = 10%) that
    # was applied when this order was placed — copied from the tenant's
    # Profile.marketplace_commission_pct at creation. Persisting the rate means a
    # historical order can be re-audited even after the tenant's rate later
    # changes. Default 0 (non-marketplace orders carry no commission).
    commission_rate_applied = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Snapshot of the commission rate applied (fraction, 0.10 = 10%).",
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
    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "When the customer wants this advance order fulfilled (null = ASAP). "
            "While set and status=SCHEDULED the order is hidden from the kitchen until "
            "the release sweep moves it to PENDING shortly before this time."
        ),
    )
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
    loyalty_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Discount applied by redeeming loyalty points at checkout.",
    )
    redeemed_loyalty_points = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Loyalty points spent on this order's checkout discount. Null = none redeemed.",
    )
    # Loose reference to accounts.User (public schema) — the staff member / owner who
    # last advanced this order's status. Powers per-staff work stats and the waiter's
    # own shift view. Loose IntegerField (not FK) to avoid a tenant→public cross-app FK,
    # matching PushSubscription.user_id.
    handled_by_user_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="accounts.User pk of the staff/owner who last advanced this order.",
    )
    fired_course = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "Highest course number that has been fired (sent to kitchen). "
            "Items with course <= fired_course are considered fired; items with course > fired_course "
            "are held. Course 0 items are always fired immediately. "
            "Default 1 means course-1 items fire on placement."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    status_updated_at = models.DateTimeField(null=True, blank=True)
    # Set when the post-meal review push has been sent, so the scheduled command
    # that nudges customers ~30 min after completion never double-sends.
    review_prompt_sent_at = models.DateTimeField(null=True, blank=True)
    # OPS-3: client-minted idempotency key for order placement. Allows the SPA
    # to safely retry a timed-out POST without creating a duplicate kitchen ticket.
    # Nullable so legacy orders (no key supplied) are unconstrained; when present
    # the conditional unique constraint below guarantees at-most-one order per key
    # within this tenant schema.
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Client-minted UUIDv4 sent at placement time; used for retry-safe dedup.",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            # Staff "?since=" delta-poll filters status + orders by updated_at (~300 req/min);
            # without this it scans all active rows every tick.
            models.Index(fields=("status", "updated_at")),
            # OPS-4 C: customer_phone used in CRM GROUP BY, win-back, return-rate, search
            # (4 scan paths). A plain db_index on the field alone conflicts with the field
            # definition, so it is expressed as a Meta index instead.
            models.Index(fields=("customer_phone",), name="order_customer_phone_idx"),
            # Indexed suffix-digits for exact-match phone search (btree-friendly).
            # customer_phone btree is useless for LIKE '%..%'; this column stores the
            # last 9 digits so searches hit a btree exact-match instead.
            models.Index(fields=("customer_phone_digits",), name="order_phone_digits_idx"),
            # OPS-4 C: Z-report / digest paid_at range queries filter on (status, paid_at).
            models.Index(fields=("status", "paid_at"), name="order_status_paid_at_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="uniq_order_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_number} ({self.status})"

    @property
    def requires_prepayment(self) -> bool:
        """Pickup & delivery are pay-now; table (dine-in) is an open tab paid at the end."""
        return self.fulfillment_type in (
            self.FulfillmentType.PICKUP,
            self.FulfillmentType.DELIVERY,
        )

    @property
    def is_paid(self) -> bool:
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def is_scheduled(self) -> bool:
        """True for an advance order still waiting for its release time."""
        return self.status == self.Status.SCHEDULED

    def mark_paid(self, *, save: bool = True):
        """Settle the order's bill. Idempotent."""
        from django.utils import timezone as _tz
        if self.payment_status != self.PaymentStatus.PAID:
            self.payment_status = self.PaymentStatus.PAID
            self.paid_at = _tz.now()
            if save:
                self.save(update_fields=["payment_status", "paid_at", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    dish_slug = models.SlugField(max_length=210)
    dish_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    qty = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=120, blank=True)
    options = models.JSONField(default=list, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Per-item kitchen readiness — lets the kitchen tick off individual items on a
    # multi-item ticket instead of an all-or-nothing order status.
    is_ready = models.BooleanField(default=False)
    ready_at = models.DateTimeField(null=True, blank=True)
    # Dine-in item voiding — a waiter can remove a line item from an open tab
    # (e.g. customer changes mind) without cancelling the whole order.
    is_voided = models.BooleanField(default=False)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=120, blank=True)
    voided_by_user_id = models.IntegerField(null=True, blank=True)
    # Course sequencing — snapshot of dish.category.course at placement/append time.
    # 0 = no course / fire immediately; 1–4 = course number held until staff fires it.
    course = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Course snapshot captured at order placement. 0 = fire immediately; "
            "1–4 = held until Order.fired_course reaches this value."
        ),
    )
    # Combo snapshot — when the ordered dish is a combo, this captures the fixed
    # components at placement time so receipt/kitchen views can render sub-lines
    # even if the combo definition changes later. Empty list for non-combo dishes.
    # Schema: [{dish_id, name, qty}] where qty is the per-unit component qty
    # (not pre-multiplied by item.qty — restock math multiplies by item.qty).
    combo_components = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Placement snapshot of combo components. "
            "Each entry: {dish_id, name, qty} where qty is per-unit (×item.qty to get total). "
            "Empty for non-combo dishes."
        ),
    )

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(
                condition=models.Q(is_voided=True),
                fields=["voided_at"],
                name="menu_orderitem_voided_at_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.qty}x {self.dish_name}"


class OrderPayment(models.Model):
    """Individual payment instalment toward an Order (split-bill / partial settle).

    A single order can carry multiple OrderPayment rows — one per cash or wallet
    instalment.  The authoritative paid total is sum(payments.amount); the legacy
    order.wallet_amount_paid field is kept in sync for wallet payments so that
    daily-digest queries and dashboards that read that column continue to work.

    Note: the one-shot settle endpoints (StaffSettleView, WalletSettleView, etc.)
    do NOT write ledger rows — they simply flip order.payment_status to PAID and
    (for wallet) increment wallet_amount_paid.  For those orders amount_paid
    derives from wallet_amount_paid alone and the payments list is empty.  The
    split-bill endpoint (StaffOrderPaymentView) always writes a row here AND
    keeps wallet_amount_paid consistent, so both read paths remain accurate.
    """

    class Method(models.TextChoices):
        WALLET = "wallet", "Wallet"
        CASH = "cash", "Cash"

    order = models.ForeignKey(
        "Order", on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=8, choices=Method.choices)
    recorded_by_user_id = models.IntegerField(null=True, blank=True)
    recorded_by_name = models.CharField(max_length=80, blank=True)
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # OPS-3 contract D: client idempotency key for the DB-level replay backstop.
    # When present, a UniqueConstraint guarantees that the same key cannot produce
    # two OrderPayment rows even if the Redis cache is down and the short-circuit
    # check misses. The endpoint catches IntegrityError on a duplicate and returns
    # the existing row instead of failing or double-charging.
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Client-minted key; uniqueness enforced by DB constraint when non-null.",
    )

    # ── Payment-method correction audit trail (OPS-2 contract D) ──────────────
    # A staff member may have recorded the wrong tender type (cash vs wallet).
    # These fields allow relabelling without touching the wallet ledger.
    # Boundary: changing `method` here only affects the Z-report cash/wallet split
    # and the owner order-detail view. It does NOT move money: the WalletTransaction
    # and Customer.wallet_balance are NEVER updated by a correction.
    original_method = models.CharField(
        max_length=8,
        blank=True,
        help_text=(
            "The method value before the first correction. "
            "Blank = this payment has never been corrected."
        ),
    )
    corrected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the method was last corrected.",
    )
    corrected_by_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Display name of the staff member who corrected the method.",
    )

    class Meta:
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="uniq_orderpayment_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.amount} for order {self.order_id}"


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


class Campaign(models.Model):
    """Owner broadcast push campaign to past customers of this tenant.

    ``created_by_user_id`` is a bare integer reference to the public-schema
    accounts.User — no cross-schema FK. audience_count is set at creation;
    sent_count is updated best-effort after dispatch (fire-and-forget).
    """

    title = models.CharField(max_length=80)
    message = models.CharField(max_length=200)
    created_by_user_id = models.IntegerField(null=True)
    audience_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Campaign({self.title!r}, {self.created_at:%Y-%m-%d})"


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

    # Owner reply — the restaurant can post a public response visible to the customer.
    owner_reply = models.TextField(blank=True, default="")
    owner_reply_at = models.DateTimeField(null=True, blank=True)

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


class HappyHour(models.Model):
    """Time-based pricing rule: discount *percent_off* % from dish.price during the window.

    Semantics (enforced in menu/pricing.py):
    - percent_off applies to dish.price ONLY; option price_delta is never discounted.
    - When several active rules match a dish, the LARGEST percent_off wins.
    - Empty categories M2M = rule covers ALL categories.
    - Overnight windows: start_time > end_time → wraps midnight.
    - Time source = tenant-local wall-clock (_profile_now in menu/views.py).
    - Max 8 rows per tenant (validated in HappyHourSerializer on create).
    """

    name = models.CharField(max_length=80)
    days = models.JSONField(
        default=list,
        help_text="List of weekday ints — 0=Monday … 6=Sunday (Python weekday() convention).",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    percent_off = models.PositiveSmallIntegerField(
        help_text="Percentage discount applied to dish.price (1–90).",
    )
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="happy_hours",
        help_text="Restrict rule to these categories. Empty = all categories.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"HappyHour({self.name!r}, -{self.percent_off}%)"


class CustomerNote(models.Model):
    """Private, per-tenant note about a customer.

    Lives in the tenant schema so it is never shared across restaurants.
    ``customer_id`` is a bare integer reference to the public-schema
    ``accounts.Customer.id`` (no FK constraint across schemas).

    At most one row per customer per tenant (enforced by unique_together).
    """

    customer_id = models.IntegerField(
        db_index=True,
        help_text="Refers to accounts.Customer.id (public schema) — no DB-level FK.",
    )
    notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("customer_id",)]
        ordering = ["-updated_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"CustomerNote customer_id={self.customer_id}"
