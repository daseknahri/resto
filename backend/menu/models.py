from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
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
    slug = models.SlugField(max_length=210, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    image_url = models.URLField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class DishOption(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=150)
    price_delta = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    is_required = models.BooleanField(default=False)
    max_select = models.PositiveIntegerField(default=1)

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
