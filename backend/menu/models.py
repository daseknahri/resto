from django.db import models


class SuperCategory(models.Model):
    name = models.CharField(max_length=150)
    name_i18n = models.JSONField(default=dict, blank=True)
    slug = models.SlugField(max_length=160, unique=True)
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
    is_published = models.BooleanField(default=True)
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
    currency = models.CharField(max_length=8, default="USD")
    owner_note = models.TextField(blank=True)
    estimated_ready_minutes = models.PositiveIntegerField(null=True, blank=True)
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
