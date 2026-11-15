from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from sales.audit import log_admin_action
from sales.models import AdminAuditLog

from .models import (
    Customer,
    PasswordResetToken,
    PlatformConfig,
    PlatformFlashSale,
    RideRequest,
    User,
    WalletTransaction,
    WalletVoucher,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Roles", {"fields": ("role", "tenant")}),
    )
    list_display = ("username", "email", "role", "tenant", "is_active")
    list_filter = ("role", "is_active")
    # A-43: no search_fields meant finding a user required paging.
    search_fields = ("username", "email")

    def save_model(self, request, obj, form, change):
        previous_role = None
        if change:
            previous_role = User.objects.filter(pk=obj.pk).values_list("role", flat=True).first()
        super().save_model(request, obj, form, change)
        if previous_role and previous_role != obj.role:
            log_admin_action(
                action=AdminAuditLog.Actions.USER_ROLE_CHANGED,
                request=request,
                actor=request.user,
                tenant=obj.tenant,
                target_repr=f"user:{obj.id}",
                metadata={
                    "username": obj.username,
                    "previous_role": previous_role,
                    "new_role": obj.role,
                },
            )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    # A-36: raw reset tokens are bearer secrets — they must not appear in the
    # list view or be searchable. Same pattern as ActivationTokenAdmin
    # (sales/admin.py): token omitted from list_display, readonly in the form.
    list_display = ("user", "expires_at", "used_at", "created_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("used_at",)
    readonly_fields = ("token",)


class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    readonly_fields = ("type", "amount", "reference", "tenant_id", "note", "created_at")
    can_delete = False
    ordering = ("-created_at",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("phone", "name", "email", "wallet_balance", "locale", "created_at")
    search_fields = ("phone", "name", "email")
    list_filter = ("locale", "created_at")
    # A-35: wallet_balance is ledger money — hand-editing it bypasses the
    # wallet service, idempotency keys, WalletTransaction rows and audit
    # logging. Balances change only via the bonus/fund flows.
    readonly_fields = ("wallet_balance", "created_at", "updated_at")
    ordering = ("-created_at",)
    inlines = [WalletTransactionInline]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("customer", "type", "amount", "reference", "tenant_id", "created_at")
    search_fields = ("customer__phone", "customer__name", "reference")
    list_filter = ("type", "created_at")
    # A-34: the wallet ledger is append-only. Every money field is readonly
    # so a staff admin cannot rewrite a transaction's amount after the fact;
    # rows are created by the wallet service, never by the admin form, and
    # never deleted from the panel.
    readonly_fields = (
        "customer",
        "type",
        "amount",
        "reference",
        "tenant_id",
        "note",
        "idempotency_key",
        "balance_after",
        "currency",
        "vertical",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# A-42: Django-admin registrations for the key platform models, so the admin
# is a fallback ops surface when the Vue console is down. Money rows are
# read-first: created by the app flows, never fabricated or deleted here.
@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    # Guarded edit (not readonly): fares/threshold are the values a platform
    # admin tunes live. The row is a singleton (save() forces pk=1), so the
    # admin can never delete it and can only add one when none exists.
    list_display = (
        "wallet_charge_approval_threshold",
        "ride_base_fare",
        "ride_per_km",
        "ride_minimum_fare",
        "ride_commission_pct",
        "ride_per_minute",
        "updated_at",
    )
    readonly_fields = ("updated_at",)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return not PlatformConfig.objects.exists()


@admin.register(PlatformFlashSale)
class PlatformFlashSaleAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_value", "active_from", "active_until", "is_active", "redemption_count")
    list_filter = ("is_active", "active_from")
    search_fields = ("name",)
    # redemption_count is a live counter owned by the redemption flow.
    readonly_fields = ("redemption_count", "created_at")


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    # Read-first: fare/status are lifecycle money — changed only via the ride
    # endpoints (incl. force-resolve), never by hand in the panel. The
    # delivery code and recipient tracking token are secrets and never shown.
    list_display = ("id", "kind", "rider", "driver", "status", "fare", "payment_method", "created_at")
    list_filter = ("kind", "status", "payment_method", "created_at")
    search_fields = ("rider__phone", "rider__name", "driver__phone", "pickup_address", "dropoff_address")
    ordering = ("-created_at",)
    # The handover code and recipient tracking token are secrets (see the
    # model comments) — never rendered in the panel, even read-only.
    exclude = ("delivery_code", "recipient_track_token")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletVoucher)
class WalletVoucherAdmin(admin.ModelAdmin):
    # Read-first: voucher codes are bearer money-tokens — the code itself is
    # never shown in the list view nor searchable, and rows are created by the
    # admin voucher flow, never by the Django-admin form.
    list_display = ("amount", "is_used", "used_by", "used_at", "expires_at", "created_at")
    list_filter = ("is_used", "created_at")
    search_fields = ("used_by__phone", "used_by__name", "note")
    ordering = ("-created_at",)
    # The code itself is never rendered in the panel, even read-only: it is a
    # bearer money-token (same exposure class as A-36's reset tokens).
    exclude = ("code",)

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
