from django.contrib import admin

from .models import AnalyticsEvent, Category, Dish, DishOption, TableLink


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "is_published")
    list_filter = ("is_published",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("position", "name")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "currency", "is_published")
    list_filter = ("category", "is_published")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category", "position")


@admin.register(DishOption)
class DishOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "dish", "price_delta", "is_required", "max_select")
    list_filter = ("is_required",)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "category_slug", "dish_slug", "source", "created_at")
    list_filter = ("event_type", "source", "created_at")
    search_fields = ("path", "category_slug", "dish_slug", "session_id")
    ordering = ("-created_at",)
    readonly_fields = (
        "event_type",
        "path",
        "category_slug",
        "dish_slug",
        "source",
        "session_id",
        "metadata",
        "created_at",
    )


@admin.register(TableLink)
class TableLinkAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "position", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("label", "slug")
    ordering = ("position", "label", "id")
