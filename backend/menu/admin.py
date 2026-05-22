from django.contrib import admin
from django.contrib import messages

from .models import AnalyticsEvent, Category, ClosureDate, CurrencyRate, Dish, DishOption, OptionGroup, SuperCategory, TableLink, WaitlistEntry


@admin.register(SuperCategory)
class SuperCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "is_published", "is_temporarily_disabled")
    list_filter = ("is_published", "is_temporarily_disabled")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("position", "name")
    fields = (
        "name", "name_i18n", "slug",
        "description", "description_i18n", "image_url",
        "position", "is_published", "is_temporarily_disabled", "disabled_note",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "super_category", "slug", "position", "is_published")
    list_filter = ("super_category", "is_published")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("super_category", "position", "name")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "currency", "is_published")
    list_filter = ("category", "is_published")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("category", "position")


class DishOptionInline(admin.TabularInline):
    model = DishOption
    extra = 1
    fields = ("name", "price_delta", "position", "is_required", "max_select")


@admin.register(OptionGroup)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "dish", "min_select", "max_select", "position")
    list_filter = ("dish__category",)
    inlines = [DishOptionInline]


@admin.register(DishOption)
class DishOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "dish", "group", "price_delta", "is_required", "max_select", "position")
    list_filter = ("is_required", "group")


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


@admin.register(ClosureDate)
class ClosureDateAdmin(admin.ModelAdmin):
    list_display = ("date", "label", "created_at")
    search_fields = ("label",)
    ordering = ("date",)


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "booked_for", "party_size", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "phone", "email")
    readonly_fields = ("created_at",)
    ordering = ("booked_for", "created_at")


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "mad_per_unit", "is_active", "updated_at")
    list_editable = ("mad_per_unit", "is_active")
    readonly_fields = ("updated_at",)
    ordering = ("code",)
    actions = ["fetch_latest_rates"]

    @admin.action(description="⟳ Fetch latest rates from Frankfurter API")
    def fetch_latest_rates(self, request, queryset):
        """Trigger the fetch_currency_rates management command inline from the admin."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        try:
            call_command("fetch_currency_rates", stdout=out, stderr=out)
            self.message_user(request, out.getvalue().strip(), messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Fetch failed: {exc}", messages.ERROR)
