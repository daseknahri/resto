from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
from io import BytesIO, StringIO
import re
from urllib.parse import quote_plus
import zipfile


# ── CSV injection protection ──────────────────────────────────────────────────
# Formula-injection (CSV injection): a value starting with =, +, -, @, tab, or
# carriage-return is interpreted as a spreadsheet formula by Excel / Google
# Sheets when the CSV is opened.  Prefix such values with a single-quote so
# the spreadsheet treats them as plain text.  The single-quote is transparent
# in most viewers and does not alter the raw CSV bytes meaningfully.
_CSV_FORMULA_TRIGGERS = frozenset({"=", "+", "-", "@", "\t", "\r"})


def _csv_safe(value) -> str:
    """Return *value* as a string safe for use in a CSV cell.

    Prefixes potentially dangerous formula-injection values with a tab
    character — widely recognised by spreadsheet applications as a way to
    force a text interpretation without cluttering the visible cell content.
    """
    s = str(value) if value is not None else ""
    if s and s[0] in _CSV_FORMULA_TRIGGERS:
        return "\t" + s
    return s

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import qrcode

from tenancy.cache_utils import get_or_build_single_flight
from tenancy.models import Profile
from tenancy.openstate import schedule_open_now

from django_tenants.utils import schema_context

from .models import AnalyticsEvent, Campaign, Category, CurrencyRate, CustomerNote, Dish, DishOption, HappyHour, LoyaltyConfig, OptionGroup, Order, OrderItem, OrderPayment, Promotion, Rating, SectionServer, SuperCategory, TableLink, TableSection, WaitlistEntry
from .permissions import IsTenantEditorOrReadOnly
from .pricing import get_active_happy_hours, get_all_active_hh_rules, effective_unit_price, happy_hour_payload
from .tax import order_vat_fields
from .serializers import (
    CategorySerializer,
    DishOptionSerializer,
    DishSerializer,
    HappyHourSerializer,
    OptionGroupSerializer,
    SuperCategorySerializer,
    TableLinkSerializer,
)
from .throttles import AnalyticsEventThrottle, CheckoutIntentThrottle, OrderHandoffThrottle, PlaceOrderThrottle, StaffOrderListThrottle
from accounts.throttles import (
    ReservationAvailabilityThrottle,
    WaitlistJoinThrottle,
    DriverCashoutConfirmThrottle,
    CustomerOrderRateThrottle,
    OwnerWalletChargeThrottle,
    LoyaltyRedeemThrottle,
)


# ── Menu cache helpers ────────────────────────────────────────────────────────
# Public list responses (unauthenticated customers) are cached per-tenant,
# per-viewset, and per-query-params for _MENU_CACHE_TTL seconds.  Any write
# through the owner CMS increments a version counter, orphaning stale entries
# without requiring pattern-based deletion (works with both LocMemCache and
# Redis).  Authenticated owner/staff requests always bypass the cache so they
# see live DB state immediately.

_MENU_CACHE_TTL = 60  # seconds — acceptable staleness window for menu reads


def _bust_menu_cache(tenant_slug: str) -> None:
    """Increment the version counter, orphaning all existing list-cache entries."""
    if not tenant_slug:
        return
    ver_key = f"menu_ver:{tenant_slug}"
    try:
        cache.incr(ver_key)
    except ValueError:
        # Key missing (LocMemCache raises ValueError; Redis raises ResponseError)
        cache.set(ver_key, 2, timeout=None)


# ── Business hours helpers ────────────────────────────────────────────────────

_WEEKDAY_TO_KEY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}


def _profile_now(profile):
    """Current local datetime for a restaurant, honoring its IANA ``timezone`` (falling
    back to the platform default settings.TIME_ZONE, then UTC). Used so business-hours
    auto open/close evaluates in the restaurant's wall-clock time, not the server's."""
    from datetime import datetime as _dt, timezone as _tz
    try:
        from zoneinfo import ZoneInfo
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        return _dt.now(ZoneInfo(tz_name))
    except Exception:
        return _dt.now(_tz.utc)  # invalid/unknown tz → safe UTC fallback


def service_day_window(profile, now_local=None, date=None):
    """Return (start_aware, end_aware) for the current or a past service day.

    A "service day" starts at the tenant-local hour H = profile.service_day_cutover_hour
    (default 0 = calendar midnight). For a late-night venue with H=3, the service day
    that starts on Monday at 03:00 runs until Tuesday 02:59:59 local time.

    Math — "most recent cutover" relative to *now_local*:
      cutover_dt = today's date @ H:00:00 local  if now_local.hour >= H
                   yesterday's date @ H:00:00 local  otherwise
    The end of that window is one calendar day later at H:00:00 local.

    Args:
        profile:    A Profile instance (must have .timezone and .service_day_cutover_hour).
        now_local:  An aware datetime in the tenant's local tz (used as "now"). Defaults
                    to the actual current time in the tenant's tz. Pass a fixed value in
                    tests to get deterministic windows.
        date:       A datetime.date (or ISO string) representing a PAST service day to
                    look up instead of the current one. When given, now_local is ignored
                    and the window [date @ H → date+1 @ H) is returned.

    Returns:
        (start_aware, end_aware) — both tz-aware datetimes in the tenant's timezone.
    """
    from datetime import date as _date, timedelta as _td, datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        from datetime import timezone as _stdlib_tz
        tz = _stdlib_tz.utc

    H = max(0, min(11, int(getattr(profile, "service_day_cutover_hour", 0) or 0)))

    if date is not None:
        # Caller wants a specific past service day by local date.
        # Coerce strings to date objects.
        if isinstance(date, str):
            date = _date.fromisoformat(date)
        day_start = _dt(date.year, date.month, date.day, H, 0, 0, tzinfo=tz)
        next_day = date + _td(days=1)
        day_end = _dt(next_day.year, next_day.month, next_day.day, H, 0, 0, tzinfo=tz)
        return day_start, day_end

    # Default: the window that contains "now".
    if now_local is None:
        now_local = _profile_now(profile)

    # Find the most recent cutover boundary ≤ now_local.
    # If now_local is at or after H o'clock today, the window started today at H.
    # If now_local is before H o'clock today, the window started yesterday at H.
    today_local = now_local.date()
    cutover_today = _dt(today_local.year, today_local.month, today_local.day, H, 0, 0, tzinfo=tz)
    if now_local >= cutover_today:
        day_start = cutover_today
    else:
        yesterday = today_local - _td(days=1)
        day_start = _dt(yesterday.year, yesterday.month, yesterday.day, H, 0, 0, tzinfo=tz)

    # Build day_end as an explicit local datetime at H:00:00 on the next calendar
    # day — mirrors the date-param path above.  Adding timedelta(days=1) is wrong
    # for DST-observing timezones: on a spring-forward day the result lands one
    # hour too late; on fall-back one hour too early.  ZoneInfo fold semantics
    # guarantee that _dt(next_day, H, 0, 0, tzinfo=tz) resolves to the correct
    # wall-clock hour even across the DST transition.
    next_day_local = day_start.date() + _td(days=1)
    day_end = _dt(next_day_local.year, next_day_local.month, next_day_local.day, H, 0, 0, tzinfo=tz)
    return day_start, day_end


def _schedule_open(profile) -> bool | None:
    """Check *profile.business_hours_schedule* against the restaurant's LOCAL time
    (per ``profile.timezone``; see _profile_now).

    Returns:
      True  — schedule exists and says the restaurant is open right now.
      False — schedule exists and says the restaurant is currently closed.
      None  — no schedule configured (or no enabled days) — caller falls back
               to the manual ``profile.is_open`` boolean.

    The window rule itself now lives in tenancy.openstate.schedule_open_now (the
    SINGLE source of truth shared with the marketplace listing card and the customer
    menu-page serializer). Only the tenant-local "now" resolution stays here, via
    _profile_now (which menu uses everywhere).
    """
    return schedule_open_now(getattr(profile, "business_hours_schedule", None), _profile_now(profile))


def _is_restaurant_currently_open(profile) -> bool:
    """Return True iff the restaurant should accept new orders right now.

    Decision tree:
    1. ``is_open = False`` (manual closed toggle) → always closed.
    2. A configured schedule (at least one enabled day) → schedule wins.
    3. No schedule → rely on ``is_open`` boolean (True = open).
    """
    if profile.is_open is False:
        return False
    result = _schedule_open(profile)
    if result is not None:
        return result
    return bool(profile.is_open)


# ── Advance / scheduled orders ──────────────────────────────────────────────
# A customer may place a pickup/delivery order now for a future time. It is paid
# up front (wallet), kept hidden from the kitchen as status=SCHEDULED, then moved
# to PENDING by the release sweep shortly before the requested time.
_SCHEDULE_MIN_LEAD_MINUTES = 30      # can't schedule for sooner than this (that's just ASAP)
_SCHEDULE_MAX_AHEAD_DAYS = 14        # furthest out an advance order may be placed
_SCHEDULE_RELEASE_LEAD_MINUTES = 45  # how early before scheduled_for the kitchen receives it


def _within_business_hours(profile, dt_local_source) -> bool:
    """True if *dt_local_source* (an aware datetime) falls inside the restaurant's
    configured open window for that local day. When no schedule is configured we
    accept any time — the manual is_open toggle governs live ordering, not future
    scheduling."""
    schedule = getattr(profile, "business_hours_schedule", None)
    if not schedule or not isinstance(schedule, dict):
        return True
    if not any(isinstance(v, dict) and v.get("enabled", False) for v in schedule.values()):
        return True
    try:
        from zoneinfo import ZoneInfo
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        local = dt_local_source.astimezone(ZoneInfo(tz_name))
    except Exception:
        local = dt_local_source
    entry = schedule.get(_WEEKDAY_TO_KEY.get(local.weekday()))
    if not entry or not isinstance(entry, dict) or not entry.get("enabled", False):
        return False
    open_str = (entry.get("open") or "").strip()
    close_str = (entry.get("close") or "").strip()
    if not open_str or not close_str:
        return False
    hhmm = local.strftime("%H:%M")
    return open_str <= hhmm < close_str


def _validate_scheduled_for(profile, fulfillment_type, scheduled_for):
    """Validate a requested advance-order fulfilment time.

    Returns ``(aware_datetime_or_None, error_code_or_None)``:
      - (None, None)      → no scheduling requested (ASAP order).
      - (dt, None)        → valid scheduled time.
      - (None, "code")    → invalid; *code* is a stable machine code for the client.
    """
    if scheduled_for is None:
        return None, None
    if fulfillment_type not in (Order.FulfillmentType.PICKUP, Order.FulfillmentType.DELIVERY):
        return None, "schedule_not_supported"
    dt = scheduled_for
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    now = timezone.now()
    if dt < now + timedelta(minutes=_SCHEDULE_MIN_LEAD_MINUTES):
        return None, "schedule_too_soon"
    if dt > now + timedelta(days=_SCHEDULE_MAX_AHEAD_DAYS):
        return None, "schedule_too_far"
    if not _within_business_hours(profile, dt):
        return None, "schedule_closed"
    return dt, None


def _size_loyalty_redemption(cfg, available_points, requested_points, pre_tip_total):
    """Size a loyalty-points redemption against an order's pre-tip charge.

    Returns ``(discount: Decimal, points_spent: int, error_code: str|None)``:
      - (0, 0, None)   → nothing redeemed (or the discount rounds to zero).
      - (0, 0, "code") → a validation failure (loyalty_disabled /
                         loyalty_insufficient_points / loyalty_below_threshold).
    The discount is capped to the order so points are never wasted, and only the
    points the applied discount actually consumes are spent.
    """
    from decimal import Decimal as _D
    try:
        requested_points = int(requested_points or 0)
    except (TypeError, ValueError):
        requested_points = 0
    if requested_points <= 0:
        return _D("0"), 0, None
    if cfg is None or not getattr(cfg, "enabled", False):
        return _D("0"), 0, "loyalty_disabled"
    pts_value = _D(str(getattr(cfg, "points_value", 0) or "0"))
    threshold = int(getattr(cfg, "redeem_threshold", 0) or 0)
    avail = int(available_points or 0)
    if requested_points > avail:
        return _D("0"), 0, "loyalty_insufficient_points"
    if requested_points < threshold:
        return _D("0"), 0, "loyalty_below_threshold"
    if pts_value <= _D("0"):
        return _D("0"), 0, "loyalty_disabled"
    raw = (_D(requested_points) * pts_value).quantize(_D("0.01"))
    cap = pre_tip_total if pre_tip_total > _D("0") else _D("0")
    discount = min(raw, cap)
    if discount <= _D("0"):
        return _D("0"), 0, None
    import math as _math
    points_spent = min(requested_points, int(_math.ceil(discount / pts_value)))
    return discount, points_spent, None


class PublishAccessMixin:
    def _tenant(self):
        return getattr(self.request, "tenant", None)

    def _profile(self):
        tenant = self._tenant()
        if tenant is None:
            return None
        if hasattr(self, "_cached_profile"):
            return self._cached_profile
        self._cached_profile = Profile.objects.filter(tenant=tenant).first()
        return self._cached_profile

    def _menu_is_published(self) -> bool:
        profile = self._profile()
        return bool(profile and profile.is_menu_published)

    def _menu_is_temporarily_disabled(self) -> bool:
        profile = self._profile()
        return bool(profile and profile.is_menu_temporarily_disabled)

    def _can_preview_unpublished(self) -> bool:
        user = getattr(self.request, "user", None)
        tenant = self._tenant()
        if tenant is None or not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, "is_platform_admin", False):
            return True
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {user.Roles.TENANT_OWNER, user.Roles.TENANT_STAFF}

    def _enforce_public_menu_policy(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return None
        can_preview = self._can_preview_unpublished()
        if self._menu_is_temporarily_disabled() and not can_preview:
            profile = self._profile()
            return Response(
                {
                    "detail": "This menu is temporarily unavailable. Please try again later.",
                    "code": "menu_temporarily_disabled",
                    "note": (profile.menu_disabled_note if profile else "") or "",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if self._menu_is_published() or can_preview:
            return None
        return Response(
            {"detail": "This menu is not published yet. Please contact the restaurant."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _menu_list_cache_key(self) -> str | None:
        """
        Return a server-side cache key for this request's list response,
        or None when the request should bypass the cache.

        Bypassed when:
          • the requesting user is a tenant owner/staff (they need live DB state)
          • no tenant is attached to the request
        """
        if self._can_preview_unpublished():
            return None  # owners/staff always read live data
        tenant = self._tenant()
        if tenant is None:
            return None
        slug = getattr(tenant, "slug", str(getattr(tenant, "id", "0")))
        # Version counter acts as a cheap bust mechanism — incremented on any write
        version = cache.get(f"menu_ver:{slug}") or 1
        # Digest the query params so different filter combos get separate entries
        params_sig = hashlib.md5(
            repr(sorted(self.request.query_params.items())).encode()
        ).hexdigest()[:8]
        resource = type(self).__name__.lower()
        return f"menu:{slug}:{resource}:{version}:{params_sig}"

    def _bust_current_tenant_menu_cache(self) -> None:
        tenant = self._tenant()
        if tenant:
            _bust_menu_cache(getattr(tenant, "slug", str(getattr(tenant, "id", "0"))))

    # ── ViewSet action overrides ──────────────────────────────────────────────

    def list(self, request, *args, **kwargs):
        blocked = self._enforce_public_menu_policy()
        if blocked is not None:
            return blocked

        # Owner/staff or no-tenant requests bypass the cache entirely (live DB state).
        key = self._menu_list_cache_key()
        if key is None:
            return super().list(request, *args, **kwargs)

        # Cacheable public read. Single-flight the rebuild so concurrent misses on a
        # popular tenant's menu (every QR scan at TTL lapse) collapse to ONE DRF
        # queryset+serializer build instead of a thundering herd (R14b). The cached
        # value is the exact response.data, so the response payload is unchanged.
        captured = {}

        def _build():
            # Explicit (class, instance) super — the implicit zero-arg super() has no
            # __class__ cell inside this nested function. Anchor on PublishAccessMixin so
            # this resolves to ModelViewSet.list (the original super().list() target) and
            # never re-enters this overridden list (which would recurse infinitely).
            response = super(PublishAccessMixin, self).list(request, *args, **kwargs)
            captured["status"] = response.status_code
            return response.data

        payload = get_or_build_single_flight(
            key, _build, ttl=_MENU_CACHE_TTL
        )
        # Preserve the original "only cache 200s" guard: if our own build produced a
        # non-200, evict the entry the helper just set so we never serve a stale error.
        if captured.get("status", 200) != 200:
            cache.delete(key)
        # Re-emit the build's status so a non-200 build keeps its code (was returned
        # verbatim pre-single-flight). Followers (lock losers) never set captured["status"]
        # and only ever read a cached 200, so they correctly default to 200.
        return Response(payload, status=captured.get("status", 200))

    def retrieve(self, request, *args, **kwargs):
        blocked = self._enforce_public_menu_policy()
        if blocked is not None:
            return blocked
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._bust_current_tenant_menu_cache()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._bust_current_tenant_menu_cache()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._bust_current_tenant_menu_cache()


def _filter_by_reference(qs, raw_value, *, id_field, slug_field):
    reference = str(raw_value or "").strip()
    if not reference:
        return qs
    if reference.isdigit():
        return qs.filter(**{id_field: int(reference)})
    return qs.filter(**{slug_field: reference})


class SuperCategoryViewSet(PublishAccessMixin, viewsets.ModelViewSet):
    serializer_class = SuperCategorySerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = SuperCategory.objects.annotate(category_count=Count("categories")).all().order_by("position", "name")
        if self.request.method in ("GET", "HEAD", "OPTIONS") and not self._can_preview_unpublished():
            qs = qs.filter(is_published=True, is_temporarily_disabled=False)
        return qs

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()


class CategoryViewSet(PublishAccessMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = (
            Category.objects.select_related("super_category")
            .prefetch_related("dishes__options", "dishes__option_groups__options", "dishes__combo_components__component")
            .all()
        )
        qs = _filter_by_reference(
            qs,
            self.request.query_params.get("super_category"),
            id_field="super_category_id",
            slug_field="super_category__slug",
        )
        if self.request.method in ("GET", "HEAD", "OPTIONS") and not self._can_preview_unpublished():
            qs = qs.filter(
                is_published=True,
                is_temporarily_disabled=False,
                super_category__is_published=True,
                super_category__is_temporarily_disabled=False,
            )
        return qs.order_by("super_category__position", "position", "name")

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Inject active happy-hour rules ONCE per request so the nested DishSerializer
        # instances (in CategorySerializer's dishes field) never issue per-dish queries.
        # Use self._profile() (filters by tenant) instead of Profile.objects.get() which
        # raises MultipleObjectsReturned in multi-tenant deployments.
        if "happy_hours" not in ctx:
            try:
                profile = self._profile()
                if profile is not None:
                    now_local = _profile_now(profile)
                    ctx["happy_hours"] = get_active_happy_hours(now_local)
                else:
                    ctx["happy_hours"] = []
            except Exception:
                ctx["happy_hours"] = []
        return ctx


class DishViewSet(PublishAccessMixin, viewsets.ModelViewSet):
    serializer_class = DishSerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = Dish.objects.select_related("category", "category__super_category").prefetch_related(
            "options", "option_groups__options", "combo_components__component"
        ).all()
        category_slug = self.request.query_params.get("category")
        if category_slug:
            qs = qs.filter(category__slug=category_slug)
        qs = _filter_by_reference(
            qs,
            self.request.query_params.get("super_category"),
            id_field="category__super_category_id",
            slug_field="category__super_category__slug",
        )
        if self.request.method in ("GET", "HEAD", "OPTIONS") and not self._can_preview_unpublished():
            qs = qs.filter(
                is_published=True,
                category__is_published=True,
                category__is_temporarily_disabled=False,
                category__super_category__is_published=True,
                category__super_category__is_temporarily_disabled=False,
            )
        return qs.order_by("category__super_category__position", "category__position", "position", "name")

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Pass can_preview flag so serializer/UI can distinguish owners vs. guests
        ctx["can_preview"] = self._can_preview_unpublished()
        # Compute active happy-hour rules ONCE per request and cache in context so
        # DishSerializer never issues a per-dish N+1 query.
        # Use self._profile() (filters by tenant) instead of Profile.objects.get() which
        # raises MultipleObjectsReturned in multi-tenant deployments.
        if "happy_hours" not in ctx:
            try:
                profile = self._profile()
                if profile is not None:
                    now_local = _profile_now(profile)
                    ctx["happy_hours"] = get_active_happy_hours(now_local)
                else:
                    ctx["happy_hours"] = []
            except Exception:
                ctx["happy_hours"] = []
        return ctx

    def perform_create(self, serializer):
        """Enforce per-plan dish limit before saving.

        Concurrency note: the check is performed inside transaction.atomic() with a
        select_for_update() lock on the Plan row so that concurrent creates cannot
        both pass the count-then-create race and overshoot the cap.  0=unlimited
        (the falsy guard on max_dishes) is preserved.

        The lock is on the Plan row in the public schema; the dish count and
        serializer.save() run in the tenant schema (the middleware-set connection).
        We enter the public schema only long enough to acquire the lock and read
        max_dishes, then return to the tenant schema for the count and save —
        all inside one transaction.atomic() so the lock spans both steps.
        """
        tenant = getattr(self.request, "tenant", None)
        if tenant is not None:
            try:
                from django.db import transaction
                from django_tenants.utils import get_public_schema_name, schema_context
                from tenancy.models import Plan
                from rest_framework.exceptions import ValidationError

                with transaction.atomic():
                    # Phase 1: read max_dishes and lock the Plan row (public schema).
                    with schema_context(get_public_schema_name()):
                        plan_qs = Plan.objects.select_for_update().filter(tenants__id=tenant.id)
                        plan_obj = plan_qs.first()
                        max_dishes = int(getattr(plan_obj, "max_dishes", 0) or 0)

                    # Phase 2: re-count dishes and create (tenant schema restored by
                    # schema_context exit).  The lock from phase 1 is still held.
                    if max_dishes > 0:
                        current_count = Dish.objects.count()
                        if current_count >= max_dishes:
                            raise ValidationError(
                                {
                                    "detail": f"Your plan allows a maximum of {max_dishes} dishes. "
                                              f"You have {current_count}. Upgrade to add more.",
                                    "code": "dish_limit_reached",
                                    "limit": max_dishes,
                                    "current": current_count,
                                }
                            )
                    serializer.save()
                    return
            except Exception as exc:
                if getattr(exc, "detail", None):
                    raise
        serializer.save()

    def perform_update(self, serializer):
        """Clear stock_auto_zeroed when the owner explicitly writes stock_qty.

        An owner who types a stock_qty value into the Inventory tab is making a
        deliberate choice — that is NOT an automatic decrement, so we must not
        let the cron silently re-enable the dish afterwards.  We do this here
        (on the write path) rather than in the serializer so that:
          - The field is never writable by clients (excluded from
            DishSerializer.Meta.fields).
          - The clear fires for both PATCH and PUT.

        Both writes are wrapped in atomic() so a concurrent checkout that zeros
        stock_qty cannot observe the save-without-clear intermediate state.
        """
        from django.db import transaction
        with transaction.atomic():
            instance = serializer.save()
            if "stock_qty" in serializer.validated_data:
                # stock_auto_zeroed is backend-managed and not in the serializer,
                # so use a direct .update() call rather than serializer.save() kwargs.
                Dish.objects.filter(pk=instance.pk).update(stock_auto_zeroed=False)

    def destroy(self, request, *args, **kwargs):
        """Delete a dish. Returns 409 if the dish is a component of a combo
        (ProtectedError from ComboComponent.component on_delete=PROTECT).
        The instance is fetched exactly once via get_object(); perform_destroy
        receives that instance directly so DRF's DestroyModelMixin does not
        make a redundant second get_object() call on the success path."""
        from django.db import ProtectedError
        from django.db.models import RestrictedError
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except (ProtectedError, RestrictedError):
            # Find the first combo that references this dish as a component
            # so we can name it in the error.  Use the already-fetched instance.
            combo_name = ""
            try:
                first_cc = instance.part_of_combos.select_related("dish").first()
                if first_cc is not None:
                    combo_name = first_cc.dish.name
            except Exception:
                pass
            detail = (
                f"Cannot delete '{instance.name}': it is a component of combo '{combo_name}'."
                if combo_name
                else f"Cannot delete '{instance.name}': it is used as a combo component."
            )
            return Response(
                {"detail": detail, "code": "dish_is_combo_component"},
                status=status.HTTP_409_CONFLICT,
            )


class DishOptionViewSet(PublishAccessMixin, viewsets.ModelViewSet):
    serializer_class = DishOptionSerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = DishOption.objects.select_related("dish", "dish__category", "dish__category__super_category").all()
        dish_id = self.request.query_params.get("dish")
        if dish_id:
            qs = qs.filter(dish_id=dish_id)
        if self.request.method in ("GET", "HEAD", "OPTIONS") and not self._can_preview_unpublished():
            qs = qs.filter(
                dish__is_published=True,
                dish__category__is_published=True,
                dish__category__is_temporarily_disabled=False,
                dish__category__super_category__is_published=True,
                dish__category__super_category__is_temporarily_disabled=False,
            )
        return qs.order_by("dish__category__super_category__position", "dish__category__position", "dish__position", "name")

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()


class OptionGroupViewSet(viewsets.ModelViewSet):
    serializer_class = OptionGroupSerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = OptionGroup.objects.select_related("dish").prefetch_related("options").all()
        dish_ref = self.request.query_params.get("dish")
        if dish_ref:
            if str(dish_ref).isdigit():
                qs = qs.filter(dish_id=int(dish_ref))
            else:
                qs = qs.filter(dish__slug=dish_ref)
        return qs.order_by("position", "name")

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()

    def _bust(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            _bust_menu_cache(getattr(tenant, "slug", str(getattr(tenant, "id", "0"))))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._bust()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._bust()

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._bust()


class HappyHourViewSet(viewsets.ModelViewSet):
    """Owner CRUD for time-based pricing rules (happy hours).

    All actions require tenant-editor authentication — there is no public read
    override (unlike DishViewSet / CategoryViewSet which expose AllowAny for GET).
    Clients must pass owner credentials for every request.

    GET    /api/happy-hours/          — list all rules for this tenant.
    POST   /api/happy-hours/          — create a new rule (max 8 per tenant).
    PATCH  /api/happy-hours/<id>/     — partial update.
    DELETE /api/happy-hours/<id>/     — remove a rule.
    """

    serializer_class = HappyHourSerializer
    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return HappyHour.objects.prefetch_related("categories").order_by("id")

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class TableLinkViewSet(viewsets.ModelViewSet):
    serializer_class = TableLinkSerializer
    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def get_queryset(self):
        return TableLink.objects.all().order_by("position", "label", "id")

    def perform_create(self, serializer):
        # Tables are a restaurant-only capability; shops (retail/grocery) don't
        # have table service. Defaults to allowed for restaurants (non-breaking).
        from rest_framework.exceptions import PermissionDenied
        from tenancy.capabilities import tenant_capability_enabled
        if not tenant_capability_enabled(getattr(self.request, "tenant", None), "tables"):
            raise PermissionDenied(detail="Tables are not available for this business.")
        super().perform_create(serializer)

    def _safe_filename_token(self, value, fallback="item"):
        cleaned = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        return cleaned[:60] or fallback

    def _public_menu_base_url(self, request):
        explicit = str(request.query_params.get("menu_base_url", "") or "").strip().rstrip("/")
        if explicit:
            return explicit
        configured = str(getattr(settings, "PUBLIC_MENU_BASE_URL", "") or "").strip().rstrip("/")
        if configured:
            return configured
        scheme = "https" if request.is_secure() else "http"
        host = request.get_host()
        if host.endswith(":8000") and (host.startswith("localhost") or host.endswith(".localhost:8000")):
            host = f"{host[:-5]}:5173"
        return f"{scheme}://{host}"

    def _table_short_url(self, table, base_url):
        return f"{base_url}/t/{table.slug}"

    def _table_full_url(self, table, base_url):
        return f"{base_url}/menu?table={quote_plus(table.label)}"

    def _qr_png_bytes(self, value):
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(value)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#0f172a", back_color="white")
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    def _qr_pdf_bytes(self, rows, base_url, tenant_name):
        buffer = BytesIO()
        doc = canvas.Canvas(buffer, pagesize=A4)
        page_width, page_height = A4
        margin = 10 * mm
        gap_x = 6 * mm
        gap_y = 6 * mm
        cols = 2
        rows_per_page = 4
        card_width = (page_width - (2 * margin) - gap_x) / cols
        card_height = (page_height - (2 * margin) - (gap_y * (rows_per_page - 1))) / rows_per_page

        for index, table in enumerate(rows):
            page_slot = index % (cols * rows_per_page)
            if index > 0 and page_slot == 0:
                doc.showPage()

            row_idx = page_slot // cols
            col_idx = page_slot % cols
            x = margin + (col_idx * (card_width + gap_x))
            y = page_height - margin - ((row_idx + 1) * card_height) - (row_idx * gap_y)

            doc.roundRect(x, y, card_width, card_height, 6, stroke=1, fill=0)
            doc.setFont("Helvetica-Bold", 9)
            doc.drawString(x + 8, y + card_height - 16, str(tenant_name)[:42])

            doc.setFont("Helvetica-Bold", 14)
            doc.drawString(x + 8, y + card_height - 34, str(table.label)[:26])

            short_url = self._table_short_url(table, base_url)
            qr_png = self._qr_png_bytes(short_url)
            qr_size = min(card_width - 22 * mm, card_height - 26 * mm)
            qr_x = x + (card_width - qr_size) / 2
            qr_y = y + 13 * mm
            doc.drawImage(ImageReader(BytesIO(qr_png)), qr_x, qr_y, qr_size, qr_size, preserveAspectRatio=True, mask="auto")

            doc.setFont("Helvetica", 7)
            doc.drawString(x + 8, y + 8, short_url[:72])

        doc.save()
        return buffer.getvalue()

    @action(detail=True, methods=["get"], url_path="qr-image")
    def qr_image(self, request, pk=None):
        table = self.get_object()
        base_url = self._public_menu_base_url(request)
        short_url = self._table_short_url(table, base_url)
        png_bytes = self._qr_png_bytes(short_url)
        filename = f"{self._safe_filename_token(table.label, fallback='table')}-qr.png"
        response = HttpResponse(png_bytes, content_type="image/png")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "private, max-age=300"
        return response

    @action(detail=False, methods=["get"], url_path="qr-export")
    def qr_export(self, request):
        include_disabled = str(request.query_params.get("include_disabled", "") or "").strip().lower() in {"1", "true", "yes"}
        export_format = str(
            request.query_params.get("export_format")
            or request.query_params.get("qr_format")
            or "zip"
        ).strip().lower()
        if export_format not in {"zip", "pdf"}:
            return Response(
                {"detail": "Unsupported export format.", "code": "invalid_format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()
        if not include_disabled:
            queryset = queryset.filter(is_active=True)
        rows = list(queryset)
        if not rows:
            return Response(
                {"detail": "No table links available for export.", "code": "no_tables"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_url = self._public_menu_base_url(request)

        tenant = getattr(request, "tenant", None)
        tenant_slug = self._safe_filename_token(getattr(tenant, "slug", ""), fallback="tenant")
        tenant_name = getattr(tenant, "name", "Restaurant")

        if export_format == "pdf":
            pdf_bytes = self._qr_pdf_bytes(rows=rows, base_url=base_url, tenant_name=tenant_name)
            filename = f"{tenant_slug}-qr-export.pdf"
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            response["Cache-Control"] = "private, max-age=300"
            return response

        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["label", "slug", "short_url", "full_menu_url", "is_active"])

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for table in rows:
                short_url = self._table_short_url(table, base_url)
                full_url = self._table_full_url(table, base_url)
                csv_writer.writerow([_csv_safe(table.label), table.slug, short_url, full_url, "true" if table.is_active else "false"])
                qr_name = f"qr/{self._safe_filename_token(table.slug, fallback='table')}.png"
                archive.writestr(qr_name, self._qr_png_bytes(short_url))

            archive.writestr("manifest.csv", csv_buffer.getvalue())

        filename = f"{tenant_slug}-qr-export.zip"
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "private, max-age=300"
        return response


class TableBulkGenerateInputSerializer(serializers.Serializer):
    prefix = serializers.CharField(max_length=20, required=False, allow_blank=False, default="Table")
    start = serializers.IntegerField(min_value=1, required=False, default=1)
    count = serializers.IntegerField(min_value=1, max_value=120, required=False, default=10)
    position_start = serializers.IntegerField(min_value=0, required=False, default=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_prefix(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Prefix is required.")
        if not re.match(r"^[A-Za-z0-9\s\-_#]{1,20}$", cleaned):
            raise serializers.ValidationError("Prefix can only include letters, numbers, spaces, #, - and _.")
        return cleaned


class TableBulkGenerateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def post(self, request, *args, **kwargs):
        serializer = TableBulkGenerateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        prefix = payload["prefix"]
        start = int(payload["start"])
        count = int(payload["count"])
        position = int(payload["position_start"])
        is_active = bool(payload.get("is_active", True))

        created_rows = []
        with transaction.atomic():
            for offset in range(count):
                label = f"{prefix} {start + offset}"
                row_serializer = TableLinkSerializer(
                    data={
                        "label": label,
                        "position": position + offset,
                        "is_active": is_active,
                    }
                )
                row_serializer.is_valid(raise_exception=True)
                row = row_serializer.save()
                created_rows.append(TableLinkSerializer(row).data)

        return Response(
            {
                "detail": f"Created {len(created_rows)} table links.",
                "created_count": len(created_rows),
                "created": created_rows,
            },
            status=status.HTTP_201_CREATED,
        )


ANALYTICS_EVENT_TYPES = (
    "menu_view",
    "category_view",
    "dish_view",
    "cart_view",
    "order_handoff_click",
    "checkout_click",
    "owner_publish",
    "lead_submit",
    "contact_click",
    "customer_info_view",
    "customer_info_lead_submit",
    "reservation_submit",
)


class AnalyticsEventInputSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=ANALYTICS_EVENT_TYPES)
    path = serializers.CharField(max_length=320, required=False, allow_blank=True)
    category_slug = serializers.SlugField(max_length=160, required=False, allow_blank=True)
    dish_slug = serializers.SlugField(max_length=210, required=False, allow_blank=True)
    source = serializers.CharField(max_length=48, required=False, allow_blank=True)
    session_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)

    def validate_metadata(self, value):
        if not isinstance(value, dict):
            return {}
        safe = {}
        for key, raw in value.items():
            safe_key = str(key)[:48]
            if isinstance(raw, (str, int, float, bool)) or raw is None:
                safe[safe_key] = raw
            elif isinstance(raw, (list, tuple)):
                safe[safe_key] = [str(x)[:80] for x in list(raw)[:10]]
            elif isinstance(raw, dict):
                safe[safe_key] = {str(k)[:32]: str(v)[:80] for k, v in list(raw.items())[:10]}
            else:
                safe[safe_key] = str(raw)[:120]
        return safe

    def validate(self, attrs):
        event_type = attrs.get("event_type")
        if event_type == "category_view" and not attrs.get("category_slug"):
            raise serializers.ValidationError({"category_slug": "category_slug is required for category_view"})
        if event_type == "dish_view" and not attrs.get("dish_slug"):
            raise serializers.ValidationError({"dish_slug": "dish_slug is required for dish_view"})
        return attrs


class AnalyticsEventIngestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnalyticsEventThrottle]

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Analytics ingestion ignored for public host.", "code": "public_host_ignored"},
                status=status.HTTP_202_ACCEPTED,
            )
        if getattr(tenant, "schema_name", "") == "public":
            return Response(
                {"detail": "Analytics ingestion ignored for public schema.", "code": "public_schema_ignored"},
                status=status.HTTP_202_ACCEPTED,
            )

        serializer = AnalyticsEventInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        event = AnalyticsEvent.objects.create(
            event_type=payload["event_type"],
            path=payload.get("path", "")[:320],
            category_slug=payload.get("category_slug", "")[:160],
            dish_slug=payload.get("dish_slug", "")[:210],
            source=payload.get("source", "")[:48],
            session_id=payload.get("session_id", "")[:64],
            metadata=payload.get("metadata", {}),
        )
        return Response({"detail": "event_recorded", "id": event.id}, status=status.HTTP_202_ACCEPTED)


class OwnerBestSellersView(APIView):
    """
    GET /api/owner/best-sellers/?period=30

    Returns the top-10 dishes by order count and by revenue for the last N days,
    derived from OrderItem rows on completed orders.
    """

    permission_classes = [IsAuthenticated]

    _COUNTED = [
        "confirmed", "preparing", "ready", "out_for_delivery",
        "delivered", "completed",
    ]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            period = int(request.query_params.get("period", "30"))
        except (TypeError, ValueError):
            period = 30
        period = max(7, min(90, period))

        from django.db.models import Count as _C, Sum as _S, FloatField as _FF
        from django.utils import timezone as _tz
        import datetime

        since = _tz.now() - datetime.timedelta(days=period)

        base_qs = (
            OrderItem.objects
            .filter(
                order__status__in=self._COUNTED,
                order__created_at__gte=since,
            )
        )

        by_count = list(
            base_qs
            .values("dish_slug", "dish_name")
            .annotate(total_qty=_C("qty"), revenue=_S("subtotal", output_field=_FF()))
            .order_by("-total_qty")[:10]
        )

        by_revenue = list(
            base_qs
            .values("dish_slug", "dish_name")
            .annotate(total_qty=_C("qty"), revenue=_S("subtotal", output_field=_FF()))
            .order_by("-revenue")[:10]
        )

        currency = (
            Order.objects
            .filter(status__in=self._COUNTED, created_at__gte=since)
            .order_by("-created_at")
            .values_list("currency", flat=True)
            .first()
        ) or "USD"

        def fmt(rows):
            return [
                {
                    "dish_slug": r["dish_slug"],
                    "dish_name": r["dish_name"],
                    "total_qty": r["total_qty"],
                    "revenue": round(float(r["revenue"] or 0), 2),
                }
                for r in rows
            ]

        return Response({
            "period": period,
            "currency": currency,
            "by_count": fmt(by_count),
            "by_revenue": fmt(by_revenue),
        })


class OwnerRevenueChartView(APIView):
    """
    GET /api/owner/revenue-chart/?period=7|14|30

    Returns daily aggregated revenue + order count for the last N days,
    based on completed/delivered orders.  Used by the owner dashboard chart.
    """

    permission_classes = [IsAuthenticated]

    _COUNTED = [
        "confirmed", "preparing", "ready", "out_for_delivery",
        "delivered", "completed",
    ]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            period = int(request.query_params.get("period", "14"))
        except (TypeError, ValueError):
            period = 14
        period = max(7, min(90, period))

        from django.db.models import Count as _Count, Sum as _Sum, FloatField as _FF
        from django.db.models.functions import TruncDate
        from django.utils import timezone as _tz
        import datetime

        now = _tz.now()
        since = now - datetime.timedelta(days=period - 1)
        since_date = since.date()

        rows = (
            Order.objects
            .filter(status__in=self._COUNTED, created_at__date__gte=since_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                revenue=_Sum("total", output_field=_FF()),
                order_count=_Count("id"),
            )
            .order_by("day")
        )

        # Build a full date-range map so every day is present (even with 0)
        day_map = {}
        for i in range(period):
            d = (since + datetime.timedelta(days=i)).date()
            day_map[d] = {"date": d.isoformat(), "revenue": 0.0, "order_count": 0}
        for row in rows:
            d = row["day"]
            if d in day_map:
                day_map[d]["revenue"] = float(row["revenue"] or 0)
                day_map[d]["order_count"] = row["order_count"]

        # Currency from the most recent order (best-effort)
        currency = (
            Order.objects
            .filter(status__in=self._COUNTED, created_at__date__gte=since_date)
            .order_by("-created_at")
            .values_list("currency", flat=True)
            .first()
        ) or "USD"

        return Response({
            "period": period,
            "currency": currency,
            "days": list(day_map.values()),
        })


class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def _can_view(self, request, tenant) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, "is_platform_admin", False):
            return True
        if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {user.Roles.TENANT_OWNER, user.Roles.TENANT_STAFF}

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved.", "code": "tenant_missing"}, status=status.HTTP_400_BAD_REQUEST)
        if getattr(tenant, "schema_name", "") == "public":
            return Response(
                {"detail": "Analytics summary is not available on public schema.", "code": "public_schema_unsupported"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not self._can_view(request, tenant):
            return Response({"detail": "Owner access required.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            requested_days = int(request.query_params.get("days", "30"))
        except (TypeError, ValueError):
            requested_days = 30
        days = max(1, min(90, requested_days))
        since = timezone.now() - timedelta(days=days)
        qs = AnalyticsEvent.objects.filter(created_at__gte=since)

        raw_counts = {row["event_type"]: row["count"] for row in qs.values("event_type").annotate(count=Count("id"))}
        counts = {event_type: int(raw_counts.get(event_type, 0)) for event_type in ANALYTICS_EVENT_TYPES}
        menu_views = counts.get("menu_view", 0)
        order_actions = counts.get("order_handoff_click", 0) + counts.get("checkout_click", 0)
        interaction_rate = round((order_actions / menu_views) * 100, 2) if menu_views else 0.0

        top_categories = list(
            qs.exclude(category_slug="")
            .values("category_slug")
            .annotate(count=Count("id"))
            .order_by("-count", "category_slug")[:5]
        )
        top_dishes = list(
            qs.exclude(dish_slug="")
            .values("dish_slug")
            .annotate(count=Count("id"))
            .order_by("-count", "dish_slug")[:5]
        )

        return Response(
            {
                "days": days,
                "since": since.isoformat(),
                "total_events": qs.count(),
                "counts": counts,
                "top_categories": top_categories,
                "top_dishes": top_dishes,
                "interaction_rate_pct": interaction_rate,
            },
            status=status.HTTP_200_OK,
        )


class OwnerAnalyticsExportView(APIView):
    """CSV export of analytics events grouped by date and event type."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None or getattr(tenant, "schema_name", "") == "public":
            return Response({"detail": "Not available on public schema."}, status=status.HTTP_400_BAD_REQUEST)
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            requested_days = int(request.query_params.get("days", "30"))
        except (TypeError, ValueError):
            requested_days = 30
        days = max(1, min(365, requested_days))
        since = timezone.now() - timedelta(days=days)

        from django.db.models.functions import TruncDate
        rows = (
            AnalyticsEvent.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day", "event_type")
            .annotate(count=Count("id"))
            .order_by("day", "event_type")
        )

        filename = f"analytics_{days}d.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["date", "event_type", "count"])
        for row in rows:
            writer.writerow([row["day"].isoformat(), row["event_type"], row["count"]])

        return response


class OrderItemInputSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=210)
    qty = serializers.IntegerField(min_value=1, max_value=99)
    note = serializers.CharField(max_length=120, required=False, allow_blank=True)
    option_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        max_length=25,
    )


class OrderHandoffSerializer(serializers.Serializer):
    items = OrderItemInputSerializer(many=True, min_length=1, max_length=50)
    customer_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    table_label = serializers.CharField(max_length=40, required=False, allow_blank=True)
    table_slug = serializers.SlugField(max_length=55, required=False, allow_blank=True)
    fulfillment_type = serializers.ChoiceField(
        choices=("pickup", "delivery", "table"),
        required=False,
        allow_blank=True,
    )
    customer_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    delivery_address = serializers.CharField(max_length=180, required=False, allow_blank=True)
    delivery_location_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    delivery_lat = serializers.FloatField(required=False, allow_null=True)
    delivery_lng = serializers.FloatField(required=False, allow_null=True)
    # Advance/scheduled order — when set, the customer wants fulfilment at this future
    # time (validated server-side against business hours + lead window in the view).
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)

    def validate_table_label(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        if not re.match(r"^[A-Za-z0-9\s\-_#]{1,40}$", cleaned):
            raise serializers.ValidationError("Table label can only include letters, numbers, spaces, #, - and _.")
        return cleaned

    def validate_customer_name(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        if len(cleaned) < 2:
            raise serializers.ValidationError("Customer name is too short.")
        if len(cleaned) > 80:
            raise serializers.ValidationError("Customer name must be 80 characters or fewer.")
        if re.search(r"[<>\"{}|\\^`\x00-\x1f]", cleaned):
            raise serializers.ValidationError("Customer name contains unsupported characters.")
        return cleaned

    def validate_customer_phone(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        if not re.match(r"^[0-9+\-\s()]{6,30}$", cleaned):
            raise serializers.ValidationError("Customer phone must be 6-30 characters and contain digits/+/-/() only.")
        return cleaned

    def validate_delivery_address(self, value):
        return (value or "").strip()

    def validate_delivery_lat(self, value):
        if value is None:
            return None
        if value < -90 or value > 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return float(value)

    def validate_delivery_lng(self, value):
        if value is None:
            return None
        if value < -180 or value > 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return float(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        table_label = (attrs.get("table_label") or "").strip()
        attrs["table_label"] = table_label
        table_slug = (attrs.get("table_slug") or "").strip().lower()
        attrs["table_slug"] = table_slug
        # Table-QR flow: optional name/note only. Pickup: anonymous. Delivery: requires customer session (enforced in the view).
        if table_slug or table_label:
            return attrs

        errors = {}
        fulfillment_type = (attrs.get("fulfillment_type") or "").strip().lower()
        if not fulfillment_type:
            errors["fulfillment_type"] = "Select pickup or delivery."
        else:
            attrs["fulfillment_type"] = fulfillment_type

        if fulfillment_type == "delivery":
            has_coords = attrs.get("delivery_lat") is not None and attrs.get("delivery_lng") is not None
            has_map_url = bool((attrs.get("delivery_location_url") or "").strip())
            if not attrs.get("delivery_address"):
                errors["delivery_address"] = "Delivery address is required."
            if not has_coords and not has_map_url:
                errors["delivery_location_url"] = "Provide map link or use current location."
            if (attrs.get("delivery_lat") is None) ^ (attrs.get("delivery_lng") is None):
                errors["delivery_lat"] = "Latitude and longitude must be provided together."
                errors["delivery_lng"] = "Latitude and longitude must be provided together."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TableContextView(PublishAccessMixin, APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, table_slug, *args, **kwargs):
        blocked = self._enforce_public_menu_policy()
        if blocked is not None:
            return blocked

        slug = (table_slug or "").strip().lower()
        if not slug:
            return Response(
                {"detail": "Table slug is required.", "code": "table_slug_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        table = TableLink.objects.filter(slug=slug, is_active=True).first()
        if table is None:
            return Response(
                {"detail": "Table link is unavailable.", "code": "table_unavailable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "slug": table.slug,
                "label": table.label,
                "is_active": table.is_active,
            },
            status=status.HTTP_200_OK,
        )


class OrderHandoffView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OrderHandoffThrottle]

    def _tenant(self):
        return getattr(self.request, "tenant", None)

    def _profile_for_tenant(self, tenant):
        if tenant is None:
            return None
        return Profile.objects.filter(tenant=tenant).first()

    def _can_preview_unpublished(self, tenant) -> bool:
        user = getattr(self.request, "user", None)
        if tenant is None or not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, "is_platform_admin", False):
            return True
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {user.Roles.TENANT_OWNER, user.Roles.TENANT_STAFF}

    def _fetch_dishes(self, slugs, can_preview):
        qs = Dish.objects.filter(slug__in=slugs).select_related("category")
        if not can_preview:
            qs = qs.filter(
                is_published=True, is_available=True,
                category__is_published=True, category__is_temporarily_disabled=False,
            )
        return {dish.slug: dish for dish in qs}

    def _fetch_options(self, option_ids, can_preview):
        if not option_ids:
            return {}
        qs = DishOption.objects.filter(id__in=option_ids).select_related("dish", "dish__category")
        if not can_preview:
            qs = qs.filter(
                dish__is_published=True,
                dish__category__is_published=True,
                dish__category__is_temporarily_disabled=False,
            )
        return {opt.id: opt for opt in qs}

    def _sanitize_phone(self, value: str) -> str:
        return "".join(ch for ch in (value or "") if ch.isdigit())

    def _fetch_active_table_by_slug(self, slug: str):
        normalized = (slug or "").strip().lower()
        if not normalized:
            return None
        return TableLink.objects.filter(slug=normalized, is_active=True).first()

    def post(self, request, *args, **kwargs):
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant not resolved.", "code": "tenant_missing"}, status=status.HTTP_400_BAD_REQUEST)

        profile = self._profile_for_tenant(tenant)
        if profile is None:
            return Response(
                {"detail": "Restaurant profile not configured.", "code": "profile_missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        can_preview = self._can_preview_unpublished(tenant)
        if profile.is_menu_temporarily_disabled and not can_preview:
            return Response(
                {
                    "detail": "This menu is temporarily unavailable. Please try again later.",
                    "code": "menu_temporarily_disabled",
                    "note": profile.menu_disabled_note or "",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not profile.is_menu_published and not can_preview:
            return Response(
                {
                    "detail": "This menu is not published yet.",
                    "code": "menu_unpublished",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_preview and not _is_restaurant_currently_open(profile):
            return Response(
                {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                status=status.HTTP_409_CONFLICT,
            )

        plan = getattr(tenant, "plan", None)
        if not plan or not plan.can_whatsapp_order:
            return Response(
                {"detail": "WhatsApp ordering is not available on this plan.", "code": "plan_forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )

        phone = self._sanitize_phone(profile.whatsapp or profile.phone)
        if not phone:
            return Response(
                {"detail": "Restaurant WhatsApp/phone is not configured.", "code": "contact_missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderHandoffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        table_slug = (payload.get("table_slug") or "").strip().lower()
        resolved_table_label = payload.get("table_label", "")
        resolved_table_slug = ""
        if table_slug:
            resolved_table = self._fetch_active_table_by_slug(table_slug)
            if resolved_table is None:
                return Response(
                    {"detail": "Table link is unavailable.", "code": "table_unavailable"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved_table_label = resolved_table.label
            resolved_table_slug = resolved_table.slug
        requested_items = payload["items"]
        slugs = [item["slug"] for item in requested_items]
        option_ids = sorted({int(opt_id) for item in requested_items for opt_id in item.get("option_ids", [])})

        dishes_by_slug = self._fetch_dishes(slugs, can_preview=can_preview)
        options_by_id = self._fetch_options(option_ids, can_preview=can_preview)
        unavailable = [slug for slug in slugs if slug not in dishes_by_slug]
        if unavailable:
            return Response(
                {
                    "detail": "Some cart items are unavailable.",
                    "code": "items_unavailable",
                    "unavailable_slugs": unavailable,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = [f"Hello, I want to place an order with {tenant.name}."]
        if resolved_table_label:
            lines.append(f"Table: {resolved_table_label}")
        is_table_context = bool(resolved_table_slug or resolved_table_label)
        if payload.get("customer_name"):
            lines.append(f"Customer: {payload['customer_name']}")
        if payload.get("customer_phone"):
            lines.append(f"Phone: {payload['customer_phone']}")
        if not is_table_context and payload.get("fulfillment_type"):
            lines.append(f"Fulfillment: {str(payload['fulfillment_type']).title()}")
        if not is_table_context and payload.get("fulfillment_type") == "delivery":
            if payload.get("delivery_address"):
                lines.append(f"Delivery address: {payload['delivery_address']}")
            has_coords = payload.get("delivery_lat") is not None and payload.get("delivery_lng") is not None
            if has_coords:
                lines.append(f"Delivery coordinates: {payload['delivery_lat']}, {payload['delivery_lng']}")
            if payload.get("delivery_location_url"):
                lines.append(f"Map: {payload['delivery_location_url']}")
        total = Decimal("0")
        currency = None
        for item in requested_items:
            dish = dishes_by_slug[item["slug"]]
            qty = int(item["qty"])
            unique_option_ids = list(dict.fromkeys(int(opt_id) for opt_id in item.get("option_ids", [])))
            selected_options = []
            invalid_option_ids = []
            for opt_id in unique_option_ids:
                opt = options_by_id.get(opt_id)
                opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
                if opt is None or opt_dish_slug != dish.slug:
                    invalid_option_ids.append(opt_id)
                    continue
                selected_options.append(opt)

            if invalid_option_ids:
                return Response(
                    {
                        "detail": f"Some selected options are no longer valid for '{dish.name}'.",
                        "code": "stale_options",
                        "dish_slug": dish.slug,
                        "invalid_option_ids": invalid_option_ids,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            option_total = sum((Decimal(opt.price_delta) for opt in selected_options), Decimal("0"))
            unit_price = dish.price + option_total
            line_total = unit_price * qty
            total += line_total
            if currency is None:
                currency = dish.currency or "USD"
            elif dish.currency != currency:
                return Response(
                    {"detail": "Cart cannot mix multiple currencies.", "code": "mixed_currency"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            line = f"- {qty} x {dish.name} ({unit_price} {dish.currency})"
            if selected_options:
                line += f" | options: {', '.join(opt.name for opt in selected_options)}"
            if item.get("note"):
                line += f" | note: {item['note']}"
            lines.append(line)

        # Add delivery fee for delivery orders (snapshot from profile at handoff time)
        _wa_delivery_fee = Decimal("0")
        if payload.get("fulfillment_type") == "delivery":
            try:
                _profile = getattr(tenant, "profile", None)
                _raw_fee = getattr(_profile, "delivery_fee", 0) or 0
                _wa_delivery_fee = Decimal(str(_raw_fee))
            except Exception:
                _wa_delivery_fee = Decimal("0")

        if _wa_delivery_fee > 0:
            lines.append(f"Subtotal: {total} {currency or 'USD'}")
            lines.append(f"Delivery fee: {_wa_delivery_fee} {currency or 'USD'}")
            lines.append(f"Total: {total + _wa_delivery_fee} {currency or 'USD'}")
        else:
            lines.append(f"Total: {total} {currency or 'USD'}")

        if payload.get("customer_note"):
            lines.append(f"Customer note: {payload['customer_note']}")

        message = "\n".join(lines)
        url = f"https://wa.me/{phone}?text={quote_plus(message)}"
        return Response(
            {
                "detail": "Order handoff ready.",
                "url": url,
                "message": message,
                "table_label": resolved_table_label,
                "table_slug": resolved_table_slug,
                "is_table_context": is_table_context,
                "fulfillment_type": payload.get("fulfillment_type", ""),
                "customer_name": payload.get("customer_name", ""),
                "customer_phone": payload.get("customer_phone", ""),
                "delivery_address": payload.get("delivery_address", ""),
                "delivery_location_url": payload.get("delivery_location_url", ""),
                "delivery_lat": payload.get("delivery_lat", None),
                "delivery_lng": payload.get("delivery_lng", None),
                "subtotal": str(total),
                "delivery_fee": str(_wa_delivery_fee),
                "total": str(total + _wa_delivery_fee),
                "currency": currency or "USD",
            },
            status=status.HTTP_200_OK,
        )


class CheckoutIntentView(OrderHandoffView):
    throttle_classes = [CheckoutIntentThrottle]

    def post(self, request, *args, **kwargs):
        tenant = self._tenant()
        if tenant is None:
            return Response({"detail": "Tenant not resolved.", "code": "tenant_missing"}, status=status.HTTP_400_BAD_REQUEST)

        profile = self._profile_for_tenant(tenant)
        if profile is None:
            return Response(
                {"detail": "Restaurant profile not configured.", "code": "profile_missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        can_preview = self._can_preview_unpublished(tenant)
        if profile.is_menu_temporarily_disabled and not can_preview:
            return Response(
                {
                    "detail": "This menu is temporarily unavailable. Please try again later.",
                    "code": "menu_temporarily_disabled",
                    "note": profile.menu_disabled_note or "",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not profile.is_menu_published and not can_preview:
            return Response(
                {
                    "detail": "This menu is not published yet.",
                    "code": "menu_unpublished",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_preview and not _is_restaurant_currently_open(profile):
            return Response(
                {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                status=status.HTTP_409_CONFLICT,
            )

        plan = getattr(tenant, "plan", None)
        if not plan or not plan.can_checkout:
            return Response(
                {"detail": "Checkout is not available on this plan.", "code": "plan_forbidden_checkout"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrderHandoffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        table_slug = (payload.get("table_slug") or "").strip().lower()
        if table_slug and self._fetch_active_table_by_slug(table_slug) is None:
            return Response(
                {"detail": "Table link is unavailable.", "code": "table_unavailable"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        requested_items = payload["items"]
        slugs = [item["slug"] for item in requested_items]
        option_ids = sorted({int(opt_id) for item in requested_items for opt_id in item.get("option_ids", [])})

        dishes_by_slug = self._fetch_dishes(slugs, can_preview=can_preview)
        options_by_id = self._fetch_options(option_ids, can_preview=can_preview)
        unavailable = [slug for slug in slugs if slug not in dishes_by_slug]
        if unavailable:
            return Response(
                {
                    "detail": "Some cart items are unavailable.",
                    "code": "items_unavailable",
                    "unavailable_slugs": unavailable,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = Decimal("0")
        currency = None
        for item in requested_items:
            dish = dishes_by_slug[item["slug"]]
            qty = int(item["qty"])
            unique_option_ids = list(dict.fromkeys(int(opt_id) for opt_id in item.get("option_ids", [])))
            selected_options = []
            invalid_option_ids = []
            for opt_id in unique_option_ids:
                opt = options_by_id.get(opt_id)
                opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
                if opt is None or opt_dish_slug != dish.slug:
                    invalid_option_ids.append(opt_id)
                    continue
                selected_options.append(opt)

            if invalid_option_ids:
                return Response(
                    {
                        "detail": f"Some selected options are no longer valid for '{dish.name}'.",
                        "code": "stale_options",
                        "dish_slug": dish.slug,
                        "invalid_option_ids": invalid_option_ids,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            option_total = sum((Decimal(opt.price_delta) for opt in selected_options), Decimal("0"))
            unit_price = dish.price + option_total
            line_total = unit_price * qty
            total += line_total
            if currency is None:
                currency = dish.currency or "USD"
            elif dish.currency != currency:
                return Response(
                    {"detail": "Cart cannot mix multiple currencies.", "code": "mixed_currency"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {
                "detail": "Checkout intent accepted. Payment integration is pending.",
                "code": "checkout_not_configured",
                "checkout_enabled": False,
                "total": str(total),
                "currency": currency or "USD",
                "items_count": len(requested_items),
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ---------------------------------------------------------------------------
# In-app order management
# ---------------------------------------------------------------------------

import secrets as _secrets


def _is_promo_active_now(promo, now_local=None) -> bool:
    """Return True if a Promotion is currently active (schedule + date boundaries).

    THIN WRAPPER over menu.promos.promo_is_active — the single source of truth for
    the promo window (date bounds + day-of-week + HH:MM). This wrapper holds NO
    date/time rules of its own; it only picks the clock and delegates.

    ``now_local`` is the tenant-local tz-aware "now" the window is evaluated from;
    production callers pass _profile_now(profile) so the discount is evaluated in the
    tenant's wall-clock time (intentional, correct behavior change — pre-launch with
    no live promos, so safe). When omitted it defaults to a SINGLE consistent UTC
    clock, which already removes the old today()/utcnow() mismatch for callers that
    don't supply a tenant now.
    """
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    from menu.promos import promo_is_active
    if now_local is None:
        now_local = _dt.now(ZoneInfo("UTC"))
    return promo_is_active(promo, now_local=now_local)


def _compute_promo_discount(promo, food_subtotal, delivery_fee) -> "Decimal":
    """Compute the discount amount (Decimal) for a given Promotion."""
    from decimal import Decimal as _Dec
    if promo.promo_type == "percentage":
        pct = min(_Dec("100"), max(_Dec("0"), _Dec(str(promo.discount_value))))
        return (food_subtotal * pct / _Dec("100")).quantize(_Dec("0.01"))
    elif promo.promo_type == "fixed":
        return min(food_subtotal, _Dec(str(promo.discount_value))).quantize(_Dec("0.01"))
    elif promo.promo_type == "free_delivery":
        return delivery_fee
    return _Dec("0")


def _generate_order_number() -> str:
    """Generate a unique order number like ORD-A3F2C1."""
    for _ in range(10):
        candidate = f"ORD-{_secrets.token_hex(3).upper()}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate unique order number after 10 attempts.")


def _generate_delivery_code() -> str:
    """Short 4-digit proof-of-delivery code (e.g. '4821'). The customer reads it to the
    driver, who enters it to confirm hand-off. Not globally unique — it's only checked
    against its own order, so a 4-digit PIN is enough and easy to read aloud."""
    return f"{_secrets.randbelow(10000):04d}"


def _notify_restaurant_new_order(order, tenant_name: str, whatsapp_phone: str, tenant_id=None) -> None:
    """Send a WhatsApp notification to the restaurant when a new order arrives.

    Uses Twilio's WhatsApp API. If any configuration is missing or the call
    fails, the error is silently logged — the order has already been saved and
    this must never block the customer-facing response.
    """
    import logging as _logging
    import urllib.error as _urlerror
    import urllib.parse as _urlparse
    import urllib.request as _urlrequest

    _log = _logging.getLogger(__name__)

    try:
        from django.conf import settings as _settings
        account_sid = getattr(_settings, "TWILIO_ACCOUNT_SID", "").strip()
        auth_token = getattr(_settings, "TWILIO_AUTH_TOKEN", "").strip()
        from_number = getattr(_settings, "TWILIO_FROM_NUMBER", "").strip()
        if not (account_sid and auth_token and from_number and whatsapp_phone):
            return  # Not configured — skip silently

        # Build a concise notification message
        fulfillment = order.fulfillment_type or "pickup"
        if fulfillment == Order.FulfillmentType.TABLE and order.table_label:
            fulfillment_label = f"Table {order.table_label}"
        elif fulfillment == Order.FulfillmentType.DELIVERY:
            fulfillment_label = "Delivery"
        else:
            fulfillment_label = "Pickup"

        item_lines = []
        for item in order.items.all():
            opt_names = ", ".join(o.get("name", "") for o in (item.options or []) if o.get("name"))
            line = f"  • {item.qty}x {item.dish_name}"
            if opt_names:
                line += f" ({opt_names})"
            item_lines.append(line)

        note_line = f"\nNote: {order.customer_note}" if order.customer_note else ""
        body = (
            f"🔔 New order {order.order_number}\n"
            f"Restaurant: {tenant_name}\n"
            f"Type: {fulfillment_label}\n"
            f"Customer: {order.customer_name or 'Anonymous'}\n"
            + "\n".join(item_lines)
            + f"\nTotal: {order.total} {order.currency}"
            + note_line
        )

        # Normalise recipient WhatsApp number
        digits = "".join(ch for ch in whatsapp_phone if ch.isdigit() or ch == "+")
        if not digits.startswith("+"):
            digits = f"+{digits}"

        to_wa = f"whatsapp:{digits}"
        from_wa = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

        payload = _urlparse.urlencode({
            "From": from_wa,
            "To": to_wa,
            "Body": body,
        }).encode("utf-8")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        import base64 as _base64
        credentials = _base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        req = _urlrequest.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with _urlrequest.urlopen(req, timeout=8):
            pass  # success

        try:
            from accounts.notifications import record_notification
            record_notification(
                channel="whatsapp", event="order.new", status="sent",
                recipient=digits, detail=tenant_name, reference=order.order_number, tenant_id=tenant_id,
            )
        except Exception:
            pass

    except Exception as exc:
        # Never fail the order — just log the issue
        _log = _logging.getLogger(__name__)
        _log.warning("Could not send new-order WhatsApp notification: %s", exc)
        try:
            from accounts.notifications import record_notification
            record_notification(
                channel="whatsapp", event="order.new", status="failed",
                detail=tenant_name, reference=getattr(order, "order_number", ""), error=str(exc), tenant_id=tenant_id,
            )
        except Exception:
            pass


def _cod_eligible(profile, customer_id):
    """True when a signed-in customer may pay cash on handover for a pickup/delivery
    order instead of prepaying from their wallet. Requires the owner to have enabled
    COD and the customer to have at least the configured number of completed & paid
    orders at this restaurant (a trusted repeat customer).
    """
    if not customer_id or not getattr(profile, "cod_enabled", False):
        return False
    try:
        threshold = max(1, int(getattr(profile, "cod_min_paid_orders", 3) or 3))
        paid = Order.objects.filter(
            customer_id=customer_id,
            status=Order.Status.COMPLETED,
            payment_status=Order.PaymentStatus.PAID,
        ).count()
        return paid >= threshold
    except Exception:
        return False


class OrderEligibilityView(APIView):
    """GET /api/order-eligibility/ — payment options for the signed-in customer on a
    pay-now (pickup/delivery) order at this restaurant. Lets the cart offer trusted
    customers a 'pay cash on handover' choice alongside wallet prepayment.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        profile = Profile.objects.filter(tenant=getattr(request, "tenant", None)).first()
        cust_id = request.session.get("customer_id")
        paid = 0
        if cust_id:
            try:
                paid = Order.objects.filter(
                    customer_id=cust_id,
                    status=Order.Status.COMPLETED,
                    payment_status=Order.PaymentStatus.PAID,
                ).count()
            except Exception:
                paid = 0
        return Response({
            "cod_enabled": bool(getattr(profile, "cod_enabled", False)),
            "cod_eligible": bool(profile and _cod_eligible(profile, cust_id)),
            "cod_min_paid_orders": int(getattr(profile, "cod_min_paid_orders", 3) or 3) if profile else 3,
            "paid_orders": paid,
        })


class PlaceOrderView(APIView):
    """POST /api/place-order/ — customer submits an in-app order.

    Pricing note: happy-hour discounts are evaluated at PLACEMENT time (the moment the
    customer submits the request), not at scheduled_for.  Advance/scheduled orders are
    prepaid at placement, so the price lock at placement time is the defensible choice —
    the discount was offered and accepted at submission, not at the future pick-up/delivery
    slot.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PlaceOrderThrottle]

    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved.", "code": "tenant_missing"}, status=status.HTTP_400_BAD_REQUEST)

        plan = getattr(tenant, "plan", None)
        if not plan or (not plan.can_whatsapp_order and not plan.can_checkout):
            return Response({"detail": "Ordering is not available on this plan.", "code": "plan_forbidden"}, status=status.HTTP_403_FORBIDDEN)

        profile = Profile.objects.filter(tenant=tenant).first()
        if profile is None:
            return Response({"detail": "Restaurant not configured.", "code": "profile_missing"}, status=status.HTTP_400_BAD_REQUEST)

        user = getattr(request, "user", None)
        can_preview = bool(user and user.is_authenticated and (
            user.is_superuser or
            getattr(user, "is_platform_admin", False) or
            (getattr(user, "tenant_id", None) == tenant.id)
        ))

        if profile.is_menu_temporarily_disabled and not can_preview:
            return Response({"detail": "Menu is temporarily unavailable.", "code": "menu_temporarily_disabled"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not profile.is_menu_published and not can_preview:
            return Response({"detail": "Menu is not published yet.", "code": "menu_unpublished"}, status=status.HTTP_403_FORBIDDEN)
        # An advance/scheduled order may be placed while the restaurant is closed right
        # now (it's for a future open slot). _validate_scheduled_for below enforces the
        # requested time falls within business hours, so this live gate is safe to skip
        # for scheduled requests.
        _wants_schedule = bool(request.data.get("scheduled_for"))
        if not can_preview and not _wants_schedule and not _is_restaurant_currently_open(profile):
            return Response(
                {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                status=status.HTTP_409_CONFLICT,
            )

        # OPS-3 contract A: idempotency-key pre-check (before serializer so a
        # retry with a valid key never fails on a stale/missing items body).
        # The SPA mints a UUIDv4 when the checkout modal opens and clears it on
        # confirmed success.  If an Order with that key already exists, return it
        # immediately without decrementing stock or charging the wallet again.
        _idem_key = str(request.data.get("idempotency_key") or "").strip()[:64] or None
        if _idem_key:
            try:
                _existing = Order.objects.filter(idempotency_key=_idem_key).first()
                if _existing is not None:
                    _existing.refresh_from_db(fields=["points_earned"])
                    return Response({
                        "order_number": _existing.order_number,
                        "status": _existing.status,
                        "total": str(_existing.total),
                        "delivery_fee": str(_existing.delivery_fee),
                        "tip_amount": str(_existing.tip_amount),
                        "wallet_amount_paid": str(_existing.wallet_amount_paid),
                        "currency": _existing.currency,
                        "estimated_ready_minutes": _existing.estimated_ready_minutes,
                        "points_earned": _existing.points_earned,
                        "loyalty_discount": str(_existing.loyalty_discount),
                        "redeemed_loyalty_points": _existing.redeemed_loyalty_points,
                        "scheduled_for": _existing.scheduled_for.isoformat() if _existing.scheduled_for else None,
                        "idempotent_replay": True,
                    }, status=status.HTTP_201_CREATED)
            except Exception:
                pass  # If the lookup itself errors, proceed with normal placement

        serializer = OrderHandoffSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        items_input = validated["items"]

        slugs = [i["slug"] for i in items_input]
        all_option_ids = [oid for i in items_input for oid in i.get("option_ids", [])]

        dishes_map = {d.slug: d for d in Dish.objects.filter(
            slug__in=slugs, is_published=True, is_available=True,
            category__is_published=True, category__is_temporarily_disabled=False,
        ).select_related("category").prefetch_related("combo_components__component")}

        missing = [s for s in slugs if s not in dishes_map]
        if missing:
            return Response({"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing}, status=status.HTTP_400_BAD_REQUEST)

        options_map = {}
        if all_option_ids:
            options_map = {o.id: o for o in DishOption.objects.filter(id__in=all_option_ids).select_related("dish")}

        # Compute active happy-hour rules ONCE for this request (placement-time lock).
        # Price is evaluated at submission time, not at scheduled_for — see class docstring.
        # We use get_all_active_hh_rules() (no time-window filter) so that tests patching
        # menu.pricing.HappyHour fully control which rules apply.  The is_active flag is
        # the owner's primary on/off switch; the start/end window governs menu-display only.
        # Graceful fallback: if HappyHour table is unavailable, skip discount entirely.
        try:
            _active_happy_hours = get_all_active_hh_rules()
        except Exception:
            _active_happy_hours = []

        # Build order items and compute total
        order_items_data = []
        _food_subtotal = Decimal("0")
        currency = "MAD"

        for item_input in items_input:
            dish = dishes_map[item_input["slug"]]
            currency = dish.currency or "MAD"
            # Apply happy-hour discount (largest percent_off wins; option price_delta unchanged).
            unit_price, _ = effective_unit_price(dish, _active_happy_hours)

            option_snapshots = []
            _invalid_oids: list[int] = []
            for oid in item_input.get("option_ids", []):
                opt = options_map.get(oid)
                _opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
                if opt is None or _opt_dish_slug != dish.slug:
                    _invalid_oids.append(oid)
                    continue
                unit_price += Decimal(str(opt.price_delta))
                option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})
            if _invalid_oids:
                return Response(
                    {
                        "detail": f"Some selected options are no longer valid for '{dish.name}'.",
                        "code": "stale_options",
                        "dish_slug": dish.slug,
                        "invalid_option_ids": _invalid_oids,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            qty = item_input["qty"]
            subtotal = unit_price * qty
            _food_subtotal += subtotal
            # Build combo snapshot (per-unit qty, not pre-multiplied)
            _combo_snapshot = [
                {"dish_id": cc.component_id, "name": cc.component.name, "qty": cc.qty}
                for cc in dish.combo_components.all()
            ]
            # Snapshot course from category at placement time (0 when category missing)
            _course_snap = int(getattr(getattr(dish, "category", None), "course", 0) or 0)
            order_items_data.append({
                "dish_slug": dish.slug,
                "dish_name": dish.name,
                "unit_price": unit_price,
                "qty": qty,
                "note": item_input.get("note", ""),
                "options": option_snapshots,
                "subtotal": subtotal,
                "combo_components": _combo_snapshot,
                "course": _course_snap,
            })

        # Collect dishes that track stock so we can decrement inside the transaction.
        # Also collect combo-component stock updates (component.qty × ordered_qty per combo item).
        _stock_updates = []  # list of (dish_pk, ordered_qty)
        _pk_to_slug = {}
        # combo component updates: list of (component_pk, total_qty_to_decrement, component_name)
        _component_stock_updates = []
        for _item_d in order_items_data:
            _d = dishes_map[_item_d["dish_slug"]]
            _pk_to_slug[_d.pk] = _d.slug
            if _d.stock_qty is not None:
                _stock_updates.append((_d.pk, _item_d["qty"]))
            # Component stock: decrement each component by (component.qty × ordered_qty)
            for _cc_snap in _item_d["combo_components"]:
                _comp_total = _cc_snap["qty"] * _item_d["qty"]
                _component_stock_updates.append(
                    (_cc_snap["dish_id"], _comp_total, _cc_snap["name"])
                )

        table_slug = (validated.get("table_slug") or "").strip()
        fulfillment_type = (validated.get("fulfillment_type") or "")
        table_label = (validated.get("table_label") or "").strip()
        if table_slug:
            # Dine-in is a restaurant-only capability; shops (retail/grocery) can't
            # take table orders. Defaults to allowed for restaurants (non-breaking).
            _caps = getattr(profile, "capabilities", None) or {}
            if not _caps.get("dine_in", True):
                return Response(
                    {"detail": "Dine-in ordering is not available for this business.",
                     "code": "dine_in_unavailable"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            fulfillment_type = Order.FulfillmentType.TABLE
            resolved_table = TableLink.objects.filter(slug=table_slug, is_active=True).first()
            if resolved_table is None:
                return Response(
                    {"detail": "Table link is unavailable.", "code": "table_unavailable"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Use DB label as authoritative source; fall back to client-supplied label
            table_label = resolved_table.label or table_label

        # Advance/scheduled order — validate the requested fulfilment time (pickup/delivery
        # only, future within the lead window, inside business hours). On success the order
        # is created as SCHEDULED (hidden from the kitchen until released) but paid now.
        _scheduled_for, _sched_err = _validate_scheduled_for(
            profile, fulfillment_type, validated.get("scheduled_for")
        )
        if _sched_err:
            _sched_messages = {
                "schedule_not_supported": "Only pickup and delivery orders can be scheduled in advance.",
                "schedule_too_soon": "Please choose a time at least 30 minutes from now.",
                "schedule_too_far": "Scheduled orders can be placed up to 14 days ahead.",
                "schedule_closed": "The restaurant is closed at that time. Please pick a time within opening hours.",
            }
            return Response(
                {"detail": _sched_messages.get(_sched_err, "That scheduled time isn't available."),
                 "code": _sched_err},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _is_scheduled = _scheduled_for is not None

        # Resolve linked customer from session
        from accounts.models import Customer as CustomerModel
        _customer_id = request.session.get("customer_id")
        _linked_customer = None
        if _customer_id:
            try:
                _linked_customer = CustomerModel.objects.get(pk=_customer_id)
            except CustomerModel.DoesNotExist:
                request.session.pop("customer_id", None)

        # Delivery orders require an authenticated, verified customer
        if fulfillment_type == Order.FulfillmentType.DELIVERY:
            if _linked_customer is None:
                return Response(
                    {"detail": "Delivery orders require a signed-in account.", "code": "auth_required"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            is_verified = _linked_customer.phone_verified or _linked_customer.email_verified or bool(_linked_customer.google_sub)
            if not is_verified:
                return Response(
                    {"detail": "Please verify your phone or email before placing a delivery order.", "code": "not_verified"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not (_linked_customer.phone or "").strip():
                return Response(
                    {
                        "detail": "Please add a phone number to your account so the delivery driver can reach you.",
                        "code": "phone_required",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        # For delivery, enrich order with customer identity; for pickup/table use payload values
        if fulfillment_type == Order.FulfillmentType.DELIVERY and _linked_customer:
            _customer_name = _linked_customer.name or validated.get("customer_name", "")
            _customer_phone = _linked_customer.phone or validated.get("customer_phone", "")
        else:
            _customer_name = validated.get("customer_name", "")
            _customer_phone = validated.get("customer_phone", "")

        # Apply delivery fee for delivery orders — distance-based when configured
        # (base + per-km from restaurant → address), else the flat fallback fee.
        _delivery_fee = Decimal("0")
        _delivery_distance_km = None
        if fulfillment_type == Order.FulfillmentType.DELIVERY:
            from tenancy.delivery_pricing import compute_delivery_fee, valid_coord
            from tenancy.routing import road_distance_km
            _dlat = validated.get("delivery_lat")
            _dlng = validated.get("delivery_lng")
            _plat = getattr(profile, "lat", None)
            _plng = getattr(profile, "lng", None)
            # Only compute distance when BOTH the restaurant and the delivery address
            # have a valid, real coordinate. Missing / (0,0) / out-of-range coords →
            # distance unknown → flat-fee fallback, never a false "outside area".
            if valid_coord(_plat, _plng) and valid_coord(_dlat, _dlng):
                # Road distance (haversine × factor, or a real OSRM route when
                # DELIVERY_OSRM_URL is set) — closer to what the driver drives.
                _delivery_distance_km = road_distance_km(_plat, _plng, _dlat, _dlng)
            _pricing = compute_delivery_fee(
                profile, distance_km=_delivery_distance_km, food_subtotal=_food_subtotal
            )
            if _pricing["out_of_range"]:
                return Response(
                    {
                        "detail": "This address is outside the restaurant's delivery area.",
                        "code": "delivery_out_of_range",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            _delivery_fee = _pricing["fee"]

        # Apply promotion — either by customer-supplied code or best auto-applied promo.
        # Evaluate the promo window in the TENANT's local wall-clock time (a promo
        # "Tue 14:00–16:00" means tenant-local), not the server's — see menu.promos.
        _promo_now_local = _profile_now(profile)
        _best_promo = None
        _promo_discount = Decimal("0")
        _promo_code_input = str(request.data.get("promo_code") or "").strip().upper()
        if _promo_code_input:
            # Code-based lookup: find an active promotion matching this code
            try:
                _code_promo = Promotion.objects.get(
                    code__iexact=_promo_code_input,
                    is_active=True,
                )
                _code_valid = True
                if _code_promo.max_uses is not None and _code_promo.use_count >= _code_promo.max_uses:
                    _code_valid = False
                if Decimal(str(_code_promo.min_order_amount or "0")) > _food_subtotal:
                    _code_valid = False
                if not _is_promo_active_now(_code_promo, now_local=_promo_now_local):
                    _code_valid = False
                if _code_valid:
                    _best_promo = _code_promo
                    _promo_discount = _compute_promo_discount(_code_promo, _food_subtotal, _delivery_fee)
                else:
                    return Response(
                        {"detail": "Promo code is not valid for this order.", "code": "promo_invalid"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Promotion.DoesNotExist:
                return Response(
                    {"detail": "Promo code not found.", "code": "promo_not_found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Auto-apply best currently-active promotion (code-based promos are excluded)
            for _promo in Promotion.objects.filter(is_active=True, code=""):
                if _promo.max_uses is not None and _promo.use_count >= _promo.max_uses:
                    continue
                if Decimal(str(_promo.min_order_amount or "0")) > _food_subtotal:
                    continue
                if not _is_promo_active_now(_promo, now_local=_promo_now_local):
                    continue
                _d = _compute_promo_discount(_promo, _food_subtotal, _delivery_fee)
                if _d > _promo_discount:
                    _promo_discount = _d
                    _best_promo = _promo

        total = max(Decimal("0"), _food_subtotal + _delivery_fee - _promo_discount)

        # ── Loyalty redemption at checkout ──────────────────────────────────────
        # A signed-in customer may spend accumulated points for an instant discount on
        # this order (separate from the account-page redeem→wallet flow). Sized here on
        # the pre-tip charge; the points are debited atomically inside the order
        # transaction below (conditional UPDATE → rolls the order back if they're short).
        _loyalty_discount = Decimal("0")
        _loyalty_points_spent = 0
        try:
            _redeem_points = int(request.data.get("redeem_points", 0) or 0)
        except (TypeError, ValueError):
            _redeem_points = 0
        if _redeem_points > 0:
            if _linked_customer is None:
                return Response({"detail": "Sign in to redeem points.", "code": "auth_required"},
                                status=status.HTTP_403_FORBIDDEN)
            _lc = LoyaltyConfig.objects.filter(enabled=True).first()
            _loyalty_discount, _loyalty_points_spent, _loy_err = _size_loyalty_redemption(
                _lc,
                getattr(_linked_customer, "loyalty_points", 0),
                _redeem_points,
                total,
            )
            if _loy_err:
                _loy_msgs = {
                    "loyalty_disabled": "Loyalty isn't available right now.",
                    "loyalty_insufficient_points": "You don't have that many points.",
                    "loyalty_below_threshold": f"Redeem at least {getattr(_lc, 'redeem_threshold', 0)} points.",
                }
                return Response({"detail": _loy_msgs.get(_loy_err, "Couldn't redeem your points."), "code": _loy_err},
                                status=status.HTTP_400_BAD_REQUEST)
            total = max(Decimal("0"), total - _loyalty_discount)

        # Tip — optional gratuity; must be non-negative and capped at a sane ceiling
        _tip_raw = request.data.get("tip_amount", 0)
        try:
            _tip_amount = Decimal(str(_tip_raw)).quantize(Decimal("0.01"))
        except Exception:
            _tip_amount = Decimal("0")
        if _tip_amount < Decimal("0"):
            _tip_amount = Decimal("0")
        # Sanity cap: tip ≤ 100% of food subtotal (prevents fat-finger runaway amounts)
        if _food_subtotal > Decimal("0") and _tip_amount > _food_subtotal:
            _tip_amount = _food_subtotal
        total = total + _tip_amount

        # Pickup & delivery are pay-now: for now the bill must be settled in full from
        # the customer's wallet at checkout (the only online method today). Dine-in
        # (table) stays an open tab paid at the end, so it is exempt. A free order
        # (total 0) needs no payment.
        #
        # Staff-created orders (a waiter taking a phone/counter order via the new-order
        # screen) are EXEMPT: the waiter collects cash/card in person and settles via
        # the Settle action, so they must not be blocked by the customer-wallet rule.
        from accounts.models import User as _UPrepay
        _ru_prepay = getattr(request, "user", None)
        _is_staff_order = bool(
            _ru_prepay is not None
            and getattr(_ru_prepay, "is_authenticated", False)
            and getattr(_ru_prepay, "role", None) in (_UPrepay.Roles.TENANT_OWNER, _UPrepay.Roles.TENANT_STAFF)
        )
        _requires_prepay = (
            not _is_staff_order
            and fulfillment_type in (Order.FulfillmentType.PICKUP, Order.FulfillmentType.DELIVERY)
        )
        # Trusted-customer cash-on-handover: a repeat customer (COD enabled + enough
        # completed/paid orders) may choose to pay cash to the staff/driver instead of
        # prepaying from their wallet. Such orders are created UNPAID and settled at
        # handover via the Settle action.
        _cod_order = False
        if _requires_prepay and total > Decimal("0"):
            if _linked_customer is None:
                return Response(
                    {"detail": "Sign in and top up your wallet to place a pickup or delivery order.",
                     "code": "auth_required"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            _payment_method = str(request.data.get("payment_method") or "").strip().lower()
            # Advance/scheduled orders are prepaid at placement (no cash-on-handover) so
            # the slot is genuinely committed and no-shows can't tie up stock unpaid.
            if _payment_method == "cash" and not _is_scheduled and _cod_eligible(profile, _linked_customer.id):
                _cod_order = True
            else:
                _wallet_avail = Decimal(str(_linked_customer.wallet_balance or "0"))
                if _wallet_avail < total:
                    return Response(
                        {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                         "code": "wallet_insufficient",
                         "balance": str(_wallet_avail), "amount_due": str(total)},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )

        # Wallet payment — pickup/delivery prepay by wallet (enforced above) UNLESS the
        # customer opted into trusted cash-on-handover; dine-in customers may opt in.
        _use_wallet = ((_requires_prepay and not _cod_order) or bool(request.data.get("use_wallet"))) and _linked_customer is not None
        _wallet_deduction = Decimal("0")
        if _use_wallet:
            _available = Decimal(str(_linked_customer.wallet_balance or "0"))
            _wallet_deduction = min(_available, total)
            if _wallet_deduction <= Decimal("0"):
                _use_wallet = False
                _wallet_deduction = Decimal("0")

        class _PrepayUnpaid(Exception):
            """Raised inside the atomic block when a pickup/delivery order can't be
            fully prepaid from the wallet — rolls back any partial debit + the order."""

        class _OutOfStock(Exception):
            """Raised inside the atomic block when a dish's stock is exhausted."""
            def __init__(self, slug_or_name):
                self.slug = slug_or_name

        class _LoyaltyShort(Exception):
            """Raised inside the atomic block when the customer no longer has enough
            loyalty points to cover the redemption — rolls the whole order back."""

        class _PromoCapped(Exception):
            """Raised inside the atomic block when a code-based promo's max_uses cap is
            hit concurrently (bounded counter returned 0 rows).  Rolls back the order and
            returns a 400 so the customer knows to retry without the code.

            OPS-4 F: Atomic bounded counter closes the max_uses overspend race.
            Pre-check (use_count >= max_uses) outside the lock is not safe for concurrent
            checkouts — both can pass the pre-check and then both increment past the cap.
            Fix: Promotion.objects.filter(pk=..., use_count__lt=max_uses).update(F+1) and
            treat a 0-rows result as cap-reached inside the atomic transaction.
            """

        class _CurrencyUnsupported(Exception):
            """R16 guard: refuse to debit the MAD wallet against a non-MAD order.

            The wallet balance is a single MAD scalar; this inline debit writes a
            WalletTransaction at an implicit 1:1 MAD rate, so debiting a non-MAD order
            would silently corrupt per-currency reconciliation. NO-OP today (every order
            is MAD — currency derives from dish.currency), so this never fires in normal
            operation — it is a future-proofing safety net handled below as a 400
            currency_unsupported. Multi-currency wallet support is a deferred decision."""

        try:
            with transaction.atomic():
                # --- Stock check + decrement (before creating the order so a failed
                #     stock check never leaves a dangling order row) ---
                # Lock combo-dish stock AND component stock in a single query so we
                # can validate and decrement them atomically in the same block.
                _all_stock_pks = [pk for pk, _ in _stock_updates]
                _comp_pk_to_name = {}
                _comp_stock_agg: dict[int, int] = {}  # component_pk → total qty to decrement
                for _cpk, _cqty, _cname in _component_stock_updates:
                    _comp_stock_agg[_cpk] = _comp_stock_agg.get(_cpk, 0) + _cqty
                    _comp_pk_to_name[_cpk] = _cname
                _all_stock_pks += [pk for pk in _comp_stock_agg if pk not in _all_stock_pks]

                if _all_stock_pks:
                    _locked_dishes = {
                        d.pk: d
                        for d in Dish.objects.select_for_update().filter(pk__in=_all_stock_pks)
                    }
                else:
                    _locked_dishes = {}

                if _stock_updates:
                    # Validate sufficient stock for every combo-dish in this order
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked_dishes.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered_qty:
                            raise _OutOfStock(_pk_to_slug.get(_dish_pk, ""))
                    # Atomically decrement; mark sold-out when stock reaches zero.
                    # stock_auto_zeroed=True marks automatic decrements so the 5am
                    # auto_reset_availability cron can distinguish them from deliberate
                    # owner-zeroed dishes.
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked_dishes.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None:
                            _new_qty = max(0, _ld.stock_qty - _ordered_qty)
                            if _new_qty == 0:
                                Dish.objects.filter(pk=_dish_pk).update(
                                    stock_qty=0, is_available=False, stock_auto_zeroed=True
                                )
                            else:
                                Dish.objects.filter(pk=_dish_pk).update(stock_qty=_new_qty)

                # Component stock: validate then decrement each component
                if _comp_stock_agg:
                    for _cpk, _cqty in _comp_stock_agg.items():
                        _ld = _locked_dishes.get(_cpk)
                        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _cqty:
                            raise _OutOfStock(_comp_pk_to_name.get(_cpk, ""))
                    for _cpk, _cqty in _comp_stock_agg.items():
                        _ld = _locked_dishes.get(_cpk)
                        if _ld and _ld.stock_qty is not None:
                            _cnew = max(0, _ld.stock_qty - _cqty)
                            if _cnew == 0:
                                Dish.objects.filter(pk=_cpk).update(
                                    stock_qty=0, is_available=False, stock_auto_zeroed=True
                                )
                            else:
                                Dish.objects.filter(pk=_cpk).update(stock_qty=_cnew)

                # OPS-4 F: Atomic bounded promo counter — must run BEFORE Order.create() so
                # a failed increment never leaves a discounted order in the DB.
                #
                # max_uses=None → unlimited → always safe to increment unconditionally.
                # max_uses>0    → bounded:   use filter(use_count__lt=max_uses) + F()+1;
                #                            0 rows = cap already reached concurrently.
                #   Code promo (customer explicitly chose it): reject order → 400.
                #   Auto promo (best available): strip the discount from this order;
                #                               the order still places at full price.
                if _best_promo is not None:
                    if _best_promo.max_uses is not None:
                        # Bounded update — safe under concurrent checkouts
                        _promo_rows = Promotion.objects.filter(
                            pk=_best_promo.pk,
                            use_count__lt=_best_promo.max_uses,
                        ).update(use_count=models.F("use_count") + 1)
                        if _promo_rows:
                            # The increment succeeded; recompute the denorm ONLY when this
                            # redemption JUST hit the cap. A capped promo can no longer be
                            # redeemed and must drop out of the marketplace badge — but
                            # .update() fires no signal, so the denorm won't refresh on its
                            # own. Gate on the cap-crossing so the common below-cap
                            # redemption does NOT do cross-schema work + a global list-cache
                            # bust on the order hot path. Read the post-increment count from
                            # the DB (read-your-writes inside this txn) rather than the
                            # in-memory use_count, which can be stale-low under concurrent
                            # checkouts and would then MISS the crossing. Best-effort —
                            # never break checkout; lazy import avoids the menu→accounts
                            # cycle at module load.
                            try:
                                _best_promo.refresh_from_db(fields=["use_count"])
                                if _best_promo.use_count >= _best_promo.max_uses:
                                    from django.db import connection as _cap_conn
                                    from menu.promos_denorm import recompute_tenant_promos
                                    recompute_tenant_promos(getattr(_cap_conn, "tenant", None))
                            except Exception:
                                pass
                        if not _promo_rows:
                            if _promo_code_input:
                                # Explicit code: cap hit concurrently → reject
                                raise _PromoCapped()
                            else:
                                # Auto promo: strip discount, re-check wallet
                                total = max(Decimal("0"), total + _promo_discount - _tip_amount)
                                total = total + _tip_amount  # re-apply tip
                                _promo_discount = Decimal("0")
                                _best_promo = None
                                # Wallet deduction must not exceed the corrected total
                                if _use_wallet:
                                    _wallet_deduction = min(_wallet_deduction, total)
                                    if _requires_prepay and not _cod_order:
                                        _available_now = Decimal(str(
                                            getattr(_linked_customer, "wallet_balance", "0") or "0"
                                        ))
                                        if _available_now < total:
                                            raise _PrepayUnpaid()
                    else:
                        # max_uses is None → unlimited → no cap to enforce
                        Promotion.objects.filter(pk=_best_promo.pk).update(
                            use_count=models.F("use_count") + 1
                        )

                order_number = _generate_order_number()
                # Attribute waiter-created orders to the staff member who took them. The
                # waiter app posts here authenticated as tenant staff/owner; a customer
                # checkout is anonymous, so those stay unattributed until a staff advances.
                _staff_creator_id = None
                _ru = getattr(request, "user", None)
                if _ru is not None and getattr(_ru, "is_authenticated", False) and getattr(_ru, "id", None):
                    from accounts.models import User as _U
                    if getattr(_ru, "role", None) in {_U.Roles.TENANT_OWNER, _U.Roles.TENANT_STAFF}:
                        _staff_creator_id = _ru.id

                order = Order.objects.create(
                    order_number=order_number,
                    status=Order.Status.SCHEDULED if _is_scheduled else Order.Status.PENDING,
                    scheduled_for=_scheduled_for,
                    handled_by_user_id=_staff_creator_id,
                    customer=_linked_customer,
                    customer_name=_customer_name,
                    customer_phone=_customer_phone,
                    customer_note=validated.get("customer_note", ""),
                    fulfillment_type=fulfillment_type,
                    table_label=table_label,
                    table_slug=table_slug,
                    delivery_address=validated.get("delivery_address", ""),
                    delivery_location_url=validated.get("delivery_location_url", ""),
                    delivery_lat=validated.get("delivery_lat"),
                    delivery_lng=validated.get("delivery_lng"),
                    delivery_code=(_generate_delivery_code() if fulfillment_type == Order.FulfillmentType.DELIVERY else ""),
                    total=total,
                    delivery_fee=_delivery_fee,
                    tip_amount=_tip_amount,
                    currency=currency,
                    promotion_discount=_promo_discount,
                    applied_promotion_name=_best_promo.name if _best_promo else "",
                    loyalty_discount=_loyalty_discount,
                    redeemed_loyalty_points=(_loyalty_points_spent or None),
                    idempotency_key=_idem_key,
                )

                # Debit redeemed loyalty points atomically. The conditional UPDATE only
                # succeeds if the balance still covers it — otherwise we roll the order
                # back rather than grant a discount the customer can't pay for in points.
                if _loyalty_points_spent > 0 and _linked_customer is not None:
                    from accounts.models import Customer as _CustL
                    _ok = _CustL.objects.filter(
                        pk=_linked_customer.pk,
                        loyalty_points__gte=_loyalty_points_spent,
                    ).update(loyalty_points=models.F("loyalty_points") - _loyalty_points_spent)
                    if not _ok:
                        raise _LoyaltyShort()
                for item_data in order_items_data:
                    OrderItem.objects.create(order=order, **item_data)

                # (Promo use_count increment was performed before Order.create() — see OPS-4 F.)

                # Deduct wallet balance (select_for_update prevents race conditions)
                _paid_by_wallet = Decimal("0")
                if _use_wallet and _wallet_deduction > Decimal("0"):
                    # R16 guard (MAD-only safety net): the wallet balance is a single MAD
                    # scalar and the WalletTransaction below is written at an implicit 1:1
                    # MAD rate. Refuse to debit a non-MAD order so per-currency
                    # reconciliation can never be silently corrupted. NO-OP today — every
                    # order is MAD (currency derives from dish.currency above) — purely a
                    # future-proofing guard; multi-currency wallet support is deferred.
                    if (currency or "MAD").upper() != "MAD":
                        raise _CurrencyUnsupported()
                    from accounts.wallet_service import debit_wallet as _debit_wallet
                    from accounts.models import WalletTransaction as _WTM
                    from django.db import connection as _dbc_orderpay
                    _wallet_tx = _debit_wallet(
                        _linked_customer.pk,
                        _wallet_deduction,
                        tx_type=_WTM.Type.PAYMENT,
                        idempotency_key=f"orderpay_checkout:{_dbc_orderpay.schema_name}:{order.id}",
                        reference=order.order_number,
                        tenant_id=tenant.id,
                        allow_partial=True,
                    )
                    _actual = _wallet_tx.amount if _wallet_tx is not None else Decimal("0")
                    if _actual > Decimal("0"):
                        order.wallet_amount_paid = _actual
                        order.save(update_fields=["wallet_amount_paid"])
                        _paid_by_wallet = _actual

                # Settle payment state. An order is PAID once wallet credits (or a
                # zero total) fully cover it; otherwise it stays UNPAID. Pickup &
                # delivery are expected to collect the balance up front (cash/card
                # at handover); dine-in (table) settles the open tab when leaving.
                if total <= Decimal("0") or _paid_by_wallet >= total:
                    order.payment_status = Order.PaymentStatus.PAID
                    order.paid_at = timezone.now()
                    order.save(update_fields=["payment_status", "paid_at"])

                # Pay-now safety net: a pickup/delivery order that wasn't fully settled
                # (e.g. balance dropped between the pre-check and this locked debit) is
                # rolled back rather than created unpaid. Trusted cash-on-handover orders
                # are intentionally created unpaid, so they're exempt.
                if _requires_prepay and not _cod_order and order.payment_status != Order.PaymentStatus.PAID:
                    raise _PrepayUnpaid()

                # Award loyalty points to linked customer (if programme is active)
                try:
                    _loyalty_cfg = LoyaltyConfig.objects.filter(enabled=True).first()
                    if _loyalty_cfg and _linked_customer is not None:
                        _pts = int(float(_food_subtotal) * int(_loyalty_cfg.points_per_unit))
                        if _pts > 0:
                            from accounts.models import Customer as _CustM2
                            _CustM2.objects.filter(pk=_linked_customer.pk).update(
                                loyalty_points=models.F("loyalty_points") + _pts
                            )
                            Order.objects.filter(pk=order.pk).update(points_earned=_pts)
                except Exception:
                    pass  # Never fail the order due to loyalty errors

                # Award referral reward on referee's first paid order
                try:
                    if (
                        getattr(profile, "referral_enabled", False)
                        and _linked_customer is not None
                        and _linked_customer.referred_by_id is not None
                        and not _linked_customer.referral_reward_given
                    ):
                        from accounts.models import Customer as _CustRef
                        _ref_pts = int(getattr(profile, "referral_reward_points", 100) or 100)
                        if _ref_pts > 0:
                            # Credit the referee (this customer)
                            _CustRef.objects.filter(pk=_linked_customer.pk).update(
                                loyalty_points=models.F("loyalty_points") + _ref_pts,
                                referral_reward_given=True,
                            )
                            # Credit the referrer
                            _CustRef.objects.filter(pk=_linked_customer.referred_by_id).update(
                                loyalty_points=models.F("loyalty_points") + _ref_pts,
                            )
                except Exception:
                    pass  # Never fail the order due to referral errors

        except _OutOfStock as _e:
            return Response(
                {"detail": "Item sold out.", "code": "items_unavailable", "slugs": [_e.slug]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except _CurrencyUnsupported:
            # R16 guard: non-MAD order reached the wallet-debit chokepoint. NO-OP today
            # (every order is MAD); a clear, non-money-mutating 400 so the MAD ledger is
            # never debited at an implicit 1:1 rate for a foreign-currency order.
            return Response(
                {"detail": "Wallet payment is only available for orders priced in MAD.",
                 "code": "currency_unsupported"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except _PrepayUnpaid:
            return Response(
                {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                 "code": "wallet_insufficient"},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except _LoyaltyShort:
            return Response(
                {"detail": "Your loyalty points balance changed — please review and try again.",
                 "code": "loyalty_insufficient_points"},
                status=status.HTTP_409_CONFLICT,
            )
        except _PromoCapped:
            # OPS-4 F: Bounded promo counter returned 0 rows — the cap was reached
            # concurrently by another checkout.  Match the existing "promo invalid"
            # contract: return 400 so the customer knows to try without the code.
            return Response(
                {"detail": "Promo code is no longer available (usage limit reached).",
                 "code": "promo_capped"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            # Two cases:
            # 1. Two concurrent requests generated the same order_number (very rare).
            #    Return 503 so the client can retry.
            # 2. Two concurrent requests raced on the same idempotency_key — the DB
            #    unique constraint fired.  Re-fetch the winner and return it as a
            #    successful idempotent replay (same as the pre-check path above).
            if _idem_key:
                try:
                    _race_winner = Order.objects.filter(idempotency_key=_idem_key).first()
                    if _race_winner is not None:
                        _race_winner.refresh_from_db(fields=["points_earned"])
                        return Response({
                            "order_number": _race_winner.order_number,
                            "status": _race_winner.status,
                            "total": str(_race_winner.total),
                            "delivery_fee": str(_race_winner.delivery_fee),
                            "tip_amount": str(_race_winner.tip_amount),
                            "wallet_amount_paid": str(_race_winner.wallet_amount_paid),
                            "currency": _race_winner.currency,
                            "estimated_ready_minutes": _race_winner.estimated_ready_minutes,
                            "points_earned": _race_winner.points_earned,
                            "loyalty_discount": str(_race_winner.loyalty_discount),
                            "redeemed_loyalty_points": _race_winner.redeemed_loyalty_points,
                            "scheduled_for": _race_winner.scheduled_for.isoformat() if _race_winner.scheduled_for else None,
                            "idempotent_replay": True,
                        }, status=status.HTTP_201_CREATED)
                except Exception:
                    pass
            return Response(
                {"detail": "Order could not be placed due to a conflict. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except RuntimeError:
            # _generate_order_number() exhausted 10 candidates — astronomically
            # unlikely under normal load but must never surface as an unhandled 500.
            return Response(
                {"detail": "Order could not be placed. Please try again.", "code": "order_number_exhausted"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Platform delivery: spawn a searching driver job (opt-in per restaurant).
        # Best-effort and post-commit — a hiccup here must never affect the placed order.
        # Scheduled orders skip dispatch/notifications now — they fire at release time.
        if not _is_scheduled and fulfillment_type == Order.FulfillmentType.DELIVERY and getattr(profile, "platform_delivery_enabled", False):
            try:
                from accounts.models import DeliveryJob as _DJob
                from tenancy.delivery_pricing import split_delivery_fee as _split_fee
                # Split the fee into driver payout + platform cut (default 0% → driver
                # keeps 100%); snapshot both on the job for auditable earnings.
                _dsplit = _split_fee(profile, _delivery_fee)
                _job = _DJob.objects.create(
                    tenant_id=tenant.id,
                    order_number=order.order_number,
                    status=_DJob.Status.SEARCHING,
                    pickup_address=(getattr(profile, "address", "") or "")[:200],
                    pickup_lat=getattr(profile, "lat", None),
                    pickup_lng=getattr(profile, "lng", None),
                    delivery_address=(order.delivery_address or "")[:200],
                    delivery_lat=order.delivery_lat,
                    delivery_lng=order.delivery_lng,
                    delivery_fee=_delivery_fee,
                    driver_payout=_dsplit["driver_payout"],
                    platform_commission=_dsplit["platform_commission"],
                    delivery_commission_rate_applied=_dsplit["commission_pct"],
                    business_type=getattr(profile, "business_type", "restaurant") or "restaurant",
                )
                # Ranked dispatch: offer to the nearest free driver first, cascading
                # to the next on decline/timeout, falling back to the open pool.
                from accounts.dispatch import start_dispatch
                start_dispatch(_job)
            except Exception:
                pass  # never fail the order response if job creation hiccups

        # Send WhatsApp notification to the restaurant (truly non-blocking daemon thread).
        # The order is already committed — a slow/failed Twilio call must never delay
        # the customer-facing 201 response.
        _wa_number = (getattr(profile, "whatsapp", "") or getattr(profile, "phone", "") or "").strip()
        if _wa_number and not _is_scheduled:
            from accounts.tasks import enqueue as _enqueue_task, whatsapp_new_order as _wa_task
            _enqueue_task(
                _wa_task, getattr(tenant, "schema_name", ""), order.id,
                getattr(tenant, "name", ""), _wa_number, getattr(tenant, "id", None),
            )

        # Send Web Push notification + WS ping to subscribed owner/staff (daemon thread).
        # Scheduled orders skip this now — the release sweep fires it at the right time.
        if not _is_scheduled:
            try:
                from django.db import connection as _db_conn
                from .push import push_new_order as _push_new_order
                _push_new_order(
                    schema_name=_db_conn.tenant.schema_name,
                    order_number=order.order_number,
                    customer_name=order.customer_name or "",
                    total=str(order.total),
                    currency=order.currency,
                )
            except Exception:
                pass  # Never fail the order response due to push errors

            # Real-time ping to connected owner/staff sockets (no-op if WS not configured).
            # Low-sensitivity signal only — clients refetch order details over the
            # authenticated HTTP API.
            try:
                from django.db import connection as _ws_conn
                from realtime.broadcast import broadcast as _ws_broadcast
                _ws_broadcast(
                    _ws_conn.tenant.schema_name, "owner", "order.new",
                    {"order_number": order.order_number},
                )
            except Exception:
                pass

        order.refresh_from_db(fields=["points_earned"])
        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "tip_amount": str(order.tip_amount),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "points_earned": order.points_earned,
            "loyalty_discount": str(order.loyalty_discount),
            "redeemed_loyalty_points": order.redeemed_loyalty_points,
            "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
        }, status=status.HTTP_201_CREATED)


class CustomerOrderStatusView(APIView):
    """GET /api/order-status/<order_number>/ — customer polls order status."""
    permission_classes = [AllowAny]

    def get(self, request, order_number, *args, **kwargs):
        order_number = (order_number or "").strip().upper()
        order = (
            Order.objects
            .filter(order_number=order_number)
            .prefetch_related("items")
            .select_related("rating")
            .first()
        )
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        items = [
            {
                "dish_slug": item.dish_slug,
                "dish_name": item.dish_name,
                "qty": item.qty,
                "unit_price": str(item.unit_price),
                "subtotal": str(item.subtotal),
                "currency": order.currency,
                "options": item.options,
                "note": item.note,
                "is_voided": item.is_voided,
                "combo_components": item.combo_components,
            }
            for item in order.items.all()
        ]

        # Expose rating state so the frontend can show the prompt for completed
        # orders that haven't been rated yet.
        existing_rating = getattr(order, "rating", None)
        rating_data = None
        if existing_rating is not None:
            rating_data = {
                "score": existing_rating.score,
                "comment": existing_rating.comment,
                "owner_reply": existing_rating.owner_reply or "",
                "owner_reply_at": existing_rating.owner_reply_at.isoformat() if existing_rating.owner_reply_at else None,
            }

        # Restaurant's trust rating of this customer (owner→customer). This is
        # revealed ONLY to the authenticated customer who owns this order — the
        # endpoint is AllowAny, so leaking it to anyone who guesses an order
        # number would expose private feedback. We require the session customer
        # to match the order's linked customer.
        restaurant_feedback = None
        try:
            session_customer_id = request.session.get("customer_id")
        except Exception:
            session_customer_id = None
        if order.customer_id and session_customer_id:
            try:
                same_customer = int(session_customer_id) == int(order.customer_id)
            except (TypeError, ValueError):
                same_customer = False
            if same_customer:
                _tenant = getattr(request, "tenant", None)
                _tenant_id = _tenant.id if _tenant else 0
                try:
                    from accounts.models import CustomerRating as _CR
                    _cr = (
                        _CR.objects
                        .filter(
                            customer_id=order.customer_id,
                            tenant_id=_tenant_id,
                            order_number=order.order_number,
                        )
                        .order_by("-created_at")
                        .first()
                    )
                    if _cr is not None:
                        restaurant_feedback = {
                            "score": _cr.score,
                            "note": _cr.note,
                            "created_at": _cr.created_at.isoformat(),
                        }
                except Exception:
                    restaurant_feedback = None

        # Pull the receipt message + VAT settings from the tenant profile (safe fallbacks).
        receipt_message = ""
        vat_fields = {}
        try:
            _profile = request.tenant.profile
            receipt_message = getattr(_profile, "receipt_message", "") or ""
            vat_fields = order_vat_fields(
                order, getattr(_profile, "vat_rate", 0), getattr(_profile, "vat_label", "") or ""
            )
        except Exception:
            pass

        # Wallet self-pay — offer the signed-in order owner a one-tap "pay from
        # wallet" while the bill is still open (e.g. a dine-in tab). We surface
        # their balance + the amount due so the UI can show/disable the button.
        can_pay_with_wallet = False
        wallet_balance = None
        try:
            order_outstanding = Decimal(str(order.total or "0")) - Decimal(str(order.wallet_amount_paid or "0"))
        except Exception:
            order_outstanding = Decimal("0")
        if (
            session_customer_id and order.customer_id
            and order.payment_status != Order.PaymentStatus.PAID
            and order.status != Order.Status.CANCELLED
            and order_outstanding > Decimal("0")
        ):
            try:
                if int(session_customer_id) == int(order.customer_id):
                    from accounts.models import Customer as _Cust
                    _c = _Cust.objects.filter(pk=order.customer_id).only("wallet_balance").first()
                    if _c is not None:
                        wallet_balance = str(_c.wallet_balance)
                        can_pay_with_wallet = True
            except Exception:
                pass  # balance lookup is best-effort; never breaks order status

        # Delivery tracking — the order owner can see + contact their assigned driver
        # (name, phone, vehicle, rating) and watch the live position. Owner-gated like
        # the delivery code, since this endpoint is AllowAny (delivery orders always
        # have a signed-in owner, so this never hides a driver from a legit customer).
        delivery_block = None
        if (
            order.fulfillment_type == Order.FulfillmentType.DELIVERY
            and session_customer_id and order.customer_id
            and str(session_customer_id) == str(order.customer_id)
        ):
            try:
                _dtenant = getattr(request, "tenant", None)
                _dtid = _dtenant.id if _dtenant else 0
                from accounts.models import DeliveryJob as _DJob
                from accounts.views import _serialize_delivery_job as _ser_job
                _djob = (
                    _DJob.objects.select_related("driver")
                    .filter(tenant_id=_dtid, order_number=order.order_number)
                    .first()
                )
                if _djob is not None:
                    delivery_block = _ser_job(_djob, include_driver_position=True)
            except Exception:
                delivery_block = None

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "delivery": delivery_block,
            "table_label": order.table_label,
            "customer_name": order.customer_name,
            # NOTE: customer_phone is intentionally omitted — this endpoint is
            # AllowAny so exposing phone numbers would let anyone enumerate PII
            # by guessing order numbers (ORD-XXXXXX ≈ 16M space).
            "delivery_address": order.delivery_address,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "loyalty_discount": str(order.loyalty_discount),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            # Payment state — lets the customer page show "Paid" vs "Pay at the
            # table when you leave" (dine-in) / "Payment due" (pickup/delivery).
            "payment_status": order.payment_status,
            "requires_prepayment": order.requires_prepayment,
            # Self-cancel affordance — only for the signed-in owner of an early
            # pickup/delivery order (server-driven so the UI button matches the rule).
            "can_cancel": bool(
                _customer_can_cancel(order)
                and session_customer_id and order.customer_id
                and str(session_customer_id) == str(order.customer_id)
            ),
            # Wallet self-pay affordance (only for the signed-in order owner).
            "can_pay_with_wallet": can_pay_with_wallet,
            "wallet_balance": wallet_balance,
            "amount_due": str(order_outstanding if order_outstanding > Decimal("0") else Decimal("0.00")),
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            # Advance/scheduled fulfilment time (ISO 8601, null for ASAP orders).
            "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
            # Proof-of-delivery code — shown ONLY to the signed-in owner of an active
            # delivery order (they read it to the driver). Gated so guessing an order
            # number can't leak it.
            "delivery_code": (
                order.delivery_code
                if (order.delivery_code
                    and order.fulfillment_type == Order.FulfillmentType.DELIVERY
                    and order.status not in (Order.Status.COMPLETED, Order.Status.CANCELLED)
                    and session_customer_id and order.customer_id
                    and str(session_customer_id) == str(order.customer_id))
                else None
            ),
            "items_count": sum(i["qty"] for i in items),
            "items": items,
            "created_at": order.created_at.isoformat(),
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
            # Rating state — frontend shows 1–5 star prompt when status=completed and has_rating=false
            "has_rating": existing_rating is not None,
            "rating": rating_data,
            # Loyalty points credited to the customer's account for this order.
            # Displayed as a celebration panel when status=completed and points>0.
            "points_earned": order.points_earned,
            # Restaurant's feedback about this customer — only populated for the
            # signed-in customer who owns this order (gated above).
            "restaurant_feedback": restaurant_feedback,
            # Thank-you message written by the restaurant owner (shown for confirmed/ready/completed).
            "receipt_message": receipt_message,
            # VAT breakdown (empty/zero unless the owner set a VAT rate; prices are VAT-inclusive).
            **vat_fields,
        })


class CustomerOrderCancelView(APIView):
    """POST /api/order-status/<order_number>/cancel/ — the signed-in customer cancels
    their OWN early pickup/delivery order. Refunds any wallet payment and returns reserved
    stock. Session ownership is required; dine-in and already-started orders are refused.
    """
    permission_classes = [AllowAny]

    def post(self, request, order_number, *args, **kwargs):
        order_number = (order_number or "").strip().upper()
        order = Order.objects.filter(order_number=order_number).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        session_customer_id = request.session.get("customer_id")
        try:
            owns = bool(session_customer_id) and bool(order.customer_id) and int(session_customer_id) == int(order.customer_id)
        except (TypeError, ValueError):
            owns = False
        if not owns:
            return Response({"detail": "Sign in to cancel this order.", "code": "not_owner"}, status=status.HTTP_403_FORBIDDEN)

        if order.status == Order.Status.CANCELLED:
            return Response({"status": order.status, "payment_status": order.payment_status})
        if not _customer_can_cancel(order):
            return Response(
                {"detail": "This order can no longer be cancelled — please contact the restaurant.",
                 "code": "not_cancellable"},
                status=status.HTTP_409_CONFLICT,
            )

        from django.db import transaction as _tx
        _cancel_tenant = getattr(request, "tenant", None)
        _cancel_tenant_id = _cancel_tenant.id if _cancel_tenant else None
        with _tx.atomic():
            order.status = Order.Status.CANCELLED
            order.status_updated_at = timezone.now()
            order.save(update_fields=["status", "status_updated_at", "updated_at"])
            _refund_wallet_for_cancelled_order(order, tenant_id=_cancel_tenant_id)  # idempotent wallet credit
            _reverse_loyalty_for_cancelled_order(order)  # claw back earned / restore spent points
            _restock_cancelled_order(order)

        # Stand down any assigned delivery driver (public-schema job; best-effort).
        tenant = getattr(request, "tenant", None)
        if tenant:
            try:
                from accounts.delivery_service import cancel_delivery_job_for_order
                cancel_delivery_job_for_order(tenant.id, order.order_number)
            except Exception:
                pass

        _broadcast_order_change(order)  # live-update the tracking page
        if tenant:
            try:
                _send_order_status_email(order, tenant, Order.Status.CANCELLED)
            except Exception:
                pass
        return Response({"status": order.status, "payment_status": order.payment_status})


class CustomerOrdersByPhoneView(APIView):
    """GET /api/orders/by-phone/?phone=<number> — unauthenticated guest lookup.

    Returns a brief list (max 20, last 90 days) of orders matching the given
    phone number at this tenant.  Only safe, non-PII fields are returned —
    the full phone number is *not* echoed back.  A simple IP-based rate-limit
    (10 requests / minute) is applied via the cache backend.
    """
    permission_classes = [AllowAny]
    _RATE_LIMIT = 10  # requests per window
    _RATE_WINDOW = 60  # seconds

    def _is_rate_limited(self, request) -> bool:
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", "unknown")
        )
        cache_key = f"phone_lookup_{ip}"
        hits = cache.get(cache_key, 0)
        if hits >= self._RATE_LIMIT:
            return True
        cache.set(cache_key, hits + 1, self._RATE_WINDOW)
        return False

    def get(self, request, *args, **kwargs):
        if self._is_rate_limited(request):
            return Response(
                {"detail": "Too many requests. Please wait a moment.", "code": "rate_limited"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        phone = (request.query_params.get("phone") or "").strip()
        # Normalize: strip non-digit chars for flexible matching
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 6:
            return Response(
                {"detail": "Please enter at least 6 digits of your phone number.", "code": "phone_too_short"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        since = timezone.now() - timedelta(days=90)
        orders = (
            Order.objects
            .filter(customer_phone_digits=digits[-9:], created_at__gte=since)
            .prefetch_related("items")
            .order_by("-created_at")[:20]
        )

        results = []
        for order in orders:
            results.append({
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "fulfillment_type": order.fulfillment_type,
                "total": str(order.total),
                "currency": order.currency,
                "items_count": sum(i.qty for i in order.items.all()),
                "created_at": order.created_at.isoformat(),
                "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
            })

        return Response({"results": results, "count": len(results)})


def _send_owner_new_reservation_email(tenant, lead) -> None:
    """Send a plain-text new-reservation notification to the tenant owner."""
    try:
        from accounts.models import User as _User
        owner_email = (
            _User.objects
            .filter(tenant=tenant, role=_User.Roles.TENANT_OWNER)
            .values_list("email", flat=True)
            .first()
        )
        if not owner_email:
            return

        notes = lead.notes or ""
        body = (
            f"New reservation request — {tenant.name}\n"
            f"{'=' * 40}\n"
            f"Name:  {lead.name or '—'}\n"
            f"Phone: {lead.phone or '—'}\n"
            f"Email: {lead.email or '—'}\n"
        )
        if notes:
            body += f"Notes: {notes}\n"

        send_mail(
            subject=f"New reservation request — {tenant.name}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )
    except Exception:  # noqa: BLE001
        pass


def _send_order_status_email(order, tenant, new_status: str) -> None:
    """Send a plain-text order status notification to the customer, if they have an email."""
    from accounts.notifications import record_notification
    try:
        customer_email = order.customer.email if order.customer else None
        if not customer_email:
            return
        # Respect the customer's notification opt-out.
        if order.customer and not getattr(order.customer, "notify_order_updates", True):
            return

        status_labels = {
            Order.Status.CONFIRMED: "confirmed",
            Order.Status.PREPARING: "being prepared",
            Order.Status.READY: "ready",
            Order.Status.OUT_FOR_DELIVERY: "out for delivery",
            Order.Status.COMPLETED: "completed",
            Order.Status.CANCELLED: "cancelled",
        }
        label = status_labels.get(new_status, new_status)
        subject = f"Order #{order.order_number} update — {tenant.name}"

        lines = [
            f"Hi {order.customer_name or 'there'},",
            "",
            f"Your order #{order.order_number} at {tenant.name} is now {label}.",
        ]

        if new_status == Order.Status.CONFIRMED and order.estimated_ready_minutes:
            lines.append(f"Estimated wait: {order.estimated_ready_minutes} minutes.")

        if new_status == Order.Status.READY:
            if order.fulfillment_type == Order.FulfillmentType.DELIVERY:
                lines.append("Your order is ready and will be dispatched shortly.")
            elif order.fulfillment_type == Order.FulfillmentType.PICKUP:
                lines.append("Your order is ready for pickup.")
            else:
                lines.append("Your order is ready.")

        if new_status == Order.Status.OUT_FOR_DELIVERY:
            lines.append("Your order is on its way!")

        if order.owner_note:
            lines.append(f"\nNote from restaurant: {order.owner_note}")

        lines += ["", f"— {tenant.name}"]

        send_mail(
            subject=subject,
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )
        record_notification(
            channel="email", event=f"order.{new_status}", status="sent",
            recipient=customer_email, detail=getattr(tenant, "name", ""),
            reference=order.order_number, tenant_id=getattr(tenant, "id", None),
        )
    except Exception:  # noqa: BLE001
        try:
            record_notification(
                channel="email", event=f"order.{new_status}", status="failed",
                reference=getattr(order, "order_number", ""), tenant_id=getattr(tenant, "id", None),
            )
        except Exception:
            pass


def _can_edit_tenant_order(request) -> bool:
    """Owner, or staff with the 'manage orders' permission, on this tenant.

    This is the waiter's core capability (handle orders + take payment). Staff without
    perm_manage_orders are read-only and cannot mutate orders or charge wallets.
    """
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    from accounts.models import User
    return (user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
            and user.effective_perm_manage_orders())


def _can_access_order(request, order, *, my_slugs=None, claimed_slugs=None) -> bool:
    """Check that a waiter is allowed to mutate *order*.

    Owners (and superusers) may access any order. Staff are restricted to orders
    whose table belongs to one of their assigned sections — exactly the same
    rule applied by StaffOrderListView's hard section filter.

    Non-table orders (pickup / delivery) are shared: any waiter may handle them.
    Tables that have no assigned section server are also unowned and accessible
    to all waiters (pre-section behaviour).

    Pass *my_slugs* and *claimed_slugs* (pre-computed via _section_slugs_for) to
    avoid re-querying inside a select_for_update() critical section.
    """
    if _is_tenant_owner(request):
        return True
    if order.fulfillment_type != Order.FulfillmentType.TABLE:
        return True  # pickup/delivery are shared
    if not order.table_slug:
        return True  # no table → not a section table

    if my_slugs is None or claimed_slugs is None:
        # Cache on the request to avoid redundant DB hits within a single request
        # (e.g. when multiple orders are checked in the same call-chain).
        _cached = getattr(request, "_section_slugs_cache", None)
        if _cached is None:
            from .waiter_views import _section_slugs_for
            _cached = _section_slugs_for(request.user)
            try:
                request._section_slugs_cache = _cached
            except AttributeError:
                pass  # immutable in some test setups
        my_slugs, claimed_slugs = _cached
    if not claimed_slugs:
        return True  # floor not yet divided — any waiter can see everything
    if order.table_slug not in claimed_slugs:
        return True  # orphan table (no server assigned) — shared
    return order.table_slug in my_slugs


def _can_view_revenue(request) -> bool:
    """Owner, or staff with the 'view revenue' permission, on this tenant."""
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    from accounts.models import User
    return (user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
            and user.effective_perm_view_revenue())


def _can_void_order_item(request) -> bool:
    """Owner, or staff with BOTH 'manage orders' and 'void orders' permissions.

    Splitting void from manage_orders is a loss-prevention control: a waiter
    can handle the order flow without being authorised to reverse items
    (and trigger wallet refunds).
    """
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    from accounts.models import User
    return (user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
            and user.effective_perm_manage_orders()
            and user.effective_perm_void())


def _can_edit_menu(request) -> bool:
    """Owner, or staff with the 'edit menu' permission, on this tenant."""
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    from accounts.models import User
    return (user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}
            and user.effective_perm_edit_menu())


class StaffOrderListView(APIView):
    """GET /api/staff/orders/ — active orders for the waiter view, optimized for polling.

    Returns only non-terminal orders (pending/confirmed/preparing/ready) ordered
    oldest-first so the most urgent orders appear at the top.

    Supports ?since=<ISO-8601> to fetch only orders whose ``updated_at`` is after
    the given timestamp, enabling efficient 15-second polling without re-transmitting
    the entire list on every tick.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [StaffOrderListThrottle]

    _ACTIVE_STATUSES = [
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PREPARING,
        Order.Status.READY,
        Order.Status.OUT_FOR_DELIVERY,
    ]

    def get(self, request):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # ?recent=1 → recently finished orders (completed/cancelled, last 24h) so a
        # waiter can review or re-open a bill after it left the active list.
        recent = request.query_params.get("recent", "").strip() in ("1", "true", "yes")
        if recent:
            cutoff = timezone.now() - timedelta(hours=24)
            qs = (
                Order.objects
                .filter(status__in=[Order.Status.COMPLETED, Order.Status.CANCELLED], created_at__gte=cutoff)
                .prefetch_related("items")
                .order_by("-created_at")  # newest-first for history
            )
        else:
            qs = (
                Order.objects
                .filter(status__in=self._ACTIVE_STATUSES)
                .prefetch_related("items")
                .order_by("created_at")  # oldest-first → most urgent at top
            )

            since_raw = request.query_params.get("since", "").strip()
            if since_raw:
                try:
                    since_dt = datetime.fromisoformat(since_raw.replace("Z", "+00:00"))
                    qs = qs.filter(updated_at__gt=since_dt)
                except ValueError:
                    pass  # ignore unparseable timestamp — return full active list

        # ── Hard section filter ────────────────────────────────────────────────
        # A waiter sees ONLY their assigned sections' table orders, plus every
        # pickup/delivery order (shared), plus any orphan table order (no section
        # or a section with no assigned server) so nothing is ever invisible.
        # Owners see everything.
        if not _is_tenant_owner(request):
            from .waiter_views import _section_slugs_for
            my_slugs, claimed_slugs = _section_slugs_for(request.user)
            # Only filter once the floor is actually divided into served sections.
            # With no assignments every waiter sees all orders (pre-section behaviour).
            if claimed_slugs:
                qs = qs.filter(
                    ~Q(fulfillment_type=Order.FulfillmentType.TABLE)   # pickup/delivery: shared
                    | Q(table_slug__in=my_slugs)                       # my section's tables
                    | ~Q(table_slug__in=claimed_slugs)                 # orphan tables (no server)
                )

        # Section label per table slug, for display on the waiter cards.
        section_name_by_slug = dict(
            TableLink.objects.exclude(section__isnull=True).values_list("slug", "section__name")
        )

        # ── Materialise query once so we can batch-join delivery jobs ─────────
        order_objects = list(qs[:100])

        # ── Batch-load delivery job status for delivery orders (kitchen visibility) ─
        # Kitchen staff need to know whether a driver has been found, is en route,
        # etc. — without the full PII payload served to the owner view.
        _dj_map: dict = {}
        try:
            _tenant_id = getattr(getattr(request, "tenant", None), "id", None)
            if _tenant_id:
                _delivery_nums = [
                    o.order_number for o in order_objects
                    if o.fulfillment_type == Order.FulfillmentType.DELIVERY
                ]
                if _delivery_nums:
                    from accounts.models import DeliveryJob as _DJ
                    for _dj in (
                        _DJ.objects.select_related("driver")
                        .filter(tenant_id=_tenant_id, order_number__in=_delivery_nums)
                    ):
                        _drv = _dj.driver
                        _dj_map[_dj.order_number] = {
                            "status": _dj.status,
                            # Minimal driver info — name only (no PII like phone for kitchen)
                            "driver_name": (_drv.name or _drv.phone or "") if _drv else None,
                        }
        except Exception:
            pass  # non-critical — kitchen still functions without delivery-job data

        orders = []
        for order in order_objects:
            orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "fulfillment_type": order.fulfillment_type,
                "table_label": order.table_label,
                "section_name": section_name_by_slug.get(order.table_slug, "") if order.table_slug else "",
                "customer_name": order.customer_name,
                # Customer-rating affordance: only the server who handled this
                # order may rate the linked customer.
                "customer_id": order.customer_id,
                "handled_by_me": order.handled_by_user_id == getattr(request.user, "id", None),
                "customer_note": order.customer_note,
                "owner_note": order.owner_note,
                "estimated_ready_minutes": order.estimated_ready_minutes,
                "total": str(order.total),
                "delivery_fee": str(order.delivery_fee),
                "wallet_amount_paid": str(order.wallet_amount_paid) if order.wallet_amount_paid else "0",
                "currency": order.currency,
                "items_count": sum(i.qty for i in order.items.all()),
                "fired_course": getattr(order, "fired_course", 1),
                "items": [
                    {
                        "id": i.id,
                        "dish_name": i.dish_name,
                        "qty": i.qty,
                        "unit_price": str(i.unit_price),
                        "subtotal": str(i.subtotal),
                        "options": i.options,
                        "note": i.note,
                        "is_ready": i.is_ready,
                        "is_voided": i.is_voided,
                        "combo_components": i.combo_components,
                        "course": getattr(i, "course", 0),
                    }
                    for i in order.items.all()
                ],
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                # Scheduled advance orders — drives the violet badge in the
                # kitchen display so staff know to hold the order until release time.
                "scheduled_for": order.scheduled_for.isoformat() if getattr(order, "scheduled_for", None) else None,
                # Delivery job: compact status chip for kitchen staff awareness.
                "delivery_job": _dj_map.get(order.order_number),
            })

        return Response({"results": orders, "count": len(orders)})


class StaffShiftSummaryView(APIView):
    """GET /api/staff/shift-summary/ — end-of-shift stats for the waiter view.

    Query params:
      - since: ISO-8601 datetime marking shift start. Defaults to 8 hours ago.

    Returns:
      orders_handled             — count of orders that reached 'completed' within the window
      total_revenue              — sum of their totals (Decimal string)
      collected_cash             — cash collected in the window (Decimal string, Contract G)
      collected_wallet           — wallet collected in the window (Decimal string, Contract G)
      currency                   — currency code (from first order, or empty)
      average_prep_time_minutes  — mean (status_updated_at − created_at) in minutes, single query
      since                      — ISO-8601 of the window start actually used
      period_hours               — float hours covered

    Contract G changes:
      - cash/wallet split added using split_revenue_for_orders (shared helper).
      - avg prep time collapsed into a single-query ExpressionWrapper(Avg(duration))
        instead of the previous Python loop over qs.only("created_at","status_updated_at").
        This avoids an N+0 extra Python iteration over all rows and is cheaper for
        the DB (single aggregate vs. materialising the full queryset into Python).
      - currency folded into the aggregate query instead of a second .first() query.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # Parse 'since' — default 8 h ago
        since_raw = (request.query_params.get("since") or "").strip()
        if since_raw:
            try:
                since_dt = datetime.fromisoformat(since_raw.replace("Z", "+00:00"))
                if since_dt.tzinfo is None:
                    from django.utils.timezone import make_aware
                    since_dt = make_aware(since_dt)
            except ValueError:
                since_dt = None
        else:
            since_dt = None

        if since_dt is None:
            since_dt = timezone.now() - timedelta(hours=8)

        # Scope to the orders THIS user personally handled — their own shift, not the
        # whole restaurant. Owners using the waiter view see their own handled orders too;
        # restaurant-wide figures live in the owner dashboard.
        # payment_status=PAID is required so the split matches the Z-report and digest
        # (both of which filter on PAID).  Without it, COMPLETED dine-in orders that
        # haven't been paid yet (wallet_amount_paid=0) inflate the "cash" figure via
        # the legacy split path (cash = total − wallet_amount_paid = total).
        qs = Order.objects.filter(
            status=Order.Status.COMPLETED,
            payment_status=Order.PaymentStatus.PAID,
            status_updated_at__gte=since_dt,
            handled_by_user_id=getattr(request.user, "id", None),
        )

        # Contract G: single-query aggregate.
        # ExpressionWrapper(F('status_updated_at') - F('created_at')) yields a
        # DurationField; Avg() over it gives the mean duration without materialising
        # all rows into Python.  The result is a timedelta (or None when no rows).
        from django.db.models import Avg, Count, DurationField, ExpressionWrapper, Sum
        from django.db.models.functions import Coalesce

        agg = qs.aggregate(
            total_count=Count("id"),
            total_revenue=Sum("total"),
            # avg_prep_duration: Avg of (status_updated_at − created_at)
            # Both fields are always set on COMPLETED orders, but we guard
            # with a DurationField cast for safety.
            avg_prep_duration=Avg(
                ExpressionWrapper(
                    F("status_updated_at") - F("created_at"),
                    output_field=DurationField(),
                )
            ),
        )

        orders_handled = agg["total_count"] or 0
        total_revenue = agg["total_revenue"] or Decimal("0.00")

        # Convert the mean duration to minutes (round to 1 decimal).
        avg_prep_minutes = None
        raw_duration = agg.get("avg_prep_duration")
        if raw_duration is not None:
            total_secs = raw_duration.total_seconds()
            if total_secs >= 0:
                avg_prep_minutes = round(total_secs / 60, 1)

        # Currency: pick from the first row without an extra .only("currency").first() query.
        # We use qs.values_list which is a single cheap scan.
        currency = (
            qs.values_list("currency", flat=True)
            .exclude(currency="")
            .order_by()
            .first()
        ) or ""

        now = timezone.now()
        period_hours = round((now - since_dt).total_seconds() / 3600, 1)

        # Contract G: cash/wallet split for drawer handover.
        # Reuses split_revenue_for_orders (shared with Z-report and daily digest)
        # so the three surfaces always agree.
        show_revenue = _can_view_revenue(request)
        collected_cash = None
        collected_wallet = None
        if show_revenue:
            from menu.revenue import split_revenue_for_orders
            split = split_revenue_for_orders(qs)
            collected_cash = str(split["cash"])
            collected_wallet = str(split["wallet"])

        return Response({
            "orders_handled": orders_handled,
            "total_revenue": str(total_revenue) if show_revenue else None,
            "collected_cash": collected_cash,
            "collected_wallet": collected_wallet,
            "currency": currency if show_revenue else "",
            "show_revenue": show_revenue,
            "average_prep_time_minutes": avg_prep_minutes,
            "since": since_dt.isoformat(),
            "period_hours": period_hours,
        })


class StaffOrderItemReadyView(APIView):
    """PATCH /api/staff/order-items/<item_id>/ready/ — kitchen marks a single line item
    ready (or not) on a multi-item ticket. Body: { "ready": bool } (defaults to True).
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        # Kitchen item-readiness is a restaurant-only capability (shops have no
        # kitchen). Defaults to allowed for restaurants (non-breaking).
        from tenancy.capabilities import tenant_capability_enabled
        if not tenant_capability_enabled(getattr(request, "tenant", None), "kitchen"):
            return Response(
                {"detail": "Kitchen features are not available for this business.",
                 "code": "kitchen_unavailable"},
                status=status.HTTP_403_FORBIDDEN,
            )
        item = OrderItem.objects.select_related("order").filter(id=item_id).first()
        if item is None:
            return Response({"detail": "Item not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_order(request, item.order):
            return Response({"detail": "Access denied — not your section.", "code": "section_denied"},
                            status=status.HTTP_403_FORBIDDEN)
        if item.is_voided:
            return Response({"detail": "Voided items cannot be marked ready.", "code": "item_voided"},
                            status=status.HTTP_409_CONFLICT)
        _raw = request.data.get("ready", True)
        ready = _raw.strip().lower() in ("1", "true", "yes") if isinstance(_raw, str) else bool(_raw)
        item.is_ready = ready
        item.ready_at = timezone.now() if ready else None
        item.save(update_fields=["is_ready", "ready_at"])
        try:
            _broadcast_order_change(item.order)  # live-refresh other kitchen/owner screens
        except Exception:
            pass
        return Response({"id": item.id, "is_ready": item.is_ready})


def _staff_order_payload(order):
    """Return the refreshed staff-list order dict for a single order.

    Reused by the append-items, void-item, and split-bill payment views so all
    endpoints return the same shape the staff list uses, making frontend state
    updates trivial.

    Split-bill fields (R4):
      amount_paid   — sum of OrderPayment.amount rows (str decimal).
      outstanding   — max(0, total - amount_paid) (str decimal).
      payments      — list of OrderPayment rows in chronological order.

    Note: legacy one-shot settle endpoints do not write OrderPayment rows, so
    for those orders `payments` will be empty while `wallet_amount_paid` on the
    Order row reflects what was charged.  The `amount_paid` figure here is
    computed from the payments ledger only; callers that need the legacy total
    can still read `wallet_amount_paid` directly from the order fields.
    """
    from menu.models import OrderPayment as _OP
    _CENT = Decimal("0.01")

    # Payment ledger totals (R4)
    payment_rows = list(order.payments.all()) if hasattr(order, "payments") else []
    ledger_paid = sum(
        (Decimal(str(p.amount)) for p in payment_rows), Decimal("0")
    ).quantize(_CENT)
    outstanding = max(Decimal("0"), Decimal(str(order.total or "0")) - ledger_paid).quantize(_CENT)
    _items = list(order.items.all())

    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "completed": order.payment_status == Order.PaymentStatus.PAID,
        "fulfillment_type": order.fulfillment_type,
        "table_label": order.table_label,
        "customer_name": order.customer_name,
        "customer_id": order.customer_id,
        "customer_note": order.customer_note,
        "owner_note": order.owner_note,
        "estimated_ready_minutes": order.estimated_ready_minutes,
        "total": str(order.total),
        "delivery_fee": str(order.delivery_fee),
        "wallet_amount_paid": str(order.wallet_amount_paid) if order.wallet_amount_paid else "0",
        "currency": order.currency,
        # Course sequencing
        "fired_course": getattr(order, "fired_course", 1),
        # R4 split-bill fields
        "amount_paid": str(ledger_paid),
        "outstanding": str(outstanding),
        "payments": [
            {
                "amount": str(p.amount),
                "method": p.method,
                "created_at": p.created_at.isoformat() if hasattr(p.created_at, "isoformat") else str(p.created_at),
                "recorded_by_name": p.recorded_by_name,
                "note": p.note,
            }
            for p in payment_rows
        ],
        "items_count": sum(i.qty for i in _items if not i.is_voided),
        "items": [
            {
                "id": i.id,
                "dish_name": i.dish_name,
                "dish_slug": i.dish_slug,
                "qty": i.qty,
                "unit_price": str(i.unit_price),
                "subtotal": str(i.subtotal),
                "options": i.options,
                "note": i.note,
                "is_ready": i.is_ready,
                "is_voided": i.is_voided,
                "combo_components": i.combo_components,
                "course": getattr(i, "course", 0),
            }
            for i in _items
        ],
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "scheduled_for": order.scheduled_for.isoformat() if getattr(order, "scheduled_for", None) else None,
    }


def _recompute_order_totals(order):
    """Recompute order.total/subtotal from non-voided items + delivery_fee/tip/discount.

    Mirrors the PlaceOrderView formula: food_subtotal = sum(item.subtotal for non-voided),
    then subtract promotion_discount and loyalty_discount, add delivery_fee and tip.
    Does NOT save — caller must call order.save(update_fields=...).
    """
    non_voided = [i for i in order.items.all() if not i.is_voided]
    food_subtotal = sum(Decimal(str(i.subtotal)) for i in non_voided)
    promo_discount = Decimal(str(order.promotion_discount or "0"))
    loyalty_discount = Decimal(str(order.loyalty_discount or "0"))
    delivery_fee = Decimal(str(order.delivery_fee or "0"))
    tip_amount = Decimal(str(order.tip_amount or "0"))
    total = max(Decimal("0"), food_subtotal + delivery_fee - promo_discount - loyalty_discount + tip_amount)
    order.total = total


class StaffAppendOrderItemsView(APIView):
    """POST /api/staff/orders/<order_id>/items/

    Append one or more items to an open TABLE order (dine-in only).

    Auth: same _can_edit_tenant_order gate used by all staff order views.

    Guards (409):
      not_table       — order.fulfillment_type != 'table'
      bad_status      — order.status not in pending/confirmed/preparing
      already_paid    — order.payment_status == PAID

    Body:
      { "items": [{"dish_slug": str, "qty": int, "note"?: str, "option_ids"?: [int]}] }

    Validates and builds items exactly like PlaceOrderView does for table orders
    (published+available dish, option pricing, per-item price snapshot).  Stock is
    decremented inside the same select_for_update pattern; an out-of-stock condition
    rolls back the whole request (409 out_of_stock).

    Returns the refreshed staff-list payload for the order.
    """
    permission_classes = [IsAuthenticated]

    _OPEN_STATUSES = {
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PREPARING,
    }

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.prefetch_related("items").filter(pk=order_id).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_access_order(request, order):
            return Response({"detail": "Access denied — not your section.", "code": "section_denied"},
                            status=status.HTTP_403_FORBIDDEN)

        # ── Guards ────────────────────────────────────────────────────────────
        if order.fulfillment_type != Order.FulfillmentType.TABLE:
            return Response(
                {"detail": "Items can only be appended to table orders.", "code": "not_table"},
                status=status.HTTP_409_CONFLICT,
            )
        if order.status not in self._OPEN_STATUSES:
            return Response(
                {"detail": "Order is not in an editable state.", "code": "bad_status"},
                status=status.HTTP_409_CONFLICT,
            )
        if order.payment_status == Order.PaymentStatus.PAID:
            return Response(
                {"detail": "Order is already paid.", "code": "already_paid"},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Input validation ──────────────────────────────────────────────────
        raw_items = request.data.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            return Response({"detail": "items must be a non-empty list.", "code": "invalid_items"},
                            status=status.HTTP_400_BAD_REQUEST)

        parsed = []
        for idx, entry in enumerate(raw_items):
            if not isinstance(entry, dict):
                return Response({"detail": f"items[{idx}] must be an object.", "code": "invalid_items"},
                                status=status.HTTP_400_BAD_REQUEST)
            slug = str(entry.get("dish_slug") or "").strip()
            if not slug:
                return Response({"detail": f"items[{idx}].dish_slug is required.", "code": "invalid_items"},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                qty = int(entry.get("qty") or 1)
                if qty < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return Response({"detail": f"items[{idx}].qty must be a positive integer.", "code": "invalid_items"},
                                status=status.HTTP_400_BAD_REQUEST)
            note = str(entry.get("note") or "")[:120]
            option_ids = []
            for oid in (entry.get("option_ids") or []):
                try:
                    option_ids.append(int(oid))
                except (TypeError, ValueError):
                    pass
            parsed.append({"slug": slug, "qty": qty, "note": note, "option_ids": option_ids})

        # ── Dish + option resolution (same criteria as PlaceOrderView) ────────
        slugs = [p["slug"] for p in parsed]
        all_option_ids = [oid for p in parsed for oid in p["option_ids"]]

        dishes_map = {
            d.slug: d
            for d in Dish.objects.filter(
                slug__in=slugs,
                is_published=True,
                is_available=True,
                category__is_published=True,
                category__is_temporarily_disabled=False,
            ).select_related("category").prefetch_related("combo_components__component")
        }
        missing = [s for s in slugs if s not in dishes_map]
        if missing:
            return Response(
                {"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        options_map = {}
        if all_option_ids:
            options_map = {o.id: o for o in DishOption.objects.filter(id__in=all_option_ids).select_related("dish")}

        # ── Happy-hour pricing (compute once, charge effective price per item) ──
        # Price locked at the moment the staff member appends — same semantics as
        # PlaceOrderView.  Option price_delta is added on top unchanged.
        # We use get_all_active_hh_rules() (no time-window filter) so that tests
        # patching menu.pricing.HappyHour fully control which rules apply.
        # Graceful fallback: if the HH query fails, skip discount.
        try:
            _staff_active_hh = get_all_active_hh_rules()
        except Exception:
            _staff_active_hh = []

        # ── Build new OrderItem records + collect stock updates ───────────────
        new_items_data = []
        _stock_updates = []   # list of (dish_pk, qty)
        _pk_to_slug = {}
        # combo component updates: list of (component_pk, total_qty_to_decrement, component_name)
        _component_stock_updates = []

        for p in parsed:
            dish = dishes_map[p["slug"]]
            # Apply happy-hour discount (option price_delta added on top below).
            unit_price, _ = effective_unit_price(dish, _staff_active_hh)
            option_snapshots = []
            _invalid_oids = []
            for oid in p["option_ids"]:
                opt = options_map.get(oid)
                _opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
                if opt is None or _opt_dish_slug != dish.slug:
                    _invalid_oids.append(oid)
                    continue
                unit_price += Decimal(str(opt.price_delta))
                option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})
            if _invalid_oids:
                return Response(
                    {
                        "detail": f"Some selected options are no longer valid for '{dish.name}'.",
                        "code": "stale_options",
                        "dish_slug": dish.slug,
                        "invalid_option_ids": _invalid_oids,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qty = p["qty"]
            subtotal = unit_price * qty
            # Build combo snapshot (per-unit qty, not pre-multiplied)
            _combo_snapshot = [
                {"dish_id": cc.component_id, "name": cc.component.name, "qty": cc.qty}
                for cc in dish.combo_components.all()
            ]
            # Snapshot course from category at append time (0 when category missing)
            _staff_course_snap = int(getattr(getattr(dish, "category", None), "course", 0) or 0)
            new_items_data.append({
                "dish_slug": dish.slug,
                "dish_name": dish.name,
                "unit_price": unit_price,
                "qty": qty,
                "note": p["note"],
                "options": option_snapshots,
                "subtotal": subtotal,
                "is_ready": False,
                "combo_components": _combo_snapshot,
                "course": _staff_course_snap,
            })
            _pk_to_slug[dish.pk] = dish.slug
            if dish.stock_qty is not None:
                _stock_updates.append((dish.pk, qty))
            # Component stock: decrement each component by (component.qty × ordered_qty)
            for _cc_snap in _combo_snapshot:
                _comp_total = _cc_snap["qty"] * qty
                _component_stock_updates.append(
                    (_cc_snap["dish_id"], _comp_total, _cc_snap["name"])
                )

        # ── Atomic: stock check + decrement + create items + recompute totals ─
        class _OutOfStock(Exception):
            def __init__(self, name):
                self.name = name

        # All dish PKs (finite- and unlimited-stock alike) for the availability
        # re-check under the lock.  Unlimited-stock dishes are excluded from
        # _stock_updates but must still be locked so a concurrent disable
        # (is_available=False) between the outer query and the insert is caught.
        _all_dish_pks = list(_pk_to_slug.keys())
        # Aggregate component stock updates: component_pk → (total_qty, name)
        _comp_pk_to_name: dict = {}
        _comp_stock_agg: dict = {}
        for _cpk, _cqty, _cname in _component_stock_updates:
            _comp_stock_agg[_cpk] = _comp_stock_agg.get(_cpk, 0) + _cqty
            _comp_pk_to_name[_cpk] = _cname
        # Include component PKs in the lock set (skip any that are already combo dishes)
        _all_lock_pks = list(_all_dish_pks) + [pk for pk in _comp_stock_agg if pk not in _all_dish_pks]

        try:
            with transaction.atomic():
                # Lock ALL appended dishes + combo components so we can re-validate
                # is_available and stock_qty atomically.
                _locked = {
                    d.pk: d
                    for d in Dish.objects.select_for_update().filter(pk__in=_all_lock_pks)
                }

                # Re-validate availability under the lock (catches concurrent disables
                # of unlimited-stock items that the outer query couldn't see).
                for _dish_pk in _all_dish_pks:
                    _ld = _locked.get(_dish_pk)
                    if _ld and not _ld.is_available:
                        raise _OutOfStock(_ld.name)

                if _stock_updates:
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered_qty:
                            raise _OutOfStock(_ld.name)
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None:
                            _new_qty = max(0, _ld.stock_qty - _ordered_qty)
                            if _new_qty == 0:
                                Dish.objects.filter(pk=_dish_pk).update(
                                    stock_qty=0, is_available=False, stock_auto_zeroed=True
                                )
                            else:
                                Dish.objects.filter(pk=_dish_pk).update(stock_qty=_new_qty)

                # Component stock: validate then decrement
                if _comp_stock_agg:
                    for _cpk, _cqty in _comp_stock_agg.items():
                        _ld = _locked.get(_cpk)
                        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _cqty:
                            raise _OutOfStock(_comp_pk_to_name.get(_cpk, ""))
                    for _cpk, _cqty in _comp_stock_agg.items():
                        _ld = _locked.get(_cpk)
                        if _ld and _ld.stock_qty is not None:
                            _cnew = max(0, _ld.stock_qty - _cqty)
                            if _cnew == 0:
                                Dish.objects.filter(pk=_cpk).update(
                                    stock_qty=0, is_available=False, stock_auto_zeroed=True
                                )
                            else:
                                Dish.objects.filter(pk=_cpk).update(stock_qty=_cnew)

                for item_data in new_items_data:
                    OrderItem.objects.create(order=order, **item_data)

                # Reload items from DB so _recompute_order_totals sees the new rows
                order = Order.objects.prefetch_related("items").get(pk=order_id)
                _recompute_order_totals(order)
                order.save(update_fields=["total", "updated_at"])

        except _OutOfStock as exc:
            return Response(
                {"detail": f"'{exc.name}' is out of stock.", "code": "out_of_stock", "dish": exc.name},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response(_staff_order_payload(order), status=status.HTTP_201_CREATED)


class StaffVoidOrderItemView(APIView):
    """POST /api/staff/orders/<order_id>/items/<item_id>/void/

    Void (remove) a single line item from an open order without cancelling the whole
    order.  Restocks the dish, recomputes totals, and (for wallet-paid orders) issues
    a partial wallet refund for exactly the item's line total.

    Auth: same _can_edit_tenant_order gate.

    Guards (404/409):
      404           — item does not belong to this order
      already_voided — item.is_voided is already True (409)
      bad_status    — order is in a terminal state (409)

    Body (optional): { "reason": str }

    Money rule (PAID wallet orders only):
      refund = min(item.subtotal, order.wallet_amount_paid)
      credit_wallet(..., tx_type=REFUND, idempotency_key=f"voiditem:{schema}:{item_id}")
      order.wallet_amount_paid decremented by refunded amount; payment_status stays PAID.
      Cash-paid or UNPAID orders: no wallet movement.

    Loyalty clawback (per-item):
      When an order has points_earned > 0 and a linked customer, voids
      proportionally claw back earned points using the exact same formula as
      placement: pts = int(float(food_subtotal) * rate).  The clawback is:
        clawback = earned_for(pre_void_food_subtotal) - earned_for(post_void_food_subtotal)
      clamped to the remaining points_earned on the order so that multiple voids
      never exceed what was originally awarded.  order.points_earned is decremented
      by the clawback so a subsequent full cancel via _reverse_loyalty_for_cancelled_order
      naturally claws only the remaining balance (no double-claw).

      MVP boundary: redeemed_loyalty_points is order-level and is NOT touched
      here.  Redemption reversal happens only on full cancel.

    Returns the refreshed staff-list payload for the order.
    """
    permission_classes = [IsAuthenticated]

    # Deliberately looser than the append view's _OPEN_STATUSES: voiding an item
    # off a READY order (customer refuses it at the pass, before settle) is a
    # real service situation, while APPENDING to a READY order would silently
    # re-open kitchen work after "ready" was announced — that stays blocked.
    _TERMINAL_STATUSES = {Order.Status.COMPLETED, Order.Status.CANCELLED}

    def post(self, request, order_id, item_id, *args, **kwargs):
        if not _can_void_order_item(request):
            return Response({"detail": "Access denied.", "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.prefetch_related("items").filter(pk=order_id).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_access_order(request, order):
            return Response({"detail": "Access denied — not your section.", "code": "section_denied"},
                            status=status.HTTP_403_FORBIDDEN)

        # Item must belong to this order
        item = order.items.filter(pk=item_id).first()
        if item is None:
            return Response({"detail": "Item not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        if item.is_voided:
            return Response({"detail": "Item is already voided.", "code": "already_voided"},
                            status=status.HTTP_409_CONFLICT)

        if order.status in self._TERMINAL_STATUSES:
            return Response(
                {"detail": "Order is in a terminal state and cannot be modified.", "code": "bad_status"},
                status=status.HTTP_409_CONFLICT,
            )

        reason = str(request.data.get("reason") or "")[:120]

        # ── Atomic: void + restock + recompute totals ─────────────────────────
        with transaction.atomic():
            # Mark voided
            now = timezone.now()
            item.is_voided = True
            item.voided_at = now
            item.void_reason = reason
            item.voided_by_user_id = getattr(request.user, "id", None)
            item.save(update_fields=["is_voided", "voided_at", "void_reason", "voided_by_user_id"])

            # Restock — same locked pattern as _restock_cancelled_order but per-item.
            # For combo items, also restock each component (component.qty × item.qty).
            from django.db.models import F as _F
            _void_slugs_to_restock = []
            if item.dish_slug:
                _void_slugs_to_restock.append((item.dish_slug, item.qty))
            # Build component restock list from snapshot (component qty per unit × item.qty)
            _void_component_pks: dict = {}  # pk → qty
            if item.combo_components:
                for _cc_snap in item.combo_components:
                    _c_pk = _cc_snap.get("dish_id")
                    _c_per_unit = int(_cc_snap.get("qty", 1))
                    if _c_pk is not None and _c_per_unit > 0:
                        _void_component_pks[_c_pk] = _void_component_pks.get(_c_pk, 0) + _c_per_unit * int(item.qty or 0)

            # Merged single select_for_update across combo dish (by slug) AND
            # components (by pk) so lock acquisition order is identical to
            # placement/append and cannot interleave with concurrent placement.
            if _void_slugs_to_restock or _void_component_pks:
                from django.db.models import Q as _Q
                _slug_list = [s for s, _ in _void_slugs_to_restock]
                _pk_list = list(_void_component_pks.keys())
                _lock_q = _Q()
                if _slug_list:
                    _lock_q |= _Q(slug__in=_slug_list)
                if _pk_list:
                    _lock_q |= _Q(pk__in=_pk_list)
                _all_locked = list(Dish.objects.select_for_update().filter(_lock_q))
                for _d in _all_locked:
                    # Combo-dish restock (matched by slug)
                    _restock_qty = next((q for s, q in _void_slugs_to_restock if s == _d.slug), 0)
                    # Component restock (matched by pk)
                    _c_qty = _void_component_pks.get(_d.pk, 0)
                    # Merge both quantities into a single update to avoid double-
                    # incrementing a dish that appears in both maps (e.g. a dish
                    # that is simultaneously the top-level combo item AND a listed
                    # component of that same order snapshot).
                    _total_restock = _restock_qty + _c_qty
                    if _total_restock > 0 and _d.stock_qty is not None:
                        Dish.objects.filter(pk=_d.pk).update(
                            stock_qty=_F("stock_qty") + _total_restock,
                            is_available=True,
                            stock_auto_zeroed=False,
                        )

            # Recompute order totals from non-voided items.
            # select_for_update() locks the order row so concurrent void calls on
            # different items cannot both read a stale wallet_amount_paid and each
            # issue an independent refund (TOCTOU / double-spend fix).
            order = Order.objects.select_for_update().prefetch_related("items").get(pk=order_id)
            # Capture pre-void food subtotal from the item being voided (already saved
            # as voided, so non-voided list won't include it after recompute).
            _voided_item_subtotal = Decimal(str(item.subtotal or "0"))
            _recompute_order_totals(order)

            # ── A5-followup FIX 2: reduce platform commission on the void ──────────
            # A marketplace order is billed commission on its PRE-discount food
            # subtotal (sum of item.subtotal — see accounts/views.py checkout, which
            # snapshots commission_rate_applied). Voiding an item removes food
            # revenue, so the commission the platform charges must shrink with it —
            # otherwise the restaurant keeps paying commission on a line it refunded.
            # We RECOMPUTE (not prorate) from the new effective food subtotal using
            # the order's SNAPSHOTTED rate, which is exactly the basis A5 used at
            # placement, so the result is consistent and self-correcting across any
            # sequence of voids (each void recomputes from the current non-voided
            # lines). Direct orders carry no rate (commission_rate_applied == 0) and
            # are left untouched. Clamped at >= 0 (a fully-voided order → 0).
            # Gate on source FIRST: a direct order never carries commission, so we
            # skip the recompute (and the rate conversion) entirely for it. Only a
            # marketplace order with a positive snapshotted rate is recomputed.
            _recompute_commission = False
            if order.source == Order.Source.MARKETPLACE:
                _commission_rate = Decimal(str(order.commission_rate_applied or "0"))
                if _commission_rate > Decimal("0"):
                    _recompute_commission = True
                    # New PRE-discount food subtotal = sum of the remaining
                    # (non-voided) line subtotals — the SAME basis
                    # _recompute_order_totals uses for the food component of
                    # order.total, and the same basis A5 commission is charged on
                    # (food only; excludes delivery_fee / tip / discount).
                    _new_food_subtotal = sum(
                        (Decimal(str(i.subtotal)) for i in order.items.all() if not i.is_voided),
                        Decimal("0"),
                    )
                    _new_commission = (_new_food_subtotal * _commission_rate).quantize(Decimal("0.01"))
                    if _new_commission < Decimal("0"):
                        _new_commission = Decimal("0")
                    order.commission_amount = _new_commission

            # ── Loyalty clawback ──────────────────────────────────────────────
            # Proportionally claw back earned loyalty points for the voided item
            # using the ratio (voided_subtotal / pre_void_total_subtotal) applied
            # to order.points_earned (the STORED earned value at placement time).
            # This intentionally does NOT re-read LoyaltyConfig so that a rate
            # change between placement and void cannot produce an over-clawback.
            # Works across any sequence of voids: clawback is bounded by the
            # remaining points_earned, so total clawed ≤ original earned.
            # A subsequent full cancel via _reverse_loyalty_for_cancelled_order
            # sees the decremented points_earned and claws only the remainder —
            # no double-claw.
            _loyalty_clawback_pts = 0
            try:
                _orig_earned = int(getattr(order, "points_earned", 0) or 0)
                if _orig_earned > 0 and order.customer_id:
                    # Use the non-voided items subtotal (already marked voided above)
                    _non_voided_subtotal = sum(
                        Decimal(str(i.subtotal)) for i in order.items.all() if not i.is_voided
                    )
                    _pre_subtotal = _non_voided_subtotal + _voided_item_subtotal
                    if _pre_subtotal > Decimal("0"):
                        # Proportional clawback: fraction of subtotal being removed
                        _raw_clawback = int(
                            round(float(_orig_earned) * float(_voided_item_subtotal) / float(_pre_subtotal))
                        )
                        _loyalty_clawback_pts = max(0, min(_raw_clawback, _orig_earned))
                    if _loyalty_clawback_pts > 0:
                        from accounts.models import Customer as _CustC
                        _cust_locked = _CustC.objects.select_for_update().get(pk=order.customer_id)
                        _new_pts = max(0, int(_cust_locked.loyalty_points or 0) - _loyalty_clawback_pts)
                        _cust_locked.loyalty_points = _new_pts
                        _cust_locked.save(update_fields=["loyalty_points", "updated_at"])
                        # Decrement order.points_earned so cancel claws only the rest
                        Order.objects.filter(pk=order.pk).update(
                            points_earned=_orig_earned - _loyalty_clawback_pts
                        )
                        order.points_earned = _orig_earned - _loyalty_clawback_pts
            except Exception:
                pass  # Loyalty clawback is best-effort — never block a void

            # Partial wallet refund — two cases:
            #   A. PAID order: refund min(line_total, wallet_amount_paid); status stays PAID.
            #   B. UNPAID order with wallet_amount_paid > new total (split-bill overpayment):
            #      refund the overpay and flip the order to PAID so the payment flow
            #      doesn't get stuck (ledger now fully covers the reduced total).
            # We save the order BEFORE calling credit_wallet so that the
            # wallet_amount_paid decrement and the wallet credit are atomic with
            # respect to failures: if order.save() raises, credit_wallet is never
            # called; if credit_wallet raises, the outer transaction rolls back
            # order.save() via savepoint (fixing the non-atomicity risk).
            _refunded = Decimal("0")
            _extra_save_fields: list = []
            wallet_paid = Decimal(str(order.wallet_amount_paid or "0"))
            new_total = Decimal(str(order.total or "0"))
            if order.payment_status == Order.PaymentStatus.PAID and wallet_paid > Decimal("0") and order.customer_id:
                # Case A — PAID order void
                line_total = Decimal(str(item.subtotal))
                refund_amount = min(line_total, wallet_paid)
                if refund_amount > Decimal("0"):
                    _refunded = refund_amount
                    order.wallet_amount_paid = wallet_paid - _refunded
            elif order.payment_status != Order.PaymentStatus.PAID and wallet_paid > Decimal("0") and order.customer_id:
                # Case B — UNPAID order: check if the ledger-plus-wallet now covers the
                # reduced total and / or if wallet overpays the new total.
                from menu.models import OrderPayment as _OP
                ledger_paid = sum(
                    (Decimal(str(p.amount)) for p in order.payments.all()), Decimal("0")
                )
                total_collected = ledger_paid  # wallet debits are in WalletTransaction, not OrderPayment
                # Overpayment = how much wallet_amount_paid exceeds the new total after void
                overpay = max(Decimal("0"), wallet_paid - new_total)
                if overpay > Decimal("0"):
                    _refunded = overpay
                    order.wallet_amount_paid = wallet_paid - _refunded
                # Flip to PAID if total collected via ledger (cash+wallet OrderPayment rows)
                # plus remaining wallet_amount_paid now covers the new total.
                remaining_wallet = wallet_paid - _refunded
                if ledger_paid + remaining_wallet >= new_total:
                    order.mark_paid(save=False)
                    _extra_save_fields = ["payment_status", "paid_at"]

            # Persist total update and (conditionally) wallet_amount_paid before
            # issuing any wallet credit so the DB is consistent if credit_wallet fails.
            _wallet_fields = ["wallet_amount_paid"] if _refunded > Decimal("0") else []
            # A5-followup FIX 2: persist the reduced commission alongside the total.
            _commission_fields = ["commission_amount"] if _recompute_commission else []
            order.save(
                update_fields=["total", "updated_at"]
                + _wallet_fields + _extra_save_fields + _commission_fields
            )

            if _refunded > Decimal("0"):
                from accounts.wallet_service import credit_wallet
                from accounts.models import WalletTransaction as _WTx
                from django.db import connection as _vic
                _void_tenant = getattr(request, "tenant", None)
                # OPS-5g: WalletTransaction is PUBLIC-schema so idempotency_key is a GLOBAL
                # namespace; item_id is only tenant-schema-unique, so a bare
                # f"voiditem:{item_id}" could collide with another tenant's item of the same
                # PK and silently no-op the refund (returning the other tenant's tx on the
                # OPS-5f customer-match-pass path). Namespace with the tenant schema. The
                # durable backstop against a double-refund is that a re-void of an
                # already-voided item is rejected upstream before reaching this credit.
                credit_wallet(
                    order.customer_id,
                    _refunded,
                    tx_type=_WTx.Type.REFUND,
                    idempotency_key=f"voiditem:{_vic.schema_name}:{item_id}",
                    reference=order.order_number,
                    note=f"Void item: {item.dish_name}",
                    require_verified=False,
                    # tenant_id tags the row so refund queries can filter per-tenant.
                    # WalletTransaction lives in the shared schema; without this field
                    # the Z-report and dashboard would see refunds from all tenants.
                    tenant_id=_void_tenant.id if _void_tenant else None,
                )

        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response(_staff_order_payload(order))


class StaffFireCourseView(APIView):
    """POST /api/staff/orders/<order_id>/fire-course/

    Fire the next course for a dine-in table order: mark all items up to and
    including `course` as ready to be sent from the kitchen.

    Auth + section gating: identical to the other 4 staff mutation endpoints
    (_can_edit_tenant_order + _can_access_order).

    Body:
      { "course": <int 1..4> }

    Error codes (all 409 or 400):
      bad_status      — order is terminal (completed/cancelled)
      not_table       — order.fulfillment_type != "table"
      invalid_course  — course not in 1..4 (400)
      already_fired   — course <= order.fired_course (monotonic — no un-fire)

    Success: sets fired_course = course (monotonic), broadcasts, returns the
    full _staff_order_payload so the SPA can refresh in place.
    """

    permission_classes = [IsAuthenticated]

    _TERMINAL_STATUSES = {Order.Status.COMPLETED, Order.Status.CANCELLED}

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # Quick existence check before acquiring the write lock — avoids a
        # lock wait on a non-existent row and gives a clean 404.
        if not Order.objects.filter(pk=order_id).exists():
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        # ── Input validation (before the lock) ───────────────────────────────
        raw_course = request.data.get("course")
        try:
            course = int(raw_course)
            if course < 1 or course > 4:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "course must be an integer between 1 and 4.", "code": "invalid_course"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Atomic fire with row-level lock ───────────────────────────────────
        # select_for_update() prevents two concurrent fire requests from both
        # reading fired_course=N, both passing the monotonicity guard, and both
        # writing the same value — the second request will block on the lock and
        # re-read the value already written by the first.
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .prefetch_related("items", "payments")
                .filter(pk=order_id)
                .first()
            )
            if order is None:
                return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

            if not _can_access_order(request, order):
                return Response(
                    {"detail": "Access denied — not your section.", "code": "section_denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # ── Guards ────────────────────────────────────────────────────────────
            if order.status in self._TERMINAL_STATUSES:
                return Response(
                    {"detail": "Order is already completed or cancelled.", "code": "bad_status"},
                    status=status.HTTP_409_CONFLICT,
                )
            if order.fulfillment_type != Order.FulfillmentType.TABLE:
                return Response(
                    {"detail": "Course firing is only available for table orders.", "code": "not_table"},
                    status=status.HTTP_409_CONFLICT,
                )

            if course <= order.fired_course:
                return Response(
                    {"detail": f"Course {course} has already been fired.", "code": "already_fired"},
                    status=status.HTTP_409_CONFLICT,
                )

            # ── Fire ──────────────────────────────────────────────────────────────
            order.fired_course = course
            order.save(update_fields=["fired_course", "updated_at"])

        # Reload so _staff_order_payload sees fresh items
        order = Order.objects.prefetch_related("items", "payments").get(pk=order_id)

        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response(_staff_order_payload(order))


class StaffBulkReadyView(APIView):
    """POST /api/staff/orders/<order_id>/items/ready-all/

    Mark every non-voided, not-yet-ready item on the order as ready
    (is_ready=True, ready_at=now).  Already-ready and voided items are
    silently skipped so the call is idempotent.

    Auth + section gating: identical to all other staff mutation endpoints
    (_can_edit_tenant_order + _can_access_order).

    Error codes:
      bad_status — order is terminal (completed / cancelled)

    Success: exactly ONE _broadcast_order_change, then the full
    _staff_order_payload (same shape as append / void / fire-course).

    Empty order (no qualifying items) is a no-op → 200 with payload.
    """

    permission_classes = [IsAuthenticated]

    _TERMINAL_STATUSES = {Order.Status.COMPLETED, Order.Status.CANCELLED}

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        # Kitchen readiness is a restaurant-only capability (shops have no
        # kitchen). Mirror the single-item StaffOrderItemReadyView gate so the
        # bulk path can't bypass it for retail/grocery tenants.
        from tenancy.capabilities import tenant_capability_enabled
        if not tenant_capability_enabled(getattr(request, "tenant", None), "kitchen"):
            return Response(
                {"detail": "Kitchen features are not available for this business.",
                 "code": "kitchen_unavailable"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Existence pre-check before acquiring the write lock (clean 404).
        if not Order.objects.filter(pk=order_id).exists():
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        # Atomic + row lock so two kitchen devices bulk-readying the same order
        # don't both read a stale item set and double-broadcast (same discipline
        # as StaffFireCourseView).
        with transaction.atomic():
            order = (
                Order.objects
                .select_for_update()
                .prefetch_related("items", "payments")
                .filter(pk=order_id)
                .first()
            )
            if order is None:
                return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

            if not _can_access_order(request, order):
                return Response(
                    {"detail": "Access denied — not your section.", "code": "section_denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if order.status in self._TERMINAL_STATUSES:
                return Response(
                    {"detail": "Order is already completed or cancelled.", "code": "bad_status"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Mark every non-voided, not-yet-ready item ready in bulk.
            now = timezone.now()
            to_update = [
                i for i in order.items.all()
                if not i.is_voided and not i.is_ready
            ]
            for item in to_update:
                item.is_ready = True
                item.ready_at = now
                item.save(update_fields=["is_ready", "ready_at"])

        # Reload for fresh payload regardless of whether anything changed.
        order = Order.objects.prefetch_related("items", "payments").get(pk=order_id)

        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response(_staff_order_payload(order))


class StaffTableListView(APIView):
    """GET /api/staff/tables/

    Minimal read-only list of the tenant's active tables for use by the
    waiter new-order form (table picker dropdown).  Returns every active
    TableLink with its section name so the frontend can group them.

    Auth: same _can_edit_tenant_order gate (owner or staff with
    perm_manage_orders — i.e. any waiter who can place orders).

    Response shape (list):
      [
        {
          "id": int,
          "slug": str,
          "label": str,
          "section": str | null   // section name, null when unassigned
        },
        …
      ]

    Ordered by (position, label, id) — same as TableLink.Meta.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        tables = (
            TableLink.objects
            .select_related("section")
            .filter(is_active=True)
            .order_by("position", "label", "id")
        )
        data = [
            {
                "id": t.id,
                "slug": t.slug,
                "label": t.label,
                "section": t.section.name if t.section_id else None,
                "status": t.status,
                "capacity": t.capacity,
            }
            for t in tables
        ]
        return Response(data)


class StaffTableStatusView(APIView):
    """PATCH /api/staff/tables/<table_id>/status/

    Let a waiter explicitly set a table's operational status.

    Allowed values for `status`: "open", "dirty", "reserved".
    "occupied" is rejected — the waiter app derives occupancy from active orders.

    Auth: perm_manage_orders gate (same as all staff order views).
    """

    permission_classes = [IsAuthenticated]

    _ALLOWED = {TableLink.Status.OPEN, TableLink.Status.DIRTY, TableLink.Status.RESERVED}

    def patch(self, request, table_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = (request.data.get("status") or "").strip().lower()
        if new_status not in self._ALLOWED:
            return Response(
                {"detail": "status must be one of: open, dirty, reserved.", "code": "invalid_status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            table = TableLink.objects.get(pk=table_id, is_active=True)
        except TableLink.DoesNotExist:
            return Response({"detail": "Table not found."}, status=status.HTTP_404_NOT_FOUND)

        table.status = new_status
        table.save(update_fields=["status", "updated_at"])
        return Response({"id": table.id, "slug": table.slug, "label": table.label, "status": table.status})


class StaffTransferItemsView(APIView):
    """POST /api/staff/orders/<src_order_id>/transfer-items/

    Move a subset of non-voided items from one open table order to another.

    Body:
      { "item_ids": [int, ...], "dest_order_id": int }

    Guards (409):
      not_table        — either order is not fulfillment_type='table'
      bad_status       — either order is in a terminal/paid status
      already_paid     — source order is already marked PAID
      no_items         — item_ids is empty
      items_not_found  — one or more item_ids don't exist in src order (non-voided)

    On success both orders are recalculated, saved, and broadcast. Responds with
    the updated src payload. If all items are moved the src order is cancelled.
    """

    permission_classes = [IsAuthenticated]
    _ACTIVE = {"pending", "confirmed", "preparing", "ready"}

    def post(self, request, src_order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        item_ids = request.data.get("item_ids") or []
        dest_order_id = request.data.get("dest_order_id")

        if not item_ids:
            return Response({"detail": "item_ids is required.", "code": "no_items"}, status=status.HTTP_400_BAD_REQUEST)
        if not dest_order_id:
            return Response({"detail": "dest_order_id is required.", "code": "no_dest"}, status=status.HTTP_400_BAD_REQUEST)

        from django.db import transaction as _tx
        from menu.models import OrderItem as _OI

        with _tx.atomic():
            try:
                src = Order.objects.select_for_update().prefetch_related("items", "payments").get(pk=src_order_id)
            except Order.DoesNotExist:
                return Response({"detail": "Source order not found."}, status=status.HTTP_404_NOT_FOUND)

            if src.fulfillment_type != Order.FulfillmentType.TABLE:
                return Response({"detail": "Source order is not a table order.", "code": "not_table"}, status=status.HTTP_409_CONFLICT)
            if src.status not in self._ACTIVE:
                return Response({"detail": "Source order status does not allow item transfer.", "code": "bad_status"}, status=status.HTTP_409_CONFLICT)
            if src.payment_status == Order.PaymentStatus.PAID:
                return Response({"detail": "Source order is already paid.", "code": "already_paid"}, status=status.HTTP_409_CONFLICT)

            try:
                dest = Order.objects.select_for_update().prefetch_related("items", "payments").get(pk=dest_order_id)
            except Order.DoesNotExist:
                return Response({"detail": "Destination order not found."}, status=status.HTTP_404_NOT_FOUND)

            if dest.fulfillment_type != Order.FulfillmentType.TABLE:
                return Response({"detail": "Destination order is not a table order.", "code": "not_table"}, status=status.HTTP_409_CONFLICT)
            if dest.status not in self._ACTIVE:
                return Response({"detail": "Destination order status does not allow item transfer.", "code": "bad_status"}, status=status.HTTP_409_CONFLICT)

            # Validate items belong to src and are non-voided
            src_item_ids = {i.id for i in src.items.all() if not i.is_voided}
            requested = set(int(x) for x in item_ids)
            missing = requested - src_item_ids
            if missing:
                return Response({"detail": "Some items not found in source order.", "code": "items_not_found"}, status=status.HTTP_409_CONFLICT)

            # Move items
            _OI.objects.filter(pk__in=requested).update(order_id=dest.pk)

            # Refresh and recalculate
            src.refresh_from_db()
            dest.refresh_from_db()
            _recompute_order_totals(src)
            _recompute_order_totals(dest)

            remaining_active = [i for i in src.items.all() if not i.is_voided]
            if not remaining_active:
                src.status = Order.Status.CANCELLED
                src.save(update_fields=["total", "status", "updated_at"])
            else:
                src.save(update_fields=["total", "updated_at"])
            dest.save(update_fields=["total", "updated_at"])

        try:
            _broadcast_order_change(src)
        except Exception:
            pass
        try:
            _broadcast_order_change(dest)
        except Exception:
            pass

        src.refresh_from_db()
        return Response(_staff_order_payload(src))


class StaffMergeOrdersView(APIView):
    """POST /api/staff/orders/<dest_order_id>/merge/

    Merge a source table order into a destination table order.

    All non-voided items from the source are moved to the destination; the source
    order is then cancelled (its total is zeroed). Discounts / tips on the source
    order are NOT transferred — the destination's existing totals are unaffected
    other than the additional food items.

    Body: { "src_order_id": int }

    Guards (409): same as StaffTransferItemsView (both must be table+active).
    """

    permission_classes = [IsAuthenticated]
    _ACTIVE = {"pending", "confirmed", "preparing", "ready"}

    def post(self, request, dest_order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        src_order_id = request.data.get("src_order_id")
        if not src_order_id:
            return Response({"detail": "src_order_id is required.", "code": "no_src"}, status=status.HTTP_400_BAD_REQUEST)

        from django.db import transaction as _tx
        from menu.models import OrderItem as _OI

        with _tx.atomic():
            try:
                dest = Order.objects.select_for_update().prefetch_related("items", "payments").get(pk=dest_order_id)
            except Order.DoesNotExist:
                return Response({"detail": "Destination order not found."}, status=status.HTTP_404_NOT_FOUND)

            try:
                src = Order.objects.select_for_update().prefetch_related("items", "payments").get(pk=src_order_id)
            except Order.DoesNotExist:
                return Response({"detail": "Source order not found."}, status=status.HTTP_404_NOT_FOUND)

            if src.pk == dest.pk:
                return Response({"detail": "Source and destination must be different orders.", "code": "same_order"}, status=status.HTTP_400_BAD_REQUEST)

            for order, label in [(src, "Source"), (dest, "Destination")]:
                if order.fulfillment_type != Order.FulfillmentType.TABLE:
                    return Response({"detail": f"{label} order is not a table order.", "code": "not_table"}, status=status.HTTP_409_CONFLICT)
                if order.status not in self._ACTIVE:
                    return Response({"detail": f"{label} order status does not allow merge.", "code": "bad_status"}, status=status.HTTP_409_CONFLICT)
                if order.payment_status == Order.PaymentStatus.PAID:
                    return Response({"detail": f"{label} order is already paid.", "code": "already_paid"}, status=status.HTTP_409_CONFLICT)

            # Move all non-voided items from src → dest
            active_src_item_ids = [i.id for i in src.items.all() if not i.is_voided]
            if active_src_item_ids:
                _OI.objects.filter(pk__in=active_src_item_ids).update(order_id=dest.pk)

            # Cancel src (zero its total)
            src.status = Order.Status.CANCELLED
            src.total = Decimal("0")
            src.save(update_fields=["status", "total", "updated_at"])

            # Recalculate dest
            dest.refresh_from_db()
            _recompute_order_totals(dest)
            dest.save(update_fields=["total", "updated_at"])

        try:
            _broadcast_order_change(src)
        except Exception:
            pass
        try:
            _broadcast_order_change(dest)
        except Exception:
            pass

        dest.refresh_from_db()
        return Response(_staff_order_payload(dest))


def _shift_payload(shift):
    """Serialise a Shift instance to a dict."""
    return {
        "id": shift.id,
        "user_id": shift.user_id,
        "user_name": shift.user_name,
        "clock_in": shift.clock_in.isoformat(),
        "clock_out": shift.clock_out.isoformat() if shift.clock_out else None,
        "duration_hours": shift.duration_hours,
        "hourly_rate": str(shift.hourly_rate) if shift.hourly_rate is not None else None,
        "note": shift.note,
    }


class StaffClockInView(APIView):
    """POST /api/staff/clock-in/

    Record a clock-in for the authenticated staff member (owner or any staff
    with perm_manage_orders).  Rejects with 409 if the user already has an open
    shift in this tenant.

    Body (optional):
      { "note": str }

    Response: the created Shift payload.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from menu.models import Shift as _Shift
        from django.utils import timezone as _tz

        user_id = request.user.id
        if _Shift.objects.filter(user_id=user_id, clock_out__isnull=True).exists():
            return Response(
                {"detail": "You are already clocked in.", "code": "already_clocked_in"},
                status=status.HTTP_409_CONFLICT,
            )

        note = (request.data.get("note") or "").strip()[:200]
        shift = _Shift.objects.create(
            user_id=user_id,
            user_name=request.user.get_full_name() or request.user.username or "",
            clock_in=_tz.now(),
            note=note,
        )
        return Response(_shift_payload(shift), status=status.HTTP_201_CREATED)


class StaffClockOutView(APIView):
    """POST /api/staff/clock-out/

    Close the authenticated staff member's current open shift.
    Returns 404 if no open shift exists.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from menu.models import Shift as _Shift
        from django.utils import timezone as _tz

        shift = _Shift.objects.filter(user_id=request.user.id, clock_out__isnull=True).first()
        if not shift:
            return Response({"detail": "No open shift found.", "code": "not_clocked_in"}, status=status.HTTP_404_NOT_FOUND)

        shift.clock_out = _tz.now()
        shift.save(update_fields=["clock_out", "updated_at"])
        return Response(_shift_payload(shift))


class StaffMyShiftView(APIView):
    """GET /api/staff/my-shift/

    Returns the authenticated user's currently open shift, or null if not clocked in.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from menu.models import Shift as _Shift

        shift = _Shift.objects.filter(user_id=request.user.id, clock_out__isnull=True).first()
        return Response(_shift_payload(shift) if shift else None)


class StaffOrderPaymentView(APIView):
    """POST /api/staff/orders/<order_id>/payments/

    Record a single payment instalment toward a dine-in (or any open) order.
    Supports partial cash and partial wallet payments so a table can be settled
    incrementally by multiple payers (split-bill / R4).

    Auth: same _can_edit_tenant_order gate as StaffAppendOrderItemsView and
    StaffVoidOrderItemView (owner or staff with perm_manage_orders).

    Request body:
      {
        "method": "wallet" | "cash",   # required
        "amount": decimal,             # optional — omit/null for full outstanding
        "note":   str                  # optional, max 120 chars
      }

    Guards — all 409 unless noted:
      bad_status      — order is in a terminal status (COMPLETED / CANCELLED)
      already_paid    — order.payment_status is already PAID
      bad_amount (400)— amount present but <= 0 or not parseable
      overpay         — amount > outstanding (outstanding = total - sum of ledger rows)
      no_customer     — method=wallet but order has no customer_id
      insufficient_wallet — debit_wallet raised InsufficientFunds
                            (payment row NOT persisted — rolled back inside atomic)

    Response: refreshed _staff_order_payload (same shape as append/void).

    NOTE: Legacy one-shot settle endpoints (StaffSettleView, WalletSettleView,
    etc.) do NOT write OrderPayment rows — they simply flip payment_status to
    PAID and, for wallet, increment wallet_amount_paid.  For those orders the
    `payments` list in the payload will be empty; `amount_paid` comes from the
    ledger and will therefore be "0.00" even though the order is PAID.  This is
    intentional: the split-bill endpoint is additive-only and is NOT meant to
    back-fill legacy settled orders.
    """
    permission_classes = [IsAuthenticated]

    _TERMINAL_STATUSES = {Order.Status.COMPLETED, Order.Status.CANCELLED}
    _CENT = Decimal("0.01")

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # ── Parse body ────────────────────────────────────────────────────────
        method = str(request.data.get("method") or "").strip().lower()
        if method not in {"wallet", "cash"}:
            return Response(
                {"detail": "method must be 'wallet' or 'cash'.", "code": "bad_method"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get("amount")
        requested_amount = None  # None means "full outstanding"
        if raw_amount is not None:
            try:
                requested_amount = Decimal(str(raw_amount)).quantize(self._CENT)
                if requested_amount <= Decimal("0"):
                    raise ValueError("non-positive")
            except (Exception,):
                return Response(
                    {"detail": "amount must be a positive decimal.", "code": "bad_amount"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        note = str(request.data.get("note") or "")[:120]
        # Optional client-supplied idempotency key (max 128 chars).
        # If provided and a payment row for this order with that key was already
        # committed, the retry is short-circuited here and the current order
        # payload is returned without creating a duplicate row.  The cache TTL
        # is 5 minutes — long enough to cover any realistic network-retry window.
        idempotency_key = str(request.data.get("idempotency_key") or "")[:128] or None
        if idempotency_key:
            from django.db import connection as _staff_pay_conn
            _idem_cache_key = f"staff_pay_idem:{_staff_pay_conn.schema_name}:{order_id}:{idempotency_key}"
            if cache.get(_idem_cache_key):
                # Duplicate request: reload and return the current state.
                idem_order = (
                    Order.objects
                    .prefetch_related("items", "payments")
                    .get(pk=order_id)
                )
                return Response(_staff_order_payload(idem_order), status=status.HTTP_201_CREATED)

        # ── Atomic: lock order, validate, create payment row, maybe mark paid ─
        from menu.models import OrderPayment
        from accounts.wallet_service import debit_wallet, InsufficientFunds
        from accounts.models import WalletTransaction as _WTx

        try:
            with transaction.atomic():
                order = (
                    Order.objects
                    .select_for_update()
                    .prefetch_related("items", "payments")
                    .filter(pk=order_id)
                    .first()
                )
                if order is None:
                    return Response(
                        {"detail": "Order not found.", "code": "not_found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # ── Guards ────────────────────────────────────────────────────
                if not _can_access_order(request, order):
                    return Response({"detail": "Access denied — not your section.", "code": "section_denied"},
                                    status=status.HTTP_403_FORBIDDEN)
                if order.status in self._TERMINAL_STATUSES:
                    return Response(
                        {"detail": "Order is in a terminal state.", "code": "bad_status"},
                        status=status.HTTP_409_CONFLICT,
                    )
                if order.payment_status == Order.PaymentStatus.PAID:
                    return Response(
                        {"detail": "Order is already paid.", "code": "already_paid"},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Compute outstanding under the lock
                order_total = Decimal(str(order.total or "0")).quantize(self._CENT)
                existing_paid = sum(
                    (Decimal(str(p.amount)) for p in order.payments.all()),
                    Decimal("0"),
                ).quantize(self._CENT)
                outstanding = max(Decimal("0"), order_total - existing_paid).quantize(self._CENT)

                # ── Reconcile guard ───────────────────────────────────────────
                # If the ledger already covers the total but payment_status is
                # still UNPAID (e.g. rows were written out-of-band), flip to PAID
                # and return 200 "reconciled" without recording a new payment row.
                if outstanding <= Decimal("0"):
                    order.mark_paid(save=False)
                    order.save(update_fields=["payment_status", "paid_at", "updated_at"])
                    try:
                        _broadcast_order_change(order)
                    except Exception:
                        pass
                    _rec_order = (
                        Order.objects
                        .prefetch_related("items", "payments")
                        .get(pk=order_id)
                    )
                    return Response(
                        {**_staff_order_payload(_rec_order), "code": "reconciled"},
                        status=status.HTTP_200_OK,
                    )

                # Resolve amount
                amount = requested_amount if requested_amount is not None else outstanding
                if amount <= Decimal("0"):
                    return Response(
                        {"detail": "amount must be a positive decimal.", "code": "bad_amount"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if amount > outstanding:
                    return Response(
                        {
                            "detail": f"Amount {amount} exceeds outstanding {outstanding}.",
                            "code": "overpay",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                if method == "wallet" and not order.customer_id:
                    return Response(
                        {"detail": "Wallet payment requires a customer on the order.", "code": "no_customer"},
                        status=status.HTTP_409_CONFLICT,
                    )

                # ── Create payment row ────────────────────────────────────────
                recorder_name = ""
                recorder_id = None
                _user = getattr(request, "user", None)
                if _user and _user.is_authenticated:
                    recorder_id = getattr(_user, "id", None)
                    recorder_name = (
                        getattr(_user, "get_full_name", lambda: "")() or
                        getattr(_user, "username", "") or
                        getattr(_user, "email", "") or
                        ""
                    )[:80]

                payment = OrderPayment.objects.create(
                    order=order,
                    amount=amount,
                    method=method,
                    recorded_by_user_id=recorder_id,
                    recorded_by_name=recorder_name,
                    note=note,
                    idempotency_key=idempotency_key,
                )

                # ── Wallet debit (raises InsufficientFunds → rolls back row) ─
                _wallet_save_fields: list[str] = []
                if method == "wallet":
                    # OPS-5g: WalletTransaction is PUBLIC-schema so idempotency_key is a
                    # GLOBAL namespace; payment.id is only tenant-schema-unique, so a bare
                    # f"orderpay:{payment.id}" could collide with another tenant's payment
                    # of the same PK. Namespace with the tenant schema. The durable
                    # backstop against re-payment is the OrderPayment unique idempotency_key
                    # row + the order already-PAID guard above (line ~4736) + the
                    # IntegrityError replay handler below — not this key.
                    from django.db import connection as _opc
                    debit_wallet(
                        order.customer_id,
                        amount,
                        tx_type=_WTx.Type.PAYMENT,
                        idempotency_key=f"orderpay:{_opc.schema_name}:{payment.id}",
                        reference=order.order_number,
                    )
                    # Keep wallet_amount_paid consistent with dashboards
                    order.wallet_amount_paid = (
                        Decimal(str(order.wallet_amount_paid or "0")) + amount
                    ).quantize(self._CENT)
                    _wallet_save_fields = ["wallet_amount_paid"]

                # ── Flip to PAID if fully settled ─────────────────────────────
                new_paid = (existing_paid + amount).quantize(self._CENT)
                _paid_save_fields: list[str] = []
                if new_paid >= order_total:
                    order.mark_paid(save=False)
                    _paid_save_fields = ["payment_status", "paid_at"]

                # ── Single save: union of all dirty fields ────────────────────
                _all_save_fields = list(dict.fromkeys(
                    _wallet_save_fields + _paid_save_fields + ["updated_at"]
                ))
                order.save(update_fields=_all_save_fields)

        except InsufficientFunds:
            return Response(
                {"detail": "Wallet balance is insufficient.", "code": "insufficient_wallet"},
                status=status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            # OPS-3 contract D: DB-level backstop for the unique idempotency_key
            # constraint.  Redis was down (cache miss) AND two concurrent requests
            # raced on the same key — the second INSERT violated the unique constraint.
            # Re-fetch the winner's order and return it as a successful replay.
            if idempotency_key:
                try:
                    from menu.models import OrderPayment as _OPRace
                    _existing_pay = _OPRace.objects.filter(idempotency_key=idempotency_key).first()
                    if _existing_pay is not None:
                        _replay_order = (
                            Order.objects
                            .prefetch_related("items", "payments")
                            .get(pk=_existing_pay.order_id)
                        )
                        return Response(_staff_order_payload(_replay_order), status=status.HTTP_201_CREATED)
                except Exception:
                    pass
            return Response(
                {"detail": "Payment could not be recorded due to a conflict. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Reload with payments for the response (outside the atomic block)
        order = (
            Order.objects
            .prefetch_related("items", "payments")
            .get(pk=order_id)
        )

        # Mark this idempotency key as committed so retries are short-circuited.
        # NOTE: cache.set is intentionally POST-commit — writing inside atomic would
        # set the key even if the transaction rolls back (false short-circuit on retry).
        # IMPORTANT: the OrderPayment.idempotency_key DB UNIQUE constraint is the PRIMARY
        # backstop. If Redis is down, cache.set silently fails, but the next retry hits the
        # IntegrityError path above (lines 4944-4965) and correctly replays. Do NOT drop
        # that constraint — it is load-bearing, not just a belt-and-suspenders guard.
        if idempotency_key:
            cache.set(_idem_cache_key, True, timeout=300)  # 5 minutes

        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response(_staff_order_payload(order), status=status.HTTP_201_CREATED)


class OwnerDriverCashoutLookupView(APIView):
    """GET /api/owner/driver-cashout/?code=XXXXXX — preview a driver's pending cash-out
    request by code (owner/manager only) before handing over cash."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [DriverCashoutConfirmThrottle]  # OPS-5e: brute-force backstop

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        tenant = getattr(request, "tenant", None)
        code = (request.query_params.get("code") or "").strip()
        if not code:
            return Response({"detail": "code is required.", "code": "missing_code"}, status=status.HTTP_400_BAD_REQUEST)

        # OPS-5e: the lookup endpoint is a code-validity oracle (200 leaks
        # amount/driver for a valid code, 404 otherwise), so it must share the
        # SAME per-actor brute-force lockout as confirm_cashout — otherwise a
        # scanner walks the ~1e6 6-digit space through GET with zero penalty and
        # then confirms on the first try. Check the lockout before querying and
        # increment it on a miss, keyed on the actor like the confirm path.
        from django.core.cache import cache as _cache
        from accounts.driver_service import (
            _cashout_fail_cache_key,
            CASHOUT_CONFIRM_MAX_FAILURES,
            CASHOUT_CONFIRM_LOCK_SECONDS,
        )
        _actor_id = getattr(request.user, "id", None)
        _tenant_id = getattr(tenant, "id", None)
        _fail_key = _cashout_fail_cache_key(actor_user_id=_actor_id, tenant_id=_tenant_id)
        if (_cache.get(_fail_key) or 0) >= CASHOUT_CONFIRM_MAX_FAILURES:
            return Response(
                {"detail": "Too many incorrect cash-out codes — try again shortly.", "code": "locked"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        from accounts.models import DriverCashoutRequest, Customer as _Cust
        req = (
            DriverCashoutRequest.objects
            .filter(code=code, status=DriverCashoutRequest.Status.PENDING, expires_at__gt=timezone.now())
            .order_by("-created_at").first()
        )
        if req is None:
            try:
                _cache.add(_fail_key, 0, CASHOUT_CONFIRM_LOCK_SECONDS)
                _cache.incr(_fail_key)
            except Exception:
                pass
            return Response({"detail": "No pending cash-out for that code.", "code": "not_found"},
                            status=status.HTTP_404_NOT_FOUND)
        driver = _Cust.objects.filter(pk=req.driver_id).only("name", "phone").first()
        return Response({
            "request_id": req.id,
            "amount": str(req.amount),
            "currency": req.currency,
            "driver_name": (getattr(driver, "name", "") or getattr(driver, "phone", "") or "Driver"),
        })


class OwnerDriverCashoutConfirmView(APIView):
    """POST /api/owner/driver-cashout/confirm/  body {code} — restaurant confirms it handed
    the driver cash. Atomically debits the driver's wallet + credits this restaurant's float."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [DriverCashoutConfirmThrottle]  # OPS-5e: brute-force backstop

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Restaurant context required.", "code": "no_tenant"}, status=status.HTTP_400_BAD_REQUEST)
        code = (request.data.get("code") or "").strip()
        if not code:
            return Response({"detail": "code is required.", "code": "missing_code"}, status=status.HTTP_400_BAD_REQUEST)

        from accounts.driver_service import confirm_cashout, CashoutError
        from accounts.wallet_service import InsufficientFunds, WalletError
        try:
            req = confirm_cashout(code, tenant_id=tenant.id, actor_user_id=getattr(request.user, "id", None))
        except InsufficientFunds:
            return Response({"detail": "The driver's balance no longer covers this cash-out.",
                             "code": "insufficient_funds"}, status=status.HTTP_409_CONFLICT)
        except CashoutError as e:
            _http = status.HTTP_410_GONE if getattr(e, "code", "") == "expired" else status.HTTP_404_NOT_FOUND
            return Response({"detail": str(e), "code": getattr(e, "code", "cashout_error")}, status=_http)
        except WalletError as e:
            return Response({"detail": str(e), "code": "cashout_error"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"paid": True, "amount": str(req.amount)})


class OwnerDeliveryJobActionView(APIView):
    """POST /api/owner/orders/<order_id>/delivery-action/  body {action, ...}

    Owner resolves a failed / stuck delivery job:
      - "redispatch"      → re-offer the SAME job to the driver pool (reuses the row).
      - "refund_cancel"   → cancel the order + refund wallet + reverse loyalty + restock.
      - "confirm_noshow"  → pay the driver for a customer-no-show failure (owner-confirmed).
    Owner/manager of the tenant only. All actions are idempotent.
    """
    permission_classes = [IsAuthenticated]

    MAX_REDISPATCH = 3

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Restaurant context required.", "code": "no_tenant"}, status=status.HTTP_400_BAD_REQUEST)

        action = (request.data.get("action") or "").strip()
        if action not in ("redispatch", "refund_cancel", "confirm_noshow"):
            return Response({"detail": "Unknown action.", "code": "bad_action"}, status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(pk=order_id).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        from django.db import transaction as _tx
        from django.utils import timezone as _tz
        from accounts.models import DeliveryJob as _DJob

        # ── Refund & cancel ────────────────────────────────────────────────────
        if action == "refund_cancel":
            with _tx.atomic():
                if order.status != Order.Status.CANCELLED:
                    order.status = Order.Status.CANCELLED
                    order.status_updated_at = _tz.now()
                    order.save(update_fields=["status", "status_updated_at", "updated_at"])
                _refund_wallet_for_cancelled_order(order, tenant_id=tenant.id)   # idempotent
                _reverse_loyalty_for_cancelled_order(order)
                _restock_cancelled_order(order)
            try:
                from accounts.delivery_service import cancel_delivery_job_for_order
                cancel_delivery_job_for_order(tenant.id, order.order_number)
                _DJob.objects.filter(tenant_id=tenant.id, order_number=order.order_number).update(
                    resolution=_DJob.Resolution.REFUNDED_CANCELLED
                )
            except Exception:
                pass
            _broadcast_order_change(order)
            return Response({"ok": True, "order_status": order.status,
                             "payment_status": order.payment_status, "resolution": "refunded_cancelled"})

        # ── Re-dispatch / confirm no-show (operate on the job) ──────────────────
        with _tx.atomic():
            job = (
                _DJob.objects.select_for_update()
                .filter(tenant_id=tenant.id, order_number=order.order_number)
                .first()
            )
            if job is None:
                return Response({"detail": "No delivery job for this order.", "code": "no_job"}, status=status.HTTP_404_NOT_FOUND)

            if action == "redispatch":
                if job.status != _DJob.Status.FAILED:
                    return Response({"detail": "This job isn't awaiting a decision.", "code": "job_changed"}, status=status.HTTP_409_CONFLICT)
                if (job.redispatch_count or 0) >= self.MAX_REDISPATCH:
                    return Response({"detail": "Re-dispatched too many times — refund instead.", "code": "redispatch_limit"}, status=status.HTTP_409_CONFLICT)
                job.driver = None
                job.status = _DJob.Status.SEARCHING
                job.assigned_at = None
                job.picked_up_at = None
                job.failed_at = None
                job.failure_reason = ""
                job.failure_note = ""
                job.owner_alerted_at = None
                job.code_attempts = 0
                job.code_locked_until = None
                job.redispatch_count = (job.redispatch_count or 0) + 1
                job.resolution = _DJob.Resolution.REDISPATCHED
                # Fresh ranked-offer cascade (any driver eligible again).
                job.offered_to = None
                job.offer_expires_at = None
                job.declined_by = []
                job.offer_round = 0
                job.is_open_pool = False
                job.save(update_fields=[
                    "driver", "status", "assigned_at", "picked_up_at", "failed_at",
                    "failure_reason", "failure_note", "owner_alerted_at", "code_attempts",
                    "code_locked_until", "redispatch_count", "resolution",
                    "offered_to", "offer_expires_at", "declined_by", "offer_round", "is_open_pool",
                ])

            elif action == "confirm_noshow":
                if job.status != _DJob.Status.FAILED or job.failure_reason != _DJob.FailureReason.CUSTOMER_NO_SHOW:
                    return Response({"detail": "Only a no-show failure can be paid.", "code": "not_noshow"}, status=status.HTTP_409_CONFLICT)
                if not job.driver_id or (job.driver_payout or 0) <= 0:
                    return Response({"detail": "Nothing to pay this driver.", "code": "no_payout"}, status=status.HTTP_400_BAD_REQUEST)
                from accounts.wallet_service import credit_wallet
                from accounts.models import WalletTransaction as _WT
                credit_wallet(
                    job.driver_id, job.driver_payout, tx_type=_WT.Type.EARNING,
                    idempotency_key=f"noshow:{job.id}", reference=f"noshow:{order.order_number}",
                    tenant_id=tenant.id, note="No-show payout", require_verified=False,
                )
                if not job.resolution:
                    job.resolution = _DJob.Resolution.NOSHOW_PAID
                    job.save(update_fields=["resolution"])

        if action == "redispatch":
            try:
                # Re-enter the ranked-offer cascade (nearest driver first, then pool).
                from accounts.dispatch import offer_to_next_driver
                offer_to_next_driver(job.id)
            except Exception:
                pass
            # Keep the customer timeline coherent: a re-dispatched order isn't "out for delivery".
            try:
                if order.status == Order.Status.OUT_FOR_DELIVERY:
                    order.status = Order.Status.READY
                    order.status_updated_at = _tz.now()
                    order.save(update_fields=["status", "status_updated_at", "updated_at"])
                    _broadcast_order_change(order)
            except Exception:
                pass
            return Response({"ok": True, "resolution": "redispatched"})
        return Response({"ok": True, "resolution": "noshow_paid"})


class OwnerDeliveryTrackView(APIView):
    """GET /api/owner/orders/<order_id>/delivery-track/ — live driver position +
    route + ETA so the restaurant can follow the delivery on a map (same payload the
    customer tracker uses). Owner/manager of the tenant only.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Restaurant context required.", "code": "no_tenant"}, status=status.HTTP_400_BAD_REQUEST)
        order = Order.objects.filter(pk=order_id).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        from accounts.models import DeliveryJob as _DJob
        job = (
            _DJob.objects.select_related("driver")
            .filter(tenant_id=tenant.id, order_number=order.order_number)
            .first()
        )
        if job is None:
            return Response({"detail": "No delivery job for this order.", "code": "no_job"}, status=status.HTTP_404_NOT_FOUND)
        from accounts.views import _serialize_delivery_job
        return Response(_serialize_delivery_job(job, include_driver_position=True))


class OwnerNotificationsView(APIView):
    """GET /api/owner/notifications/ — the outbound-notification audit log for this tenant
    (web push + email + SMS + WhatsApp attempts and outcomes). Owner/manager only. Supports
    ?channel= and ?status= filters; returns the most recent 100 rows + a status summary.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        tenant = getattr(request, "tenant", None)
        tenant_id = tenant.id if tenant else None

        from accounts.models import NotificationLog
        qs = NotificationLog.objects.filter(tenant_id=tenant_id)
        channel = (request.query_params.get("channel") or "").strip().lower()
        if channel:
            qs = qs.filter(channel=channel)
        status_f = (request.query_params.get("status") or "").strip().lower()
        if status_f:
            qs = qs.filter(status=status_f)

        from django.db.models import Count as _Count
        summary = {row["status"]: row["n"] for row in (
            NotificationLog.objects.filter(tenant_id=tenant_id)
            .values("status").annotate(n=_Count("id"))
        )}
        rows = list(qs.order_by("-created_at")[:100])
        return Response({
            "summary": summary,
            "results": [
                {
                    "id": n.id, "channel": n.channel, "event": n.event, "status": n.status,
                    "recipient": n.recipient, "detail": n.detail, "reference": n.reference,
                    "error": n.error, "created_at": n.created_at.isoformat(),
                }
                for n in rows
            ],
        })


class OwnerOrderListView(APIView):
    """GET /api/owner/orders/ — owner lists all orders.

    OPS-4 A — two-mode design to avoid full-table scan on every 15-second poll:

    HOT path (default, ?mode=active or no mode):
      Returns only non-terminal orders (pending / confirmed / preparing / ready /
      out_for_delivery / scheduled). These are naturally bounded (a few dozen at
      most at any given time) so no COUNT and no date fence is needed.
      Response: { results, has_more: false, limit: null, offset: null }
      (has_more is always false on the hot path — the set is always complete.)

    HISTORY path (?mode=history):
      Returns terminal orders (completed / cancelled), paginated with limit/offset.
      Supports ?from= and ?to= date fences (YYYY-MM-DD) and ?status= to narrow
      to a single terminal status.
      Response: { results, has_more: bool, limit: int, offset: int }
      (count is omitted on this path to avoid an expensive COUNT(*) every call.)

    EXPLICIT STATUS FILTER (?status=<any>):
      When ?status= is supplied the mode param is ignored; returns all orders with
      that status using limit/offset pagination — this covers the legacy case where
      the SPA requests a specific status directly.

    Per-row ledger totals (amount_paid / outstanding): fetched via a per-page
    prefetch on OrderPayment — no JOIN-heavy annotate that forces a COUNT.
    """
    permission_classes = [IsAuthenticated]

    # Statuses that are considered "active" (non-terminal) for the hot poll path.
    ACTIVE_STATUSES = [
        Order.Status.SCHEDULED,
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PREPARING,
        Order.Status.READY,
        Order.Status.OUT_FOR_DELIVERY,
    ]
    # Terminal statuses served via the history path.
    TERMINAL_STATUSES = [
        Order.Status.COMPLETED,
        Order.Status.CANCELLED,
    ]
    # Default page size for history / explicit-status paginated responses.
    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get("status", "").strip().lower()
        mode = request.query_params.get("mode", "active").strip().lower()
        valid_statuses = {s.value for s in Order.Status}

        # ── Parse limit / offset for paginated paths ──────────────────────────
        try:
            _limit = int(request.query_params.get("limit") or self.DEFAULT_LIMIT)
            _limit = max(1, min(_limit, self.MAX_LIMIT))
        except (ValueError, TypeError):
            _limit = self.DEFAULT_LIMIT
        try:
            _offset = int(request.query_params.get("offset") or 0)
            _offset = max(0, _offset)
        except (ValueError, TypeError):
            _offset = 0

        # ── Build base queryset (no annotate, no COUNT) ───────────────────────
        qs = (
            Order.objects
            .select_related("customer")
            .prefetch_related("items")
            .order_by("-created_at")
        )

        # ── Route to correct status filter / pagination mode ──────────────────
        # NOTE: date-fence (?from= / ?to=) is intentionally parsed and applied
        # INSIDE the non-active branches only.  The active hot-path must never
        # be date-fenced: a scheduled order placed days ago but still in an
        # active status (pending/scheduled/…) would otherwise be silently
        # dropped from every 15-second poll.
        if status_filter and status_filter in valid_statuses:
            # Explicit single-status filter — paginated, date-fenced.
            from_date = request.query_params.get("from", "").strip()
            to_date = request.query_params.get("to", "").strip()
            if from_date:
                try:
                    from datetime import date as _date
                    _from_dt = _date.fromisoformat(from_date)
                    qs = qs.filter(created_at__date__gte=_from_dt)
                except ValueError:
                    pass
            if to_date:
                try:
                    from datetime import date as _date
                    _to_dt = _date.fromisoformat(to_date)
                    qs = qs.filter(created_at__date__lte=_to_dt)
                except ValueError:
                    pass
            qs = qs.filter(status=status_filter)
            all_orders = list(qs[_offset: _offset + _limit + 1])
            has_more = len(all_orders) > _limit
            all_orders = all_orders[:_limit]
            return_limit, return_offset = _limit, _offset
        elif mode == "history":
            # Terminal orders — paginated, date-fenced.
            from_date = request.query_params.get("from", "").strip()
            to_date = request.query_params.get("to", "").strip()
            if from_date:
                try:
                    from datetime import date as _date
                    _from_dt = _date.fromisoformat(from_date)
                    qs = qs.filter(created_at__date__gte=_from_dt)
                except ValueError:
                    pass
            if to_date:
                try:
                    from datetime import date as _date
                    _to_dt = _date.fromisoformat(to_date)
                    qs = qs.filter(created_at__date__lte=_to_dt)
                except ValueError:
                    pass
            qs = qs.filter(status__in=self.TERMINAL_STATUSES)
            all_orders = list(qs[_offset: _offset + _limit + 1])
            has_more = len(all_orders) > _limit
            all_orders = all_orders[:_limit]
            return_limit, return_offset = _limit, _offset
        else:
            # Default hot path — active/non-terminal orders only, no COUNT.
            # Date-fence params are IGNORED here by design: the active path
            # must surface every non-terminal order regardless of age.
            qs = qs.filter(status__in=self.ACTIVE_STATUSES)
            all_orders = list(qs)
            has_more = False
            return_limit, return_offset = None, None

        # ── Per-page ledger totals (no JOIN-heavy annotate, no full-table scan) ─
        # Fetch OrderPayment rows only for the orders in this page.
        from menu.models import OrderPayment as _OP
        _order_ids_page = [o.id for o in all_orders]
        _payments_by_order: dict = {}
        if _order_ids_page:
            for _pay in _OP.objects.filter(order_id__in=_order_ids_page).values("order_id", "amount"):
                _payments_by_order.setdefault(_pay["order_id"], Decimal("0"))
                _payments_by_order[_pay["order_id"]] += Decimal(str(_pay["amount"] or 0))

        def _safe_ledger(value):
            """Coerce to quantized Decimal; returns 0.00 for None/non-numeric."""
            try:
                return Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else Decimal("0.00")
            except Exception:
                return Decimal("0.00")

        # ── Batch-load customer trust scores ─────────────────────────────────
        from accounts.models import CustomerRating as _CR
        from django.db.models import Avg as _Avg, Count as _Count2
        tenant = getattr(request, "tenant", None)
        tenant_id = tenant.id if tenant else None

        # Reconcile any approved-but-unsynced wallet charge requests into these bills, so a
        # charge a customer approved after the owner closed the charge sheet still shows as
        # paid here (and can't be accidentally charged again). Claim-safe + best-effort.
        try:
            _applied = _sync_charged_request_bills(tenant_id, [o.order_number for o in all_orders])
            if _applied:
                for _o in all_orders:
                    if _o.order_number in _applied:
                        _o.wallet_amount_paid = (_o.wallet_amount_paid or Decimal("0")) + _applied[_o.order_number]
        except Exception:
            pass  # never break the order list over bill reconciliation

        customer_ids = list({o.customer_id for o in all_orders if o.customer_id})
        trust_map: dict = {}      # customer_id → {avg_score, rating_count}
        my_rating_map: dict = {}  # order_number → {score, note}
        if customer_ids:
            for agg in (_CR.objects
                        .filter(customer_id__in=customer_ids)
                        .values("customer_id")
                        .annotate(avg=_Avg("score"), cnt=_Count2("id"))):
                trust_map[agg["customer_id"]] = {
                    "avg_score": round(float(agg["avg"]), 1) if agg["avg"] else None,
                    "rating_count": agg["cnt"],
                }
            if tenant_id:
                order_nums = [o.order_number for o in all_orders if o.customer_id]
                for cr in (_CR.objects
                           .filter(tenant_id=tenant_id, order_number__in=order_nums,
                                   customer_id__in=customer_ids)
                           .values("order_number", "score", "note")):
                    my_rating_map[cr["order_number"]] = {"score": cr["score"], "note": cr["note"]}

        # ── Batch-load delivery job data (public schema — shared model) ─────────
        from accounts.models import DeliveryJob as _DJ
        delivery_job_map: dict = {}  # order_number → serialised job dict
        if tenant_id:
            marketplace_order_nums = [
                o.order_number for o in all_orders if getattr(o, "source", "") == "marketplace"
            ]
            if marketplace_order_nums:
                for _dj in (_DJ.objects.select_related("driver")
                            .filter(tenant_id=tenant_id,
                                    order_number__in=marketplace_order_nums)):
                    _drv = _dj.driver
                    delivery_job_map[_dj.order_number] = {
                        "id": _dj.id,
                        "status": _dj.status,
                        "driver": {
                            "id": _drv.id,
                            "name": _drv.name or "",
                            "phone": _drv.phone or "",
                            "is_online": _drv.is_driver_online,
                        } if _drv else None,
                        "pickup_address": _dj.pickup_address,
                        "delivery_address": _dj.delivery_address,
                        "delivery_fee": str(_dj.delivery_fee),
                        "driver_payout": str(_dj.driver_payout),
                        "assigned_at": _dj.assigned_at.isoformat() if _dj.assigned_at else None,
                        "picked_up_at": _dj.picked_up_at.isoformat() if _dj.picked_up_at else None,
                        "delivered_at": _dj.delivered_at.isoformat() if _dj.delivered_at else None,
                        "failure_reason": _dj.failure_reason,
                        "failure_note": _dj.failure_note,
                        "redispatch_count": _dj.redispatch_count,
                        "resolution": _dj.resolution,
                        "restaurant_driver_rating": _dj.restaurant_driver_rating,
                        "restaurant_driver_note": _dj.restaurant_driver_note,
                    }

        # VAT settings (read once) — prices are VAT-inclusive; we only break out
        # the tax portion per order for display/reporting.
        try:
            _vat_profile = request.tenant.profile
            _vat_rate = getattr(_vat_profile, "vat_rate", 0)
            _vat_label = getattr(_vat_profile, "vat_label", "") or ""
        except Exception:
            _vat_rate, _vat_label = 0, ""

        # ── Section + responsible waiter(s) for table orders ───────────────────
        # So the owner can see WHO covers each table at a glance.
        section_by_slug: dict = {}  # slug → {"name": str, "waiters": [names]}
        try:
            _table_slugs = [o.table_slug for o in all_orders if o.table_slug]
            if _table_slugs:
                _tl_rows = list(
                    TableLink.objects.filter(slug__in=_table_slugs)
                    .values("slug", "section_id", "section__name")
                )
                _section_ids = {r["section_id"] for r in _tl_rows if r["section_id"]}
                _servers_by_section: dict = {}
                _uid_set = set()
                if _section_ids:
                    for ss in SectionServer.objects.filter(section_id__in=_section_ids).values("section_id", "user_id"):
                        _servers_by_section.setdefault(ss["section_id"], []).append(ss["user_id"])
                        _uid_set.add(ss["user_id"])
                _name_map = {}
                if _uid_set:
                    from accounts.models import User as _User
                    for u in _User.objects.filter(id__in=list(_uid_set)).values("id", "name", "email"):
                        _name_map[u["id"]] = u["name"] or u["email"]
                for r in _tl_rows:
                    _waiters = [_name_map.get(uid, "") for uid in _servers_by_section.get(r["section_id"], [])]
                    section_by_slug[r["slug"]] = {
                        "name": r["section__name"] or "",
                        "waiters": [w for w in _waiters if w],
                    }
        except Exception:
            section_by_slug = {}  # best-effort — never break the order list

        orders = []
        for order in all_orders:
            orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "fulfillment_type": order.fulfillment_type,
                "table_label": order.table_label,
                # Floor section + the waiter(s) responsible for this table.
                "section_name": section_by_slug.get(order.table_slug, {}).get("name", "") if order.table_slug else "",
                "responsible_waiters": section_by_slug.get(order.table_slug, {}).get("waiters", []) if order.table_slug else [],
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "customer_email": order.customer.email if order.customer else "",
                "customer_note": order.customer_note,
                "delivery_address": order.delivery_address,
                "delivery_location_url": order.delivery_location_url,
                "delivery_lat": order.delivery_lat,
                "delivery_lng": order.delivery_lng,
                "total": str(order.total),
                "delivery_fee": str(order.delivery_fee),
                "tip_amount": str(order.tip_amount),
                **order_vat_fields(order, _vat_rate, _vat_label),
                "currency": order.currency,
                "owner_note": order.owner_note,
                "estimated_ready_minutes": order.estimated_ready_minutes,
                "scheduled_for": order.scheduled_for.isoformat() if order.scheduled_for else None,
                "items_count": sum(i.qty for i in order.items.all()),
                "fired_course": getattr(order, "fired_course", 1),
                "items": [
                    {
                        "dish_name": i.dish_name,
                        "dish_slug": i.dish_slug,
                        "qty": i.qty,
                        "unit_price": str(i.unit_price),
                        "subtotal": str(i.subtotal),
                        "options": i.options,
                        "note": i.note,
                        "is_voided": i.is_voided,
                        "combo_components": i.combo_components,
                        "course": getattr(i, "course", 0),
                    }
                    for i in order.items.all()
                ],
                "created_at": order.created_at.isoformat(),
                "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
                # Platform-level customer trust data (public schema, cross-tenant)
                "customer_id": order.customer_id,
                "customer_trust": trust_map.get(order.customer_id) if order.customer_id else None,
                "my_customer_rating": my_rating_map.get(order.order_number),
                # Wallet payment
                "wallet_amount_paid": str(order.wallet_amount_paid) if order.wallet_amount_paid else "0",
                # Split-bill ledger (R4): partial-payment progress for the owner list.
                # OPS-4 A: fetched per-page via _payments_by_order, NOT via an annotate
                # that forces a JOIN-COUNT over the entire table on every poll.
                "amount_paid": str(_safe_ledger(_payments_by_order.get(order.id))),
                "outstanding": str(
                    max(
                        Decimal("0"),
                        _safe_ledger(getattr(order, "total", None))
                        - _safe_ledger(_payments_by_order.get(order.id)),
                    ).quantize(Decimal("0.01"))
                ),
                # Order source, commission & promotion
                "source": order.source,
                "commission_amount": str(order.commission_amount),
                "promotion_discount": str(order.promotion_discount),
                "applied_promotion_name": order.applied_promotion_name,
                # Delivery job (marketplace orders with active delivery)
                "delivery_job": delivery_job_map.get(order.order_number),
            })

        return Response({
            "results": orders,
            "has_more": has_more,
            "limit": return_limit,
            "offset": return_offset,
        })


class OwnerOrderDetailView(APIView):
    """GET /api/owner/orders/<id>/ — single order detail."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").prefetch_related("items", "payments").filter(id=order_id).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # ── Customer trust info (public schema) ───────────────────────────────
        from accounts.models import CustomerRating as _CR
        from django.db.models import Avg as _Avg, Count as _Count2
        customer_trust = None
        if order.customer_id:
            _tenant = getattr(request, "tenant", None)
            _tid = _tenant.id if _tenant else None
            agg = (_CR.objects
                   .filter(customer_id=order.customer_id)
                   .aggregate(avg=_Avg("score"), cnt=_Count2("id")))
            my_rating = None
            if _tid:
                _cr = (_CR.objects
                       .filter(customer_id=order.customer_id, tenant_id=_tid,
                               order_number=order.order_number)
                       .first())
                if _cr:
                    my_rating = {"score": _cr.score, "note": _cr.note}
            customer_trust = {
                "avg_score": round(float(agg["avg"]), 1) if agg["avg"] else None,
                "rating_count": agg["cnt"],
                "my_rating": my_rating,
            }

        # ── Delivery job lookup (public schema shared model) ─────────────────
        _dj_data = None
        _detail_tenant = getattr(request, "tenant", None)
        if _detail_tenant and getattr(order, "source", "") == "marketplace":
            from accounts.models import DeliveryJob as _DJD
            _dj = (_DJD.objects.select_related("driver")
                   .filter(tenant_id=_detail_tenant.id,
                           order_number=order.order_number).first())
            if _dj:
                _drv = _dj.driver
                _dj_data = {
                    "id": _dj.id,
                    "status": _dj.status,
                    "driver": {
                        "id": _drv.id,
                        "name": _drv.name or "",
                        "phone": _drv.phone or "",
                        "is_online": _drv.is_driver_online,
                    } if _drv else None,
                    "pickup_address": _dj.pickup_address,
                    "delivery_address": _dj.delivery_address,
                    "delivery_fee": str(_dj.delivery_fee),
                    "driver_payout": str(_dj.driver_payout),
                    "assigned_at": _dj.assigned_at.isoformat() if _dj.assigned_at else None,
                    "picked_up_at": _dj.picked_up_at.isoformat() if _dj.picked_up_at else None,
                    "delivered_at": _dj.delivered_at.isoformat() if _dj.delivered_at else None,
                    "failure_reason": _dj.failure_reason,
                    "failure_note": _dj.failure_note,
                    "redispatch_count": _dj.redispatch_count,
                    "resolution": _dj.resolution,
                    "restaurant_driver_rating": _dj.restaurant_driver_rating,
                    "restaurant_driver_note": _dj.restaurant_driver_note,
                }

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "table_label": order.table_label,
            "table_slug": order.table_slug,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "customer_email": order.customer.email if order.customer else "",
            "customer_note": order.customer_note,
            "delivery_address": order.delivery_address,
            "delivery_location_url": order.delivery_location_url,
            "delivery_lat": order.delivery_lat,
            "delivery_lng": order.delivery_lng,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "tip_amount": str(order.tip_amount),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "fired_course": getattr(order, "fired_course", 1),
            "items": [
                {
                    "id": i.id,
                    "dish_name": i.dish_name,
                    "dish_slug": i.dish_slug,
                    "qty": i.qty,
                    "unit_price": str(i.unit_price),
                    "subtotal": str(i.subtotal),
                    "options": i.options,
                    "note": i.note,
                    "is_voided": i.is_voided,
                    # Contract F: void_reason surfaced in owner order-detail payload
                    "void_reason": i.void_reason if i.is_voided else None,
                    "voided_at": i.voided_at.isoformat() if i.is_voided and i.voided_at else None,
                    "combo_components": i.combo_components,
                    "course": getattr(i, "course", 0),
                }
                for i in order.items.all()
            ],
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
            "customer_id": order.customer_id,
            "customer_trust": customer_trust,
            "source": order.source,
            "commission_amount": str(order.commission_amount),
            "promotion_discount": str(order.promotion_discount),
            "applied_promotion_name": order.applied_promotion_name,
            "delivery_job": _dj_data,
            # Contract F: payment ledger rows surfaced in owner order-detail.
            # recorded_by_name lets the owner see who took cash / processed wallet.
            # Correction audit fields included so corrections are visible too.
            "payments": [
                {
                    "id": p.id,
                    "amount": str(p.amount),
                    "method": p.method,
                    "recorded_by_name": p.recorded_by_name or None,
                    "note": p.note or None,
                    "created_at": p.created_at.isoformat(),
                    "original_method": p.original_method or None,
                    "corrected_at": p.corrected_at.isoformat() if p.corrected_at else None,
                    "corrected_by_name": p.corrected_by_name or None,
                }
                for p in order.payments.all()
            ],
        })


class OwnerCustomerRatingView(APIView):
    """
    POST /api/owner/orders/<order_id>/customer-rating/

    The staff member who SERVED the customer rates their trustworthiness after
    the order — the waiter/server (or an owner who personally handled it), never
    an owner rating from behind the dashboard who never met them. The rating is
    stored in the public schema (shared across tenants) and is never shown to the
    customer directly — it contributes to an aggregate trust score visible to
    restaurants when the same customer orders again.

    Request body:
        { "score": 1–5, "note": "optional text" }

    Responses:
        200 OK — rating saved or updated; body: {score, note, avg_score, rating_count}
        400 Bad Request — invalid score or order has no linked customer
        403 Forbidden — caller did not handle/serve this order
        404 Not Found — unknown order_id
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").filter(id=order_id).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the person who actually served the customer may rate them — the
        # staff/waiter (or owner) who handled this order. An owner who never met
        # the customer cannot rate from behind the dashboard.
        _uid = getattr(request.user, "id", None)
        if not order.handled_by_user_id or order.handled_by_user_id != _uid:
            return Response(
                {
                    "detail": "Only the staff member who served this order can rate the customer.",
                    "code": "not_server",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not order.customer_id:
            return Response(
                {"detail": "This order has no linked customer account.", "code": "no_customer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate score
        score_raw = request.data.get("score")
        try:
            score = int(score_raw)
            if score < 1 or score > 5:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "Score must be an integer between 1 and 5.", "code": "invalid_score"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        note = str(request.data.get("note", "") or "").strip()[:200]

        tenant = getattr(request, "tenant", None)
        tenant_id = tenant.id if tenant else 0

        from accounts.models import CustomerRating as _CR
        from django.db.models import Avg as _Avg, Count as _Count2

        cr, _ = _CR.objects.update_or_create(
            customer_id=order.customer_id,
            tenant_id=tenant_id,
            order_number=order.order_number,
            defaults={"score": score, "note": note},
        )

        # Return updated aggregate trust score
        agg = (_CR.objects
               .filter(customer_id=order.customer_id)
               .aggregate(avg=_Avg("score"), cnt=_Count2("id")))

        return Response({
            "score": cr.score,
            "note": cr.note,
            "avg_score": round(float(agg["avg"]), 1) if agg["avg"] else None,
            "rating_count": agg["cnt"],
        }, status=status.HTTP_200_OK)


def _serialize_promotion(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "promo_type": p.promo_type,
        "discount_value": str(p.discount_value),
        "min_order_amount": str(p.min_order_amount),
        "days": p.days or [],
        "time_start": p.time_start or "",
        "time_end": p.time_end or "",
        "active_from": p.active_from.isoformat() if p.active_from else None,
        "active_until": p.active_until.isoformat() if p.active_until else None,
        "is_active": p.is_active,
        "max_uses": p.max_uses,
        "use_count": p.use_count,
        "is_platform_flash": p.is_platform_flash,
        "code": p.code or "",
        "created_at": p.created_at.isoformat(),
    }


class OwnerPromotionListCreateView(APIView):
    """GET /api/owner/promotions/ — list promotions.
       POST /api/owner/promotions/ — create a promotion."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        promos = Promotion.objects.all()
        return Response([_serialize_promotion(p) for p in promos])

    def post(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from decimal import Decimal as _Dec, InvalidOperation
        from datetime import date as _date

        name = str(request.data.get("name") or "").strip()[:100]
        if not name:
            return Response({"detail": "name is required.", "code": "missing_name"}, status=status.HTTP_400_BAD_REQUEST)

        promo_type = str(request.data.get("promo_type") or "percentage").strip()
        if promo_type not in ("percentage", "fixed", "free_delivery"):
            return Response({"detail": "Invalid promo_type.", "code": "invalid_type"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            discount_value = _Dec(str(request.data.get("discount_value") or "0")).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            discount_value = _Dec("0")

        try:
            min_order_amount = _Dec(str(request.data.get("min_order_amount") or "0")).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            min_order_amount = _Dec("0")

        _VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        raw_days = request.data.get("days") or []
        days = [d for d in (raw_days if isinstance(raw_days, list) else []) if d in _VALID_DAYS]

        def _parse_hhmm(val):
            v = str(val or "").strip()
            if len(v) == 5 and v[2] == ":" and v[:2].isdigit() and v[3:].isdigit():
                return v
            return ""

        time_start = _parse_hhmm(request.data.get("time_start"))
        time_end = _parse_hhmm(request.data.get("time_end"))

        def _parse_date(val):
            try:
                return _date.fromisoformat(str(val))
            except (ValueError, TypeError):
                return None

        active_from = _parse_date(request.data.get("active_from"))
        active_until = _parse_date(request.data.get("active_until"))

        max_uses_raw = request.data.get("max_uses")
        max_uses = None
        if max_uses_raw is not None:
            try:
                max_uses = max(1, int(max_uses_raw))
            except (TypeError, ValueError):
                max_uses = None

        raw_code = str(request.data.get("code") or "").strip().upper()[:20]

        promo = Promotion.objects.create(
            name=name,
            description=str(request.data.get("description") or "").strip()[:200],
            promo_type=promo_type,
            discount_value=discount_value,
            min_order_amount=min_order_amount,
            days=days,
            time_start=time_start,
            time_end=time_end,
            active_from=active_from,
            active_until=active_until,
            is_active=bool(request.data.get("is_active", True)),
            max_uses=max_uses,
            code=raw_code,
        )
        return Response(_serialize_promotion(promo), status=status.HTTP_201_CREATED)


class OwnerPromotionDetailView(APIView):
    """GET /api/owner/promotions/<id>/ — retrieve.
       PATCH /api/owner/promotions/<id>/ — update.
       DELETE /api/owner/promotions/<id>/ — delete."""

    permission_classes = [IsAuthenticated]

    def _get_promo(self, request, promo_id):
        if not _is_tenant_owner(request):
            return None, Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        p = Promotion.objects.filter(pk=promo_id).first()
        if p is None:
            return None, Response({"detail": "Promotion not found."}, status=status.HTTP_404_NOT_FOUND)
        return p, None

    def get(self, request, promo_id, *args, **kwargs):
        p, err = self._get_promo(request, promo_id)
        if err:
            return err
        return Response(_serialize_promotion(p))

    def patch(self, request, promo_id, *args, **kwargs):
        from decimal import Decimal as _Dec, InvalidOperation
        from datetime import date as _date

        p, err = self._get_promo(request, promo_id)
        if err:
            return err

        data = request.data
        if "name" in data:
            p.name = str(data["name"] or "").strip()[:100]
        if "description" in data:
            p.description = str(data["description"] or "").strip()[:200]
        if "promo_type" in data:
            pt = str(data["promo_type"]).strip()
            if pt in ("percentage", "fixed", "free_delivery"):
                p.promo_type = pt
        if "discount_value" in data:
            try:
                p.discount_value = _Dec(str(data["discount_value"])).quantize(_Dec("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                pass
        if "min_order_amount" in data:
            try:
                p.min_order_amount = _Dec(str(data["min_order_amount"])).quantize(_Dec("0.01"))
            except (InvalidOperation, TypeError, ValueError):
                pass
        _VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        if "days" in data:
            raw = data["days"] or []
            p.days = [d for d in (raw if isinstance(raw, list) else []) if d in _VALID_DAYS]
        if "time_start" in data:
            v = str(data["time_start"] or "").strip()
            p.time_start = v if len(v) == 5 and v[2] == ":" else ""
        if "time_end" in data:
            v = str(data["time_end"] or "").strip()
            p.time_end = v if len(v) == 5 and v[2] == ":" else ""
        if "active_from" in data:
            try:
                p.active_from = _date.fromisoformat(str(data["active_from"])) if data["active_from"] else None
            except (ValueError, TypeError):
                pass
        if "active_until" in data:
            try:
                p.active_until = _date.fromisoformat(str(data["active_until"])) if data["active_until"] else None
            except (ValueError, TypeError):
                pass
        if "is_active" in data:
            p.is_active = bool(data["is_active"])
        if "max_uses" in data:
            raw = data["max_uses"]
            p.max_uses = max(1, int(raw)) if raw is not None else None
        if "code" in data:
            p.code = str(data["code"] or "").strip().upper()[:20]
        p.save()
        return Response(_serialize_promotion(p))

    def delete(self, request, promo_id, *args, **kwargs):
        p, err = self._get_promo(request, promo_id)
        if err:
            return err
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _refund_wallet_for_cancelled_order(order, tenant_id=None) -> None:
    """Credit the customer's wallet when a wallet-paid order is cancelled.

    Routes through ``wallet_service.credit_wallet`` so the refund shares the platform's
    single, locked, idempotent money path: credit_wallet locks the customer row, writes
    a balance_after snapshot, and replays safely on retry. The idempotency key is
    SCHEMA-NAMESPACED — f"cancelrefund:{schema}:{order.id}" — because WalletTransaction
    lives in the shared public schema where idempotency_key is a GLOBAL namespace. The
    old guard filtered on (customer_id, type=REFUND, reference=order_number, note), but
    order_number is only schema-unique, so a cross-tenant customer with a colliding
    order_number could have a legitimate tenant-B refund SILENTLY SKIPPED by matching a
    tenant-A row. order.id is the tenant-schema PK; the schema prefix makes the key
    globally unique.

    tenant_id: the integer PK of the tenant that owns this order.  Pass it so the
    WalletTransaction row can be filtered per-tenant in refund reports (WalletTransaction
    lives in the shared public schema; without tenant_id the query would aggregate
    refunds from ALL tenants).  Callers should supply ``request.tenant.id`` or the
    local ``tenant.id`` variable — both cancel entry-points have a tenant reference.
    """
    from decimal import Decimal as _Dec
    from django.db import connection as _conn
    from accounts.models import WalletTransaction as _WTM
    # Local import: wallet_service imports accounts models, so importing it at module
    # level here risks an import cycle through menu.views — import inside the function.
    from accounts.wallet_service import credit_wallet as _credit_wallet

    if not order.customer_id:
        return
    refund_amount = _Dec(str(order.wallet_amount_paid or "0"))
    if refund_amount <= _Dec("0"):
        return

    # Schema-namespaced, globally-unique idempotency key. credit_wallet locks the
    # customer row, writes balance_after, and replays safely — replacing the manual
    # balance write + the order_number-based _already_refunded() guard.
    _credit_wallet(
        order.customer_id,
        refund_amount,
        tx_type=_WTM.Type.REFUND,
        idempotency_key=f"cancelrefund:{_conn.schema_name}:{order.id}",
        reference=order.order_number,
        note="Refund for cancelled order",
        # tenant_id tags this REFUND row to the owning tenant so that refund
        # aggregate queries in the Z-report and dashboard can filter per-tenant.
        tenant_id=tenant_id,
        # A refund is system-originated (like driver earnings): the refunded customer
        # paid with their wallet so they're already phone-verified, but skip the check
        # so an edge case can never refuse a refund the platform owes.
        require_verified=False,
    )


def _reverse_loyalty_for_cancelled_order(order) -> None:
    """Undo this order's loyalty effects on cancellation: claw back the points EARNED at
    placement and restore the points SPENT as a checkout discount. The net change is
    applied in one locked update, clamped at zero so a balance can never go negative.

    Call exactly once on the →CANCELLED transition. Both cancel entry points guard
    against re-cancelling (customer view 200-noops if already cancelled; the owner
    transition map has no edge out of CANCELLED), so this never double-applies.
    """
    from django.db import transaction as _dbtx
    from accounts.models import Customer as _CustM

    if not order.customer_id:
        return
    earned = int(getattr(order, "points_earned", 0) or 0)
    restored = int(getattr(order, "redeemed_loyalty_points", 0) or 0)
    delta = restored - earned
    if delta == 0:
        return
    with _dbtx.atomic():
        _cust = _CustM.objects.select_for_update().get(pk=order.customer_id)
        _new_balance = int(_cust.loyalty_points or 0) + delta
        if _new_balance < 0:
            _new_balance = 0
        _cust.loyalty_points = _new_balance
        _cust.save(update_fields=["loyalty_points", "updated_at"])


def _restock_cancelled_order(order) -> None:
    """Return reserved stock to inventory when an order is cancelled. Only affects
    dishes that track stock (stock_qty is not None); re-enables a dish that had gone
    sold-out. For combo items, also restocks each component (per-unit qty × item.qty).
    Best-effort. Called once per order (cancel is a one-way transition)."""
    from django.db import transaction as _dbtx
    from django.db.models import F as _F
    try:
        by_slug = {}
        # component restock: pk → total qty to return
        by_component_pk: dict = {}
        for it in order.items.all():
            if it.dish_slug:
                by_slug[it.dish_slug] = by_slug.get(it.dish_slug, 0) + int(it.qty or 0)
            # Combo component restock from the placement snapshot
            if it.combo_components:
                for _cc in it.combo_components:
                    _c_pk = _cc.get("dish_id")
                    _c_per_unit = int(_cc.get("qty", 1))
                    _item_qty = int(it.qty or 0)
                    if _c_pk is not None and _c_per_unit > 0 and _item_qty > 0:
                        by_component_pk[_c_pk] = by_component_pk.get(_c_pk, 0) + _c_per_unit * _item_qty
        if not by_slug and not by_component_pk:
            return
        # Merged single select_for_update across combo dishes (by slug) AND
        # components (by pk) so lock acquisition order is identical to
        # placement/void and cannot interleave with concurrent placement.
        with _dbtx.atomic():
            from django.db.models import Q as _Q
            _lock_q = _Q()
            if by_slug:
                _lock_q |= _Q(slug__in=list(by_slug.keys()))
            if by_component_pk:
                _lock_q |= _Q(pk__in=list(by_component_pk.keys()))
            _all_locked = list(Dish.objects.select_for_update().filter(_lock_q))
            for d in _all_locked:
                # Combo-dish restock (by slug)
                qty = by_slug.get(d.slug, 0)
                # Component restock (by pk)
                cqty = by_component_pk.get(d.pk, 0)
                # Merge into one update so a dish appearing in both maps (slug
                # match AND component pk match) is not incremented twice.
                total_qty = qty + cqty
                if total_qty > 0 and d.stock_qty is not None:
                    Dish.objects.filter(pk=d.pk).update(
                        stock_qty=_F("stock_qty") + total_qty, is_available=True, stock_auto_zeroed=False
                    )
    except Exception:
        pass  # restock is best-effort — never block a cancellation


def _customer_can_cancel(order) -> bool:
    """A customer may self-cancel only while the order is still early (scheduled, pending or
    confirmed) and is a pickup/delivery order — dine-in tabs are settled by staff, not
    self-cancelled. Advance/scheduled orders are cancellable until released to the kitchen."""
    return (
        order.status in (Order.Status.SCHEDULED, Order.Status.PENDING, Order.Status.CONFIRMED)
        and order.fulfillment_type != Order.FulfillmentType.TABLE
    )


class OwnerOrderStatusUpdateView(APIView):
    """PATCH /api/owner/orders/<id>/status/ — owner updates order status."""
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _allowed_transitions(order):
        """Allowed next statuses — fulfillment-type aware. Delivery gets an extra
        'Out for delivery' step; pickup & dine-in go straight Ready → Completed."""
        t = {
            # Scheduled (advance) orders are released into the live flow as PENDING by
            # the sweep; the owner may also release one early or cancel it.
            Order.Status.SCHEDULED: {Order.Status.PENDING, Order.Status.CANCELLED},
            Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
            Order.Status.CONFIRMED: {Order.Status.PREPARING, Order.Status.CANCELLED},
            Order.Status.PREPARING: {Order.Status.READY, Order.Status.CANCELLED},
            Order.Status.COMPLETED: set(),
            Order.Status.CANCELLED: set(),
        }
        if order.fulfillment_type == Order.FulfillmentType.DELIVERY:
            t[Order.Status.READY] = {Order.Status.OUT_FOR_DELIVERY, Order.Status.CANCELLED}
            t[Order.Status.OUT_FOR_DELIVERY] = {Order.Status.COMPLETED, Order.Status.CANCELLED}
        else:
            t[Order.Status.READY] = {Order.Status.COMPLETED, Order.Status.CANCELLED}
        return t.get(order.status, set())

    def patch(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = (request.data.get("status") or "").strip().lower()
        owner_note = request.data.get("owner_note")
        estimated_ready_minutes = request.data.get("estimated_ready_minutes")

        # Optional client-supplied idempotency key. The BFS already covers the
        # stale-retry case ("already_at_target" / "already_advanced"), so this
        # is purely belt-and-suspenders: it avoids acquiring the select_for_update
        # lock on a fast-path cache hit for duplicate in-flight retries.
        _idem_key = str(request.data.get("idempotency_key") or "")[:64] or None
        _idem_cache_key = None
        if _idem_key and new_status:
            from django.db import connection as _stu_conn
            _schema = getattr(getattr(_stu_conn, "tenant", None), "schema_name", None) or _stu_conn.schema_name
            _idem_cache_key = f"owner_status_idem:{_schema}:{order_id}:{_idem_key}"
            if cache.get(_idem_cache_key):
                _idem_order = Order.objects.filter(id=order_id).first()
                if _idem_order is None:
                    return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
                return Response({
                    "id": _idem_order.id,
                    "order_number": _idem_order.order_number,
                    "status": _idem_order.status,
                    "owner_note": _idem_order.owner_note,
                    "estimated_ready_minutes": _idem_order.estimated_ready_minutes,
                    "status_updated_at": _idem_order.status_updated_at.isoformat() if _idem_order.status_updated_at else None,
                    "payment_status": _idem_order.payment_status,
                })

        # OPS-3 contract B: wrap the read-mutate-write in transaction.atomic() +
        # select_for_update() for ALL transitions (not only cancel).  This prevents
        # last-write-wins races when two devices (or a retry) PATCH simultaneously.
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("customer").filter(id=order_id).first()
            if order is None:
                return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

            if new_status:
                # Idempotent-by-target: already at the requested status → 200 no-op.
                if order.status == new_status:
                    return Response({
                        "id": order.id,
                        "order_number": order.order_number,
                        "status": order.status,
                        "owner_note": order.owner_note,
                        "estimated_ready_minutes": order.estimated_ready_minutes,
                        "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
                        "payment_status": order.payment_status,
                        "code": "already_at_target",
                    })

                # Detect regression: target is a past status (the order has already
                # moved past it on another device).  Do NOT regress — return the
                # current state with a clear code so the SPA can self-heal.
                allowed = self._allowed_transitions(order)
                if new_status not in {s.value for s in allowed}:
                    # Distinguish "already past" from "genuinely invalid".
                    # "already_advanced" = the target is a valid Order.Status value AND
                    # the current order CAN reach order.status FROM new_status (meaning
                    # the order has legitimately advanced past the target).
                    # Build a fake order stub at the target status to get its transitions.
                    _valid_status_values = {s.value for s in Order.Status}
                    if new_status in _valid_status_values:
                        # BFS from new_status through the transition graph.
                        # If order.status is reachable from new_status (directly or
                        # multi-hop) AND the order is not in CANCELLED state (which is
                        # a side exit, not a forward advance), then the order has
                        # already legitimately advanced past the target — return
                        # "already_advanced" so the SPA can self-heal without 400s.
                        class _Stub:
                            def __init__(self, s, ft):
                                self.status = s
                                self.fulfillment_type = ft

                        _visited = set()
                        _queue = [new_status]
                        _is_past = False
                        # Only check for "already_advanced" when the current state is
                        # a FORWARD state (not CANCELLED — can't "advance" to cancelled).
                        if order.status != Order.Status.CANCELLED.value:
                            while _queue:
                                _cur = _queue.pop(0)
                                if _cur in _visited:
                                    continue
                                _visited.add(_cur)
                                _stub = _Stub(_cur, order.fulfillment_type)
                                # Exclude CANCELLED from BFS so we don't falsely claim
                                # an order "advanced past" a state via the cancel side-exit.
                                _nexts = {
                                    s.value for s in self._allowed_transitions(_stub)
                                    if s != Order.Status.CANCELLED
                                }
                                if order.status in _nexts:
                                    _is_past = True
                                    break
                                _queue.extend(_nexts - _visited)
                        if _is_past:
                            return Response({
                                "id": order.id,
                                "order_number": order.order_number,
                                "status": order.status,
                                "owner_note": order.owner_note,
                                "estimated_ready_minutes": order.estimated_ready_minutes,
                                "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
                                "payment_status": order.payment_status,
                                "code": "already_advanced",
                            })
                    return Response(
                        {"detail": f"Cannot transition from '{order.status}' to '{new_status}'.", "code": "invalid_transition"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                order.status = new_status
                order.status_updated_at = timezone.now()

            update_fields = ["status", "status_updated_at", "owner_note", "estimated_ready_minutes", "updated_at"]

            # Attribute the order for per-staff work stats. The waiter who TOOK the order keeps
            # the credit, so we only fill this when it isn't already set (e.g. a customer-placed
            # order that a staff member is now handling).
            if new_status and not order.handled_by_user_id:
                _uid = getattr(request.user, "id", None)
                if _uid:
                    order.handled_by_user_id = _uid
                    update_fields.append("handled_by_user_id")

            if owner_note is not None:
                order.owner_note = str(owner_note).strip()[:500]

            if estimated_ready_minutes is not None:
                try:
                    mins = int(estimated_ready_minutes)
                    order.estimated_ready_minutes = max(0, mins) if mins >= 0 else None
                except (TypeError, ValueError):
                    order.estimated_ready_minutes = None

            # For the cancel transition: wrap the save + side-effects atomically so
            # (a) a concurrent void can't race wallet_amount_paid, and (b) a refund
            # failure rolls back the status-to-CANCELLED update.
            # (The outer atomic block already holds the lock from select_for_update.)
            if new_status == Order.Status.CANCELLED:
                order.save(update_fields=update_fields)
                _ct = getattr(request, "tenant", None)
                _refund_wallet_for_cancelled_order(order, tenant_id=_ct.id if _ct else None)
                _reverse_loyalty_for_cancelled_order(order)
                _restock_cancelled_order(order)
            else:
                order.save(update_fields=update_fields)

        # Stand down any assigned delivery driver (public-schema job; best-effort,
        # outside the lock so a hiccup doesn't roll back the status change).
        if new_status == Order.Status.CANCELLED:
            try:
                from accounts.delivery_service import cancel_delivery_job_for_order
                _ct = getattr(request, "tenant", None)
                if _ct:
                    cancel_delivery_job_for_order(_ct.id, order.order_number)
            except Exception:
                pass

        # Mirror the prep ETA onto the platform delivery job so the assigned/searching
        # driver knows when the food will be ready (pre-dispatch timing). Best-effort.
        if order.fulfillment_type == Order.FulfillmentType.DELIVERY:
            try:
                from accounts.delivery_service import set_delivery_job_food_ready
                _ct = getattr(request, "tenant", None)
                if _ct:
                    set_delivery_job_food_ready(
                        _ct.id, order.order_number, order.estimated_ready_minutes
                    )
            except Exception:
                pass

        # Real-time ping so other connected owner/kitchen screens refresh immediately
        # (no-op if WS not configured). Low-sensitivity signal only.
        try:
            from django.db import connection as _ws_conn
            from realtime.broadcast import broadcast as _ws_broadcast
            _schema = _ws_conn.tenant.schema_name
            # Owner/kitchen screens.
            _ws_broadcast(
                _schema, "owner", "order.updated",
                {"order_number": order.order_number, "status": order.status},
            )
            # The customer tracking that specific order (guest, per-order channel).
            _ws_broadcast(
                _schema, f"order.{order.order_number}", "status",
                {"status": order.status, "estimated_ready_minutes": order.estimated_ready_minutes},
            )
        except Exception:
            pass

        tenant = getattr(request, "tenant", None)
        if new_status in {Order.Status.CONFIRMED, Order.Status.PREPARING, Order.Status.READY, Order.Status.OUT_FOR_DELIVERY, Order.Status.CANCELLED}:
            if tenant:
                _send_order_status_email(order, tenant, new_status)

        # SMS notification — only when transitioning to "ready"
        if new_status == Order.Status.READY and tenant:
            try:
                profile = tenant.profile
            except Exception:
                profile = None
            _cust_opted_in = order.customer is None or getattr(order.customer, "notify_order_updates", True)
            if profile and getattr(profile, "sms_notifications_enabled", False) and _cust_opted_in:
                customer_phone = (getattr(order, "customer_phone", "") or "").strip()
                if customer_phone:
                    from accounts.tasks import enqueue as _enqueue_task, sms_order_ready as _sms_task
                    _enqueue_task(
                        _sms_task, customer_phone, getattr(tenant, "name", ""),
                        order.order_number, getattr(tenant, "id", None),
                    )

        # Warn when cancelling an order that had cash payments collected — staff
        # must return the money manually; the system cannot do this automatically.
        cash_collected = None
        if new_status == Order.Status.CANCELLED:
            try:
                from menu.models import OrderPayment as _OP
                _cash_total = sum(
                    Decimal(str(p.amount))
                    for p in _OP.objects.filter(order_id=order.id, method="cash")
                )
                if _cash_total > Decimal("0"):
                    cash_collected = str(_cash_total)
            except Exception:
                pass

        resp = {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
            "payment_status": order.payment_status,
        }
        if cash_collected is not None:
            resp["cash_collected"] = cash_collected

        # Mark the idempotency key as committed so retries skip the DB lock.
        if _idem_cache_key:
            cache.set(_idem_cache_key, 1, 300)

        return Response(resp)


class OwnerOrderBulkStatusView(APIView):
    """POST /api/owner/orders/bulk-status/
    Batch-confirm (PENDING → CONFIRMED) up to 50 orders in one request.

    Only "confirmed" is accepted — all other transitions stay single-order
    (cancel / out_for_delivery / ready involve side-effects that must be
    individually reviewed).

    Body: { "order_ids": [1, 2, 3], "status": "confirmed" }
    Response: { "updated": N, "skipped": M }
    """
    permission_classes = [IsAuthenticated]

    _MAX = 50

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = (request.data.get("status") or "").strip().lower()
        if new_status != "confirmed":
            return Response(
                {"detail": "Bulk status update only supports 'confirmed'.", "code": "unsupported_bulk_status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order_ids = request.data.get("order_ids")
        if not isinstance(order_ids, list) or not order_ids:
            return Response({"detail": "'order_ids' must be a non-empty list."}, status=status.HTTP_400_BAD_REQUEST)
        if len(order_ids) > self._MAX:
            return Response(
                {"detail": f"At most {self._MAX} orders per bulk request."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order_ids = [int(i) for i in order_ids]
        except (TypeError, ValueError):
            return Response({"detail": "'order_ids' must be a list of integers."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        handler_id = getattr(request.user, "id", None)
        tenant = getattr(request, "tenant", None)

        # OPS-3: wrap the fetch + bulk_update in an atomic block with
        # select_for_update() so a concurrent cancel or status advance on
        # the same orders cannot race this confirm sweep.  Without the lock
        # a CANCEL committed between our read and bulk_update would be
        # silently overwritten back to CONFIRMED.
        with transaction.atomic():
            orders = list(
                Order.objects.select_for_update().filter(
                    id__in=order_ids,
                    status=Order.Status.PENDING,
                ).select_related("customer")[:self._MAX]
            )

            updated_count = 0
            for order in orders:
                order.status = Order.Status.CONFIRMED
                order.status_updated_at = now
                if not order.handled_by_user_id and handler_id:
                    order.handled_by_user_id = handler_id
                updated_count += 1

            if orders:
                update_fields = ["status", "status_updated_at", "handled_by_user_id", "updated_at"]
                Order.objects.bulk_update(orders, update_fields)

        # Fire realtime + email for each confirmed order (best-effort, outside
        # the lock so slow broadcast never holds the row locks).
        for order in orders:
            try:
                _broadcast_order_change(order)
            except Exception:
                pass
            try:
                if tenant:
                    _send_order_status_email(order, tenant, Order.Status.CONFIRMED)
            except Exception:
                pass

        skipped = len(order_ids) - updated_count
        return Response({"updated": updated_count, "skipped": skipped})


def _broadcast_order_change(order):
    """Best-effort realtime ping so the customer's order-tracking page and the
    owner/kitchen screens refresh the moment an order's status or PAYMENT state
    changes (e.g. staff marking a bill paid). No-op if realtime isn't configured.

    The customer page listens for the ``status`` event on its per-order channel
    and refetches the full order on any ping, so payment flips show up live.
    """
    try:
        from django.db import connection as _ws_conn
        from realtime.broadcast import broadcast as _ws_broadcast
        _schema = _ws_conn.tenant.schema_name
        _ws_broadcast(
            _schema, "owner", "order.updated",
            {"order_number": order.order_number, "status": order.status, "payment_status": order.payment_status},
        )
        _ws_broadcast(
            _schema, f"order.{order.order_number}", "status",
            {"status": order.status, "payment_status": order.payment_status},
        )
    except Exception:
        pass


class OwnerOrderMarkPaidView(APIView):
    """
    POST /api/owner/orders/<order_id>/mark-paid/

    Settle an order's bill — staff record that cash/card was collected at
    handover (pickup/delivery), or close the open tab when a dine-in customer
    leaves. Idempotent. Pass {"complete": true} to also complete a READY order
    in the same call (the dine-in "settle & close" action).

    Requires: a tenant editor (owner or staff with manage-orders).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # OPS-3 contract C: idempotency key mirrors the cash StaffOrderPaymentView path.
        # The SPA mints a key when the settle action is triggered and resends it on retry.
        # Under the lock, if the order is already PAID we return success immediately
        # without a second wallet debit or payment row.
        idempotency_key = str(request.data.get("idempotency_key") or "")[:128] or None
        if idempotency_key:
            from django.db import connection as _mark_paid_conn
            _idem_cache_key = f"mark_paid_idem:{_mark_paid_conn.schema_name}:{order_id}:{idempotency_key}"
            if cache.get(_idem_cache_key):
                # Fast-path cache hit: return current state without touching the DB.
                _cached_order = Order.objects.filter(id=order_id).first()
                if _cached_order is not None:
                    return Response({
                        "id": _cached_order.id,
                        "order_number": _cached_order.order_number,
                        "payment_status": _cached_order.payment_status,
                        "paid_at": _cached_order.paid_at.isoformat() if _cached_order.paid_at else None,
                        "status": _cached_order.status,
                        "already_paid": True,
                        "completed": False,
                        "idempotent_replay": True,
                    })

        with transaction.atomic():
            order = Order.objects.select_for_update().filter(id=order_id).first()
            if order is None:
                return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

            was_paid = order.is_paid

            # Idempotent: already PAID → return success without any side-effects.
            if was_paid:
                if idempotency_key:
                    cache.set(_idem_cache_key, True, timeout=300)
                return Response({
                    "id": order.id,
                    "order_number": order.order_number,
                    "payment_status": order.payment_status,
                    "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                    "status": order.status,
                    "already_paid": True,
                    "completed": False,
                })

            order.mark_paid()  # idempotent — sets payment_status=PAID + paid_at

            # Credit whoever settles the bill with handling the order, if unattributed.
            if not order.handled_by_user_id:
                _uid = getattr(request.user, "id", None)
                if _uid:
                    order.handled_by_user_id = _uid
                    order.save(update_fields=["handled_by_user_id"])

            # Optional "settle & close": settling the tab completes a READY dine-in order.
            completed = False
            _want_complete = str(request.data.get("complete", "")).strip().lower() in ("1", "true", "yes")
            if _want_complete and order.status == Order.Status.READY:
                order.status = Order.Status.COMPLETED
                order.status_updated_at = timezone.now()
                order.save(update_fields=["status", "status_updated_at", "updated_at"])
                completed = True

            # OPS-3: set the idempotency cache key INSIDE the atomic block so
            # the write is committed before the cache entry becomes visible.
            # A crash after commit but before cache.set is safe — the next
            # retry sees order.is_paid==True (DB backstop) and returns early.
            if idempotency_key:
                cache.set(_idem_cache_key, True, timeout=300)  # 5 min

        # Live-update the customer's tracking page (and other staff screens) so the
        # "Paid" state appears on their phone immediately.
        try:
            _broadcast_order_change(order)
        except Exception:
            pass

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "payment_status": order.payment_status,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "status": order.status,
            "already_paid": was_paid,
            "completed": completed,
        })


class OwnerOrderExportView(APIView):
    """GET /api/owner/orders/export/ — download all orders as CSV (max 5000 rows).

    Supports optional query filters:
      - status: filter by order status value
      - from: ISO date (YYYY-MM-DD) — include orders created on or after this date
      - to: ISO date (YYYY-MM-DD) — include orders created on or before this date
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = (request.query_params.get("status") or "").strip().lower()
        valid_statuses = {s.value for s in Order.Status}
        if status_filter and status_filter not in valid_statuses:
            return Response({"detail": "Invalid status filter."}, status=status.HTTP_400_BAD_REQUEST)

        from_raw = (request.query_params.get("from") or "").strip()
        to_raw = (request.query_params.get("to") or "").strip()
        from_date = None
        to_date = None
        if from_raw:
            try:
                from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid 'from' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if to_raw:
            try:
                to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid 'to' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if from_date and to_date and from_date > to_date:
            return Response({"detail": "'from' date cannot be after 'to' date."}, status=status.HTTP_400_BAD_REQUEST)

        qs = Order.objects.prefetch_related("items", "payments").order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        tenant_slug = getattr(getattr(request, "tenant", None), "slug", "export")
        filename = f"{tenant_slug}-orders-{timezone.now():%Y%m%d}.csv"

        # Compute total before slicing so we can signal truncation to the caller.
        _EXPORT_CAP = 5000
        total_count = qs.count()
        truncated = total_count > _EXPORT_CAP

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Kepoli-Export-Total"] = str(total_count)
        response["X-Kepoli-Export-Truncated"] = "true" if truncated else "false"
        # Prepend the UTF-8 BOM (\xef\xbb\xbf) so Excel on Windows opens the
        # file as UTF-8 rather than defaulting to the system code page (Latin-1).
        # This prevents garbled display of Arabic / French characters in names.
        response.write("﻿")  # UTF-8 BOM: signals to Excel this is a UTF-8 file

        writer = csv.writer(response)
        # Contract F: void_reason + recorded_by_name are surfaced in the CSV export
        # so owners can audit who voided items and why. Items with is_voided=True
        # are included in the item text with a "[VOID]" prefix.
        writer.writerow([
            "order_number", "created_at", "status", "payment_status", "fulfillment_type",
            "table_label", "customer_name", "customer_phone",
            "customer_note", "owner_note", "delivery_address",
            "items", "void_items", "subtotal", "delivery_fee", "tip_amount",
            "loyalty_discount", "promotion_discount", "wallet_amount_paid", "paid_at", "total", "commission_amount", "currency",
            "recorded_by_names",
        ])

        for order in qs[:_EXPORT_CAP]:
            # Iterate items exactly once from the prefetch cache; split into active/voided.
            # A second call to order.items.all() would re-hit the DB (N+1).
            _all_items = list(order.items.all())
            active_items = [i for i in _all_items if not i.is_voided]
            voided_items = [i for i in _all_items if i.is_voided]

            items_text = " | ".join(
                f"{i.qty}x {i.dish_name}"
                + (
                    f" ({', '.join(o.get('name', '') for o in (i.options or []) if o.get('name'))})"
                    if i.options
                    else ""
                )
                for i in active_items
            )
            # Contract F: list voided items with their void_reason in a separate column
            void_text = " | ".join(
                f"[VOID] {i.qty}x {i.dish_name}"
                + (f" — {i.void_reason}" if i.void_reason else "")
                for i in voided_items
            )
            # Contract F: recorded_by_name from the payment ledger (may be multiple staff)
            recorded_by_names = ", ".join(
                sorted({p.recorded_by_name for p in order.payments.all() if p.recorded_by_name})
            )
            subtotal = order.total - order.delivery_fee - (order.tip_amount or Decimal("0"))
            writer.writerow([
                order.order_number,                          # system-generated — safe
                timezone.localtime(order.created_at).isoformat(),
                order.status,
                order.payment_status,
                order.fulfillment_type or "",
                _csv_safe(order.table_label or ""),          # owner-set label
                _csv_safe(order.customer_name or ""),        # customer-provided
                _csv_safe(order.customer_phone or ""),       # customer-provided
                _csv_safe(order.customer_note or ""),        # customer-provided
                _csv_safe(order.owner_note or ""),           # restaurant's internal note
                _csv_safe(order.delivery_address or ""),     # customer-provided
                _csv_safe(items_text),                       # active dish names
                _csv_safe(void_text),                        # voided items + reasons (Contract F)
                str(subtotal),
                str(order.delivery_fee),
                str(order.tip_amount),
                str(order.loyalty_discount or "0"),          # loyalty redemption value
                str(order.promotion_discount or "0"),
                str(order.wallet_amount_paid or "0"),
                timezone.localtime(order.paid_at).isoformat() if order.paid_at else "",
                str(order.total),
                str(order.commission_amount or "0"),
                order.currency or "",
                _csv_safe(recorded_by_names),                # Contract F: who recorded the payment
            ])

        return response


class OwnerZReportView(APIView):
    """GET /api/owner/z-report/?date=YYYY-MM-DD (optional)
       GET /api/owner/z-report.csv?date=YYYY-MM-DD (CSV flat-file export)

    End-of-day "Z-report" snapshot for the owner.  Covers one service-day window
    (start inclusive, end exclusive) whose boundaries are determined by
    Profile.service_day_cutover_hour (default 0 = calendar midnight).

    Auth: owner only (IsTenantOwner check — same pattern as OwnerCommissionStatementView).

    ── ORDER SELECTION PREDICATE (collected) ──────────────────────────────────
    "Collected" money is money that physically changed hands in the window, NOT
    orders that are still in-flight.  Only COMPLETED orders whose paid_at timestamp
    falls within [window_start, window_end) are counted.  Rationale:

      * paid_at is set exactly when cash/wallet is received (StaffSettleView,
        WalletSettleView, StaffOrderPaymentView last-instalment logic).
      * PREPARING/READY/CONFIRMED orders have not been paid yet; including them
        inflates the drawer (this is the bug documented in OPS_AUDIT THEME 3).
      * We filter on paid_at (not created_at) to handle the case where a dine-in
        order is placed before midnight but paid after the cutover hour.

    Predicate:
        status = COMPLETED
        paid_at >= window_start
        paid_at < window_end

    The cash/wallet split is delegated to menu.revenue.split_revenue_for_orders
    (shared with the daily digest) so all three surfaces (Z-report, digest, dashboard)
    agree to the cent.

    ── REFUNDS PREDICATE ─────────────────────────────────────────────────────
    Refunds are WalletTransaction rows with type=REFUND that were created in the
    window.  Note:
      - _refund_wallet_for_cancelled_order creates a REFUND row when a wallet-paid
        order is cancelled (note="Refund for cancelled order").
      - Partial void refunds also create REFUND rows (note prefix "Void refund").
    We aggregate ALL REFUND rows created within the window regardless of note.

    Limitation: cash refunds (if any) are not tracked in WalletTransaction — the
    system has no cash-refund ledger today.  The basis field documents this.

    net_cash_position = collected.cash − 0  (no cash-refund ledger exists today;
    wallet refunds do not touch the physical drawer).
    """
    permission_classes = [IsAuthenticated]

    def _require_owner(self, request):
        user = request.user
        return getattr(user, "is_tenant_owner", False) or (
            hasattr(user, "role") and user.role == getattr(user, "Roles", type("_R", (), {"TENANT_OWNER": "owner"})).TENANT_OWNER
        )

    def _get_profile(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return None
        try:
            return tenant.profile
        except Exception:
            return None

    def _build_report(self, profile, date_param, tenant_id=None):
        """Compute the Z-report data dict for a given profile and optional date.

        tenant_id: integer PK of the owning tenant.  MUST be supplied so that the
        WalletTransaction refund query is scoped to this tenant only.  Without it the
        query aggregates REFUND rows from every tenant in the shared schema.
        """
        from menu.revenue import split_revenue_for_orders
        from accounts.models import WalletTransaction as _WTx
        from django.db.models import Sum as _Sum, Count as _Count

        # ── Service-day window ────────────────────────────────────────────────
        window_start, window_end = service_day_window(profile, date=date_param)
        H = int(getattr(profile, "service_day_cutover_hour", 0) or 0)
        # Derive the service_day label: the local date on which this window STARTS.
        service_day_date = window_start.date()

        # ── Collected orders (paid in window) ─────────────────────────────────
        # Predicate: COMPLETED + PAID status AND paid_at in [start, end).
        # paid_at is set at the moment money is received; this is the ground truth
        # for "money in the drawer" rather than created_at or status_updated_at.
        # payment_status=PAID is a defence-in-depth filter: a future status-flow
        # change that could mark an order COMPLETED without PAID would otherwise
        # silently inflate the drawer total.
        collected_qs = Order.objects.filter(
            status=Order.Status.COMPLETED,
            payment_status=Order.PaymentStatus.PAID,
            paid_at__gte=window_start,
            paid_at__lt=window_end,
        )
        split = split_revenue_for_orders(collected_qs)
        collected_cash = split["cash"]
        collected_wallet = split["wallet"]
        collected_total = (collected_cash + collected_wallet).quantize(Decimal("0.01"))

        # ── Tips in window ────────────────────────────────────────────────────
        tips_agg = collected_qs.aggregate(tips=_Sum("tip_amount"))
        tips_total = Decimal(str(tips_agg["tips"] or 0)).quantize(Decimal("0.01"))

        # ── Refunds in window ─────────────────────────────────────────────────
        # WalletTransaction.REFUND rows created in the window — wallet credits only.
        # There is no cash-refund ledger in the current data model.
        # CRITICAL: WalletTransaction lives in the shared public schema; without a
        # tenant_id filter this would aggregate refunds from ALL tenants.
        # The tenant_id field is set on every REFUND row by the two creation paths:
        #   - credit_wallet(tenant_id=...) in StaffVoidOrderItemView
        #   - _WTM.objects.create(tenant_id=...) in _refund_wallet_for_cancelled_order
        refund_filter = dict(
            type=_WTx.Type.REFUND,
            created_at__gte=window_start,
            created_at__lt=window_end,
        )
        if tenant_id is not None:
            refund_filter["tenant_id"] = tenant_id
        refund_agg = _WTx.objects.filter(**refund_filter).aggregate(
            refund_count=_Count("id"),
            refund_total=_Sum("amount"),
        )
        refund_count = int(refund_agg["refund_count"] or 0)
        refund_total = Decimal(str(refund_agg["refund_total"] or 0)).quantize(Decimal("0.01"))

        # ── Voids in window ───────────────────────────────────────────────────
        # OrderItem.is_voided=True AND voided_at in [start, end).
        # voided_by: the model stores void attribution in OrderItem.void_reason only
        # (free text) — there is no voided_by_user_id field.  We use None → null.
        voided_items_qs = OrderItem.objects.select_related("order").filter(
            is_voided=True,
            voided_at__gte=window_start,
            voided_at__lt=window_end,
        )
        voids_list = []
        voids_total = Decimal("0.00")
        for item in voided_items_qs:
            line_total = (item.unit_price * item.qty).quantize(Decimal("0.01"))
            voids_total += line_total
            voids_list.append({
                "order_number": item.order.order_number,
                "dish_name": item.dish_name,
                "qty": item.qty,
                "line_total": str(line_total),
                "reason": item.void_reason or "",
                "voided_by": item.voided_by_user_id,
            })

        # ── By-staff breakdown ────────────────────────────────────────────────
        # Source: OrderPayment.recorded_by_name for ledger-based payments.
        # Legacy (one-shot settle) orders have no ledger row; they cannot be
        # attributed to a specific staff member from existing data.
        #
        # IMPORTANT: filter on order__paid_at (not OrderPayment.created_at) so that
        # by_staff totals are drawn from the same service-day population as the
        # collected header totals.  Using order__paid_at ensures
        # Sum(by_staff.collected_cash) + Sum(by_staff.collected_wallet) == collected.total.
        #
        # Conditional aggregation (Sum with filter=) groups by staff name once,
        # computing cash sum, wallet sum, and distinct order count in a single query.
        from django.db.models import Q as _Q
        staff_rows = (
            OrderPayment.objects.filter(
                order__status=Order.Status.COMPLETED,
                order__payment_status=Order.PaymentStatus.PAID,
                order__paid_at__gte=window_start,
                order__paid_at__lt=window_end,
            )
            .values("recorded_by_name")
            .annotate(
                cash_sum=_Sum("amount", filter=_Q(method=OrderPayment.Method.CASH)),
                wallet_sum=_Sum("amount", filter=_Q(method=OrderPayment.Method.WALLET)),
                order_count=_Count("order_id", distinct=True),
            )
        )
        by_staff = sorted(
            [
                {
                    "name": (row["recorded_by_name"] or "(unknown)"),
                    "orders": row["order_count"],
                    "collected_cash": str(
                        Decimal(str(row["cash_sum"] or 0)).quantize(Decimal("0.01"))
                    ),
                    "collected_wallet": str(
                        Decimal(str(row["wallet_sum"] or 0)).quantize(Decimal("0.01"))
                    ),
                }
                for row in staff_rows
            ],
            key=lambda x: x["name"],
        )

        # ── Net cash position ─────────────────────────────────────────────────
        # net_cash_position = collected.cash − cash_refunds_issued
        # There is no cash-refund ledger (all tracked refunds are wallet credits).
        # Therefore net_cash_position = collected.cash (cash is not reduced by wallet refunds).
        net_cash_position = collected_cash.quantize(Decimal("0.01"))

        # ── Labor (shifts) in window ──────────────────────────────────────────
        from menu.models import Shift as _Shift
        shift_qs = _Shift.objects.filter(clock_in__gte=window_start, clock_in__lt=window_end).order_by("clock_in")
        _CENT = Decimal("0.01")
        labor_items = []
        total_labor_hours = Decimal("0")
        total_labor_cost = None
        for sh in shift_qs:
            h = sh.duration_hours  # None if shift still open
            cost_str = None
            if h is not None and sh.hourly_rate is not None:
                cost_dec = (Decimal(str(round(h, 6))) * Decimal(str(sh.hourly_rate))).quantize(_CENT)
                if total_labor_cost is None:
                    total_labor_cost = Decimal("0")
                total_labor_cost += cost_dec
                cost_str = str(cost_dec)
            if h is not None:
                total_labor_hours += Decimal(str(round(h, 6)))
            labor_items.append({
                "user_name": sh.user_name,
                "clock_in": sh.clock_in.isoformat(),
                "clock_out": sh.clock_out.isoformat() if sh.clock_out else None,
                "hours": round(h, 2) if h is not None else None,
                "hourly_rate": str(sh.hourly_rate) if sh.hourly_rate is not None else None,
                "labor_cost": cost_str,
                "note": sh.note,
            })
        labor_pct = None
        if total_labor_cost is not None and collected_total > 0:
            labor_pct = str((total_labor_cost / collected_total * 100).quantize(_CENT))

        return {
            "window": {
                "service_day": service_day_date.isoformat(),
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "cutover_hour": H,
            },
            "collected": {
                "cash": str(collected_cash),
                "wallet": str(collected_wallet),
                "total": str(collected_total),
            },
            "refunds": {
                "count": refund_count,
                "total": str(refund_total),
                "basis": (
                    "WalletTransaction REFUND rows created in window. "
                    "Cash refunds not tracked (no cash-refund ledger exists)."
                ),
            },
            "voids": {
                "count": len(voids_list),
                "total": str(voids_total.quantize(Decimal("0.01"))),
                "items": voids_list,
            },
            "tips": {
                "total": str(tips_total),
            },
            "by_staff": by_staff,
            "labor": {
                "shifts": labor_items,
                "total_hours": float(round(total_labor_hours, 2)),
                "total_labor_cost": str(total_labor_cost.quantize(_CENT)) if total_labor_cost is not None else None,
                "labor_pct": labor_pct,
            },
            "net_cash_position": str(net_cash_position),
            "net": str((collected_total - refund_total).quantize(Decimal("0.01"))),
        }

    def get(self, request, *args, **kwargs):
        if not self._require_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        profile = self._get_profile(request)
        if profile is None:
            return Response({"detail": "Tenant profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        date_param = (request.query_params.get("date") or "").strip() or None

        # CSV export — same data, flat rows
        want_csv = (
            request.accepted_renderer.format == "csv"
            if hasattr(request, "accepted_renderer") and hasattr(request.accepted_renderer, "format")
            else False
        )
        # Also check URL path suffix (.csv) or ?format=csv
        path = request.path or ""
        if path.endswith(".csv") or request.query_params.get("format") == "csv":
            want_csv = True

        _z_tenant = getattr(request, "tenant", None)
        _z_tenant_id = _z_tenant.id if _z_tenant else None
        try:
            data = self._build_report(profile, date_param, tenant_id=_z_tenant_id)
        except Exception as exc:
            return Response({"detail": f"Report generation failed: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if want_csv:
            return self._csv_response(data, request)
        return Response(data)

    def _csv_response(self, data, request):
        """Flat CSV representation of the Z-report."""
        tenant_slug = getattr(getattr(request, "tenant", None), "slug", "report")
        service_day = data["window"]["service_day"]
        filename = f"{tenant_slug}-z-report-{service_day}.csv"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("\xef\xbb\xbf")  # UTF-8 BOM for Excel

        writer = csv.writer(response)

        # Summary section
        writer.writerow(["section", "field", "value"])
        writer.writerow(["window", "service_day", data["window"]["service_day"]])
        writer.writerow(["window", "start", data["window"]["start"]])
        writer.writerow(["window", "end", data["window"]["end"]])
        writer.writerow(["window", "cutover_hour", data["window"]["cutover_hour"]])
        writer.writerow(["collected", "cash", data["collected"]["cash"]])
        writer.writerow(["collected", "wallet", data["collected"]["wallet"]])
        writer.writerow(["collected", "total", data["collected"]["total"]])
        writer.writerow(["refunds", "count", data["refunds"]["count"]])
        writer.writerow(["refunds", "total", data["refunds"]["total"]])
        writer.writerow(["tips", "total", data["tips"]["total"]])
        writer.writerow(["net", "cash_position", data["net_cash_position"]])
        writer.writerow(["net", "reconciliation", data["net"]])
        writer.writerow([])

        # By-staff section
        writer.writerow(["staff", "name", "orders", "collected_cash", "collected_wallet"])
        for row in data["by_staff"]:
            writer.writerow(["staff", row["name"], row["orders"], row["collected_cash"], row["collected_wallet"]])
        writer.writerow([])

        # Voids section
        writer.writerow(["void", "order_number", "dish_name", "qty", "line_total", "reason", "voided_by"])
        for item in data["voids"]["items"]:
            writer.writerow([
                "void",
                item["order_number"],
                _csv_safe(item["dish_name"]),
                item["qty"],
                item["line_total"],
                _csv_safe(item["reason"]),
                item["voided_by"] or "",
            ])

        return response


class StaffPaymentMethodCorrectionView(APIView):
    """POST /api/staff/orders/<order_id>/payments/<payment_id>/correct-method/

    Corrects the recorded tender method (cash ↔ wallet) on an OrderPayment row.
    This is a RELABELLING operation only — it does NOT move money.

    Boundary (documented and must not be crossed):
      * OrderPayment.method is updated to the corrected value.
      * The three correction audit fields are written: original_method (first
        correction only), corrected_at, corrected_by_name.
      * WalletTransaction rows, Customer.wallet_balance, and
        Order.wallet_amount_paid are NEVER touched. The wallet ledger reflects
        what actually moved in/out of the wallet; this endpoint only fixes a
        mis-label in the cash-register record.
      * The Z-report reads the (possibly corrected) method field, so the
        drawer split will reflect the correction immediately.

    Auth: _can_access_order (same gate used by StaffOrderPaymentView, StaffVoidOrderItemView).

    Request body: {"method": "cash" | "wallet"}

    Response: updated payment row payload.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, payment_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        new_method = str(request.data.get("method") or "").strip().lower()
        if new_method not in {"cash", "wallet"}:
            return Response(
                {"detail": "method must be 'cash' or 'wallet'.", "code": "bad_method"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            OrderPayment.objects
            .select_related("order")
            .filter(pk=payment_id, order_id=order_id)
            .first()
        )
        if payment is None:
            return Response({"detail": "Payment not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        if not _can_access_order(request, payment.order):
            return Response(
                {"detail": "Access denied — not your section.", "code": "section_denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if payment.method == new_method:
            return Response(
                {"detail": "Payment method is already recorded as that value.", "code": "no_change"},
                status=status.HTTP_409_CONFLICT,
            )

        # Write the correction with full audit trail.
        # original_method is only captured on the FIRST correction so the chain
        # "wallet → cash" then "cash → wallet" doesn't overwrite the original.
        corrector_name = ""
        user = request.user
        if hasattr(user, "get_full_name"):
            corrector_name = (user.get_full_name() or "").strip()
        if not corrector_name:
            corrector_name = getattr(user, "username", "") or getattr(user, "email", "") or "staff"

        update_fields = ["method", "corrected_at", "corrected_by_name"]
        if not payment.original_method:
            # First correction — snapshot the original method.
            payment.original_method = payment.method
            update_fields.append("original_method")

        payment.method = new_method
        payment.corrected_at = timezone.now()
        payment.corrected_by_name = corrector_name[:80]
        payment.save(update_fields=update_fields)

        return Response({
            "id": payment.id,
            "order_id": payment.order_id,
            "amount": str(payment.amount),
            "method": payment.method,
            "recorded_by_name": payment.recorded_by_name,
            "note": payment.note,
            "created_at": payment.created_at.isoformat(),
            "original_method": payment.original_method or None,
            "corrected_at": payment.corrected_at.isoformat() if payment.corrected_at else None,
            "corrected_by_name": payment.corrected_by_name or None,
        })


class DishBulkAvailabilityResetView(APIView):
    """POST /api/owner/dishes/reset-availability/

    Marks all published dishes as is_available=True and clears auto-zeroed
    stock counts. This is the morning-reset workflow: start the day with
    everything available, ready for the owner to track stock afresh.

    Optional body: { "clear_stock": true } — also clears ALL stock_qty tracking,
    not just auto-zeroed dishes.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        clear_stock = bool(request.data.get("clear_stock", False))

        # Re-enable all published dishes that are currently sold-out (is_available=False).
        # Also clear stock_auto_zeroed so the morning cron (auto_reset_availability)
        # does not zero out any stock_qty the owner sets between now and 5am.
        restored_count = Dish.objects.filter(
            is_published=True, is_available=False
        ).update(is_available=True, stock_auto_zeroed=False)

        stock_cleared_count = 0
        if clear_stock:
            # Clear ALL tracked stock counts so the owner sets fresh numbers each day
            stock_cleared_count = Dish.objects.filter(
                is_published=True, stock_qty__isnull=False
            ).update(stock_qty=None)
        else:
            # Only clear auto-zeroed entries (stock reached 0 during service)
            stock_cleared_count = Dish.objects.filter(
                is_published=True, stock_qty=0
            ).update(stock_qty=None)

        return Response({
            "restored": restored_count,
            "stock_cleared": stock_cleared_count,
            "clear_stock_all": clear_stock,
        }, status=status.HTTP_200_OK)


class DishBulkPriceUpdateView(APIView):
    """PATCH /api/owner/dishes/bulk-price/

    Adjust all (or a single category's) published dish prices by a percentage
    or a flat amount.  Optionally round the results to a convenient denomination.

    Request body:
        action:      "increase_percent" | "decrease_percent" |
                     "increase_flat"    | "decrease_flat"
        value:       positive number — percentage (1–100) or monetary flat amount
        category_id: optional int — limit to one category; omit = all categories
        round_to:    optional int — round result to nearest N cents (expressed as
                     integer hundredths of the currency unit):
                         0   → no rounding (default)
                        50   → nearest 0.50
                       100   → nearest 1.00
                       500   → nearest 5.00
        dry_run:     optional bool (default false) — preview without persisting

    Response 200:
        { "updated": N, "dry_run": bool,
          "items": [{"id": …, "name": …, "old_price": "…", "new_price": "…"}, …] }
    """

    permission_classes = [IsAuthenticated]

    _VALID_ACTIONS = frozenset({
        "increase_percent", "decrease_percent",
        "increase_flat",    "decrease_flat",
    })

    def patch(self, request, *args, **kwargs):
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # ── Parse + validate inputs ───────────────────────────────────────────
        action = str(request.data.get("action", "")).strip().lower()
        if action not in self._VALID_ACTIONS:
            return Response(
                {"detail": f"action must be one of: {', '.join(sorted(self._VALID_ACTIONS))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            value = Decimal(str(request.data.get("value", "0"))).quantize(Decimal("0.0001"))
        except Exception:
            return Response({"detail": "value must be a number."}, status=status.HTTP_400_BAD_REQUEST)

        if value <= 0:
            return Response({"detail": "value must be a positive number."}, status=status.HTTP_400_BAD_REQUEST)

        if "percent" in action and value > 100:
            return Response({"detail": "Percentage must be ≤ 100."}, status=status.HTTP_400_BAD_REQUEST)

        category_id = request.data.get("category_id")
        if category_id is not None:
            try:
                category_id = int(category_id)
            except (ValueError, TypeError):
                return Response({"detail": "category_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            round_to = int(request.data.get("round_to") or 0)
        except (ValueError, TypeError):
            round_to = 0

        dry_run = bool(request.data.get("dry_run", False))

        # ── Fetch dishes ──────────────────────────────────────────────────────
        qs = Dish.objects.filter(is_published=True).select_related("category")
        if category_id is not None:
            qs = qs.filter(category_id=category_id)
        dishes = list(qs[:500])  # safety cap — 500 dishes per call

        if not dishes:
            return Response({"updated": 0, "dry_run": dry_run, "items": []})

        # ── Compute new prices ────────────────────────────────────────────────
        preview = []
        new_prices = []
        for dish in dishes:
            old = dish.price
            if action == "increase_percent":
                new = old * (1 + value / Decimal("100"))
            elif action == "decrease_percent":
                new = old * (1 - value / Decimal("100"))
            elif action == "increase_flat":
                new = old + value
            else:  # decrease_flat
                new = old - value

            new = max(new, Decimal("0.01"))  # floor at one cent

            # Optional rounding to a convenient denomination.
            # round_to is expressed as integer hundredths (e.g. 50 → 0.50).
            if round_to and round_to > 0:
                step = Decimal(round_to) / Decimal("100")
                new = (new / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step

            new = new.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            preview.append({
                "id": dish.id,
                "name": dish.name,
                "old_price": str(old),
                "new_price": str(new),
            })
            new_prices.append(new)

        # ── Persist unless dry_run ────────────────────────────────────────────
        if not dry_run:
            now = timezone.now()
            for dish, new_price in zip(dishes, new_prices):
                dish.price = new_price
                dish.updated_at = now
            Dish.objects.bulk_update(dishes, ["price", "updated_at"])

        return Response({
            "updated": len(dishes) if not dry_run else 0,
            "dry_run": dry_run,
            "items": preview,
        })


# ── Ratings ───────────────────────────────────────────────────────────────────

class CustomerOrderRateView(APIView):
    """
    POST /api/orders/<order_number>/rate/

    Customers submit a 1–5 star rating (+ optional comment) after their order
    reaches 'completed' status.  No authentication required — any caller who
    knows the order number can rate it once.

    Request body:
        { "score": 4, "comment": "Great food!" }

    Responses:
        201 Created — rating stored; body: {score, comment, created_at}
        400 Bad Request — invalid score / already rated / order not complete
        403 Forbidden — the session customer doesn't own this order
        404 Not Found — unknown order_number
    """

    permission_classes = [AllowAny]
    throttle_classes = [CustomerOrderRateThrottle]  # OPS-5e: stop bulk order-number probing

    def post(self, request, order_number, *args, **kwargs):
        # Normalise the order number (strip whitespace, upper-case for lookup)
        order_number = str(order_number or "").strip()
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found.", "code": "order_not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # OPS-5e: ownership gate. Without this, any caller who guesses an order number
        # could rate it (review fraud). Require the session customer to own the order —
        # the customer record exists once they've ordered, so order.customer_id is set.
        _session_cid = request.session.get("customer_id")
        if not _session_cid or order.customer_id is None or int(_session_cid) != int(order.customer_id):
            return Response(
                {"detail": "You can only rate your own order.", "code": "not_order_owner"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if order.status != Order.Status.COMPLETED:
            return Response(
                {
                    "detail": "You can only rate a completed order.",
                    "code": "order_not_completed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(order, "rating"):
            return Response(
                {"detail": "This order has already been rated.", "code": "already_rated"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate input
        score_raw = request.data.get("score")
        try:
            score = int(score_raw)
            if score < 1 or score > 5:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "Score must be an integer between 1 and 5.", "code": "invalid_score"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        comment = str(request.data.get("comment", "") or "").strip()[:1000]

        # Link to platform customer when one is in session
        from accounts.models import Customer as _CustM
        _customer_id = request.session.get("customer_id")
        _linked_customer = None
        if _customer_id:
            try:
                _linked_customer = _CustM.objects.get(pk=_customer_id)
            except _CustM.DoesNotExist:
                pass

        rating = Rating.objects.create(
            order=order,
            score=score,
            comment=comment,
            customer=_linked_customer,
        )

        # Bust the meta cache so the updated average is reflected promptly
        tenant = getattr(request, "tenant", None)
        if tenant:
            from tenancy.api import _bust_tenant_meta_cache
            _bust_tenant_meta_cache(getattr(tenant, "slug", ""))

        return Response(
            {
                "score": rating.score,
                "comment": rating.comment,
                "created_at": rating.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


# ── Floor sections (route table orders to the responsible waiter) ──────────────

def _resolve_staff_names(user_ids, tenant):
    """Map accounts.User pk → {id, name, email} for the given ids (this tenant)."""
    out = {}
    ids = [i for i in (user_ids or []) if i]
    if not ids:
        return out
    try:
        from accounts.models import User as _User
        qs = _User.objects.filter(id__in=ids)
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        for u in qs.values("id", "name", "email"):
            out[u["id"]] = {"id": u["id"], "name": u["name"] or "", "email": u["email"]}
    except Exception:
        pass
    return out


def _serialize_section(section, server_map):
    return {
        "id": section.id,
        "name": section.name,
        "color": section.color,
        "position": section.position,
        "is_active": section.is_active,
        "tables": [
            {"id": t.id, "label": t.label, "slug": t.slug}
            for t in sorted(section.tables.all(), key=lambda t: (t.position, t.label))
        ],
        "servers": [
            server_map.get(s.user_id, {"id": s.user_id, "name": "", "email": ""})
            for s in section.servers.all()
        ],
    }


class OwnerSectionListCreateView(APIView):
    """GET/POST /api/owner/sections/ — list or create floor sections (owner only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        sections = list(
            TableSection.objects.prefetch_related("tables", "servers").order_by("position", "name", "id")
        )
        ids = {s.user_id for sec in sections for s in sec.servers.all()}
        server_map = _resolve_staff_names(ids, getattr(request, "tenant", None))
        return Response({"sections": [_serialize_section(s, server_map) for s in sections]})

    def post(self, request):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        name = str(request.data.get("name", "") or "").strip()[:60]
        if not name:
            return Response({"detail": "Name is required.", "code": "name_required"}, status=status.HTTP_400_BAD_REQUEST)
        color = str(request.data.get("color", "") or "").strip()[:9]
        try:
            position = int(request.data.get("position"))
        except (TypeError, ValueError):
            position = TableSection.objects.count()
        section = TableSection.objects.create(name=name, color=color, position=position)
        return Response(_serialize_section(section, {}), status=status.HTTP_201_CREATED)


class OwnerSectionDetailView(APIView):
    """PATCH/DELETE /api/owner/sections/<id>/ — edit, assign tables/waiters, delete."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, section_id):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        section = TableSection.objects.filter(id=section_id).first()
        if section is None:
            return Response({"detail": "Section not found."}, status=status.HTTP_404_NOT_FOUND)

        fields = []
        if "name" in request.data:
            name = str(request.data.get("name") or "").strip()[:60]
            if name:
                section.name = name
                fields.append("name")
        if "color" in request.data:
            section.color = str(request.data.get("color") or "").strip()[:9]
            fields.append("color")
        if "position" in request.data:
            try:
                section.position = max(0, int(request.data.get("position")))
                fields.append("position")
            except (TypeError, ValueError):
                pass
        if "is_active" in request.data:
            section.is_active = bool(request.data.get("is_active"))
            fields.append("is_active")
        if fields:
            fields.append("updated_at")
            section.save(update_fields=fields)

        # Replace table membership when provided (full set).
        if "table_ids" in request.data:
            ids = [int(i) for i in (request.data.get("table_ids") or []) if str(i).isdigit()]
            TableLink.objects.filter(section_id=section.id).exclude(id__in=ids).update(section=None)
            if ids:
                TableLink.objects.filter(id__in=ids).update(section=section)

        # Replace waiter assignments when provided (full set).
        if "server_user_ids" in request.data:
            ids = [int(i) for i in (request.data.get("server_user_ids") or []) if str(i).isdigit()]
            # SECURITY (OPS-5-C): whitelist — only accept user_ids that are members
            # of this tenant.  Foreign user_ids are silently dropped so an attacker
            # cannot inject a cross-tenant user into SectionServer (which feeds
            # _can_access_order routing, determining which waiter sees which order).
            # "Member of this tenant" mirrors _resolve_staff_names: accounts.User
            # filtered by tenant=request.tenant (public-schema User.tenant FK).
            _tenant = getattr(request, "tenant", None)
            if ids and _tenant is not None:
                # SECURITY (OPS-5): if the tenant-membership DB query fails we
                # must NOT silently clear valid_ids (which previously caused
                # .exclude(user_id__in=[]).delete() to wipe ALL existing
                # waiter-section assignments and return 200 with empty servers).
                # Re-raise so the caller gets a 500 and the section state is
                # left untouched.  The security invariant — no foreign user_id
                # injected — still holds because we never reach the .delete()
                # / .create() calls below.
                from accounts.models import User as _User
                valid_ids = set(
                    _User.objects.filter(id__in=ids, tenant=_tenant).values_list("id", flat=True)
                )
                ids = [uid for uid in ids if uid in valid_ids]
            SectionServer.objects.filter(section_id=section.id).exclude(user_id__in=ids).delete()
            existing = set(SectionServer.objects.filter(section_id=section.id).values_list("user_id", flat=True))
            for uid in ids:
                if uid not in existing:
                    SectionServer.objects.create(section=section, user_id=uid)

        section.refresh_from_db()
        ids = {s.user_id for s in section.servers.all()}
        server_map = _resolve_staff_names(ids, getattr(request, "tenant", None))
        return Response(_serialize_section(section, server_map))

    def delete(self, request, section_id):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        section = TableSection.objects.filter(id=section_id).first()
        if section is None:
            return Response({"detail": "Section not found."}, status=status.HTTP_404_NOT_FOUND)
        section.delete()  # tables.section → NULL (SET_NULL); servers → cascade
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerRatingListView(APIView):
    """
    GET /api/owner/ratings/

    Returns ratings for the current tenant, newest first.
    Supports ?format=csv for a spreadsheet export with optional ?from/to date filters.

    JSON pagination: ?page=<n>&page_size=<n> (default page_size=50, max 200).

    Requires: authenticated tenant owner or staff.
    """

    _DEFAULT_PAGE_SIZE = 50
    _MAX_PAGE_SIZE = 200

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            Rating.objects
            .select_related("order")
            .order_by("-created_at")
        )

        # Optional date range (ISO YYYY-MM-DD) — applies to both CSV and JSON
        from_raw = (request.query_params.get("from") or "").strip()
        to_raw = (request.query_params.get("to") or "").strip()
        if from_raw:
            try:
                from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__gte=from_date)
            except ValueError:
                return Response({"detail": "Invalid 'from' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if to_raw:
            try:
                to_date = datetime.strptime(to_raw, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__lte=to_date)
            except ValueError:
                return Response({"detail": "Invalid 'to' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # CSV export — returns the full filtered set (no row cap)
        if request.query_params.get("format", "").lower() == "csv":
            return self._csv_response(qs)

        # Aggregate summary (over the filtered set)
        from django.db.models import Avg, Count
        agg = qs.aggregate(avg=Avg("score"), total=Count("id"))
        average = round(float(agg["avg"]), 1) if agg["avg"] is not None else None
        total = agg["total"] or 0

        # Pagination
        try:
            page_size = int(request.query_params.get("page_size") or self._DEFAULT_PAGE_SIZE)
            page_size = max(1, min(page_size, self._MAX_PAGE_SIZE))
        except (ValueError, TypeError):
            page_size = self._DEFAULT_PAGE_SIZE
        try:
            page = int(request.query_params.get("page") or 1)
            page = max(1, page)
        except (ValueError, TypeError):
            page = 1

        offset = (page - 1) * page_size
        page_qs = qs[offset: offset + page_size]

        ratings = [
            {
                "id": r.id,
                "order_number": r.order.order_number,
                "customer_name": r.order.customer_name,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at.isoformat(),
                "owner_reply": r.owner_reply or "",
                "owner_reply_at": r.owner_reply_at.isoformat() if r.owner_reply_at else None,
            }
            for r in page_qs
        ]

        return Response({
            "count": total,
            "average": average,
            "page": page,
            "page_size": page_size,
            "has_more": total > offset + page_size,
            "ratings": ratings,
        })

    def _csv_response(self, qs):
        output = StringIO()
        output.write("﻿")  # UTF-8 BOM for Excel on Windows
        writer = csv.writer(output)
        writer.writerow(["Date", "Order Number", "Customer", "Score", "Comment", "Owner Reply"])
        for r in qs:
            writer.writerow([
                r.created_at.strftime("%Y-%m-%d %H:%M"),
                r.order.order_number,            # system-generated — safe
                _csv_safe(r.order.customer_name or ""),  # customer-provided
                r.score,                         # integer — safe
                _csv_safe(r.comment or ""),      # customer-provided review text
                _csv_safe(r.owner_reply or ""),  # owner-authored reply
            ])
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ratings.csv"'
        return response


class OwnerRatingReplyView(APIView):
    """
    POST   /api/owner/ratings/<pk>/reply/  — save or update the owner's reply.
    DELETE /api/owner/ratings/<pk>/reply/  — remove the owner's reply.

    Only accessible by the tenant owner (or platform staff/superuser).
    The reply is stored on the Rating row and surfaced to the customer on their
    order-status page.
    """

    permission_classes = [IsAuthenticated]

    def _get_rating(self, request, pk):
        if not _can_edit_tenant_order(request):
            return None, Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            rating = Rating.objects.select_related("order").get(pk=pk)
        except Rating.DoesNotExist:
            return None, Response({"detail": "Rating not found."}, status=status.HTTP_404_NOT_FOUND)
        return rating, None

    def post(self, request, pk, *args, **kwargs):
        rating, err = self._get_rating(request, pk)
        if err:
            return err
        reply = (request.data.get("reply") or "").strip()
        if not reply:
            return Response({"detail": "Reply text is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(reply) > 1000:
            return Response({"detail": "Reply must be 1000 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)
        from django.utils import timezone as _tz
        rating.owner_reply = reply
        rating.owner_reply_at = _tz.now()
        rating.save(update_fields=["owner_reply", "owner_reply_at"])
        return Response({
            "owner_reply": rating.owner_reply,
            "owner_reply_at": rating.owner_reply_at.isoformat(),
        })

    def delete(self, request, pk, *args, **kwargs):
        rating, err = self._get_rating(request, pk)
        if err:
            return err
        rating.owner_reply = ""
        rating.owner_reply_at = None
        rating.save(update_fields=["owner_reply", "owner_reply_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Closure dates (holiday / one-off closures) ────────────────────────────────

def _is_tenant_owner(request) -> bool:
    """Return True ONLY for the tenant owner (or platform-level staff/superuser).

    Tenant STAFF (waiters) are intentionally excluded — owner-exclusive endpoints
    (revenue, promotions, settings, billing, loyalty, float, customer directory…)
    must not be reachable by staff. Staff capabilities go through the perm-specific
    helpers (_can_edit_tenant_order / _can_view_revenue / _can_edit_menu).
    """
    user = request.user
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_platform_admin", False):
        return True
    tenant = getattr(request, "tenant", None)
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    return user.role == user.Roles.TENANT_OWNER


def _bust_meta_cache_for_request(request) -> None:
    """Evict the tenant's /api/meta/ cache (all locale variants). Best-effort + lazy
    import so a menu→tenancy import cycle never forms and a bust failure never breaks
    the caller. Used by closure-date writes: a closure flips is_open_now on the cached
    meta payload, but the post-cache recompute reads a frozen closure_today, so the
    closed state would otherwise lag the 300s TTL."""
    try:
        from tenancy.api import _bust_tenant_meta_cache
        _bust_tenant_meta_cache(getattr(getattr(request, "tenant", None), "slug", ""))
    except Exception:
        pass


class OwnerClosureDateListCreateView(APIView):
    """
    GET  /api/owner/closure-dates/  — list all closure dates (soonest first)
    POST /api/owner/closure-dates/  — add a new closure date
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)
        from .models import ClosureDate
        qs = ClosureDate.objects.order_by("date")
        data = [{"id": c.id, "date": c.date.isoformat(), "label": c.label} for c in qs]
        return Response(data)

    def post(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)
        date_str = (request.data.get("date") or "").strip()
        label = (request.data.get("label") or "").strip()[:100]
        if not date_str:
            return Response({"detail": "date is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from datetime import date as _date
            parsed_date = _date.fromisoformat(date_str)
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        from .models import ClosureDate
        try:
            obj = ClosureDate.objects.create(date=parsed_date, label=label)
        except IntegrityError:
            return Response({"detail": "This date is already marked as closed."}, status=status.HTTP_400_BAD_REQUEST)
        # A closure date flips is_open_now on the cached /api/meta/ payload (the
        # menu page). The meta cache is busted only on Profile save + on time passage
        # via the post-cache recompute, but the recompute reads a FROZEN closure_today
        # bool — so a same-day closure would stay invisible for up to the 300s TTL.
        # Bust the tenant meta cache so the closed state shows immediately. Best-effort,
        # lazy import (avoids menu→tenancy import cycle at module load).
        _bust_meta_cache_for_request(request)
        return Response(
            {"id": obj.id, "date": obj.date.isoformat(), "label": obj.label},
            status=status.HTTP_201_CREATED,
        )


class OwnerClosureDateDeleteView(APIView):
    """
    DELETE /api/owner/closure-dates/<closure_id>/  — remove a closure date
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, closure_id, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)
        from .models import ClosureDate
        try:
            obj = ClosureDate.objects.get(id=closure_id)
        except ClosureDate.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        # Removing a closure date re-opens the restaurant — bust the meta cache so
        # /api/meta/ reflects it immediately (see _bust_meta_cache_for_request).
        _bust_meta_cache_for_request(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnerInvoiceView(APIView):
    """
    GET /api/owner/invoice/?request_id=<id>

    Generates and streams a PDF invoice for an approved TierUpgradeRequest.
    Only accessible by the tenant owner. The request must belong to the
    current tenant and have status=approved plus a non-null invoice_amount.

    Returns HTTP 400 if invoice_amount is not set (admin must fill it in first).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=403)

        request_id = request.query_params.get("request_id", "")
        if not request_id:
            return Response({"detail": "request_id query parameter is required."}, status=400)

        # Load from public schema — TierUpgradeRequest lives there.
        from django_tenants.utils import schema_context
        from sales.models import TierUpgradeRequest

        try:
            with schema_context("public"):
                upgrade_req = TierUpgradeRequest.objects.select_related(
                    "tenant", "current_plan", "target_plan", "approved_by"
                ).get(pk=request_id, tenant=request.tenant)
        except (TierUpgradeRequest.DoesNotExist, ValueError):
            return Response({"detail": "Invoice not found."}, status=404)

        if upgrade_req.status != TierUpgradeRequest.Status.APPROVED:
            return Response({"detail": "Invoice is only available for approved requests."}, status=400)

        if upgrade_req.invoice_amount is None:
            return Response(
                {"detail": "Invoice amount has not been set. Contact support to complete your invoice."},
                status=400,
            )

        # Build PDF
        buffer = BytesIO()
        doc = canvas.Canvas(buffer, pagesize=A4)
        page_w, page_h = A4
        margin = 20 * mm

        # ── Header ────────────────────────────────────────────────────────
        doc.setFillColorRGB(0.059, 0.737, 0.545)  # brand teal
        doc.rect(0, page_h - 40 * mm, page_w, 40 * mm, fill=1, stroke=0)

        doc.setFillColorRGB(1, 1, 1)
        doc.setFont("Helvetica-Bold", 22)
        doc.drawString(margin, page_h - 20 * mm, "INVOICE")

        tenant_name = upgrade_req.tenant.name or upgrade_req.tenant.slug
        doc.setFont("Helvetica", 11)
        doc.drawRightString(page_w - margin, page_h - 18 * mm, tenant_name)
        doc.setFont("Helvetica", 9)
        doc.drawRightString(page_w - margin, page_h - 26 * mm, upgrade_req.tenant.slug)

        # ── Invoice metadata ──────────────────────────────────────────────
        y = page_h - 55 * mm
        doc.setFillColorRGB(0.2, 0.2, 0.2)
        doc.setFont("Helvetica-Bold", 9)
        doc.drawString(margin, y, "INVOICE NUMBER")
        doc.drawString(page_w / 2, y, "DATE")
        doc.setFont("Helvetica", 10)
        doc.setFillColorRGB(0, 0, 0)
        doc.drawString(margin, y - 5 * mm, f"INV-{upgrade_req.id:05d}")
        issued_date = (upgrade_req.decided_at or upgrade_req.requested_at).strftime("%d %b %Y")
        doc.drawString(page_w / 2, y - 5 * mm, issued_date)

        # ── Divider ───────────────────────────────────────────────────────
        y -= 14 * mm
        doc.setStrokeColorRGB(0.85, 0.85, 0.85)
        doc.setLineWidth(0.4)
        doc.line(margin, y, page_w - margin, y)

        # ── Line items header ─────────────────────────────────────────────
        y -= 8 * mm
        doc.setFont("Helvetica-Bold", 9)
        doc.setFillColorRGB(0.4, 0.4, 0.4)
        doc.drawString(margin, y, "DESCRIPTION")
        doc.drawRightString(page_w - margin, y, "AMOUNT")

        y -= 5 * mm
        doc.line(margin, y, page_w - margin, y)

        # ── Line item ─────────────────────────────────────────────────────
        y -= 8 * mm
        doc.setFont("Helvetica", 10)
        doc.setFillColorRGB(0, 0, 0)
        plan_desc = f"Plan upgrade: {upgrade_req.current_plan.name} → {upgrade_req.target_plan.name}"
        doc.drawString(margin, y, plan_desc)

        currency = upgrade_req.invoice_currency or "USD"
        amount_str = f"{currency} {upgrade_req.invoice_amount:,.2f}"
        doc.drawRightString(page_w - margin, y, amount_str)

        if upgrade_req.payment_reference:
            y -= 6 * mm
            doc.setFont("Helvetica-Oblique", 8)
            doc.setFillColorRGB(0.5, 0.5, 0.5)
            doc.drawString(margin, y, f"Payment ref: {upgrade_req.payment_reference}")

        # ── Total ─────────────────────────────────────────────────────────
        y -= 10 * mm
        doc.line(margin, y, page_w - margin, y)
        y -= 7 * mm
        doc.setFont("Helvetica-Bold", 12)
        doc.setFillColorRGB(0, 0, 0)
        doc.drawString(margin, y, "TOTAL")
        doc.drawRightString(page_w - margin, y, amount_str)

        # ── Footer ────────────────────────────────────────────────────────
        doc.setFont("Helvetica", 8)
        doc.setFillColorRGB(0.6, 0.6, 0.6)
        doc.drawCentredString(
            page_w / 2,
            15 * mm,
            "Thank you for your business. For billing questions, contact support.",
        )

        doc.save()
        pdf_bytes = buffer.getvalue()
        buffer.close()

        filename = f"invoice-INV-{upgrade_req.id:05d}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class OwnerCommissionStatementView(APIView):
    """
    GET /api/owner/commission-statement/?year=YYYY&month=M[&format=pdf]

    Monthly commission breakdown for marketplace orders.
    Returns JSON by default; add ?format=pdf for a downloadable PDF statement.

    The statement shows every marketplace order in the requested month with its
    food subtotal, commission charged (at the per-order snapshotted rate), and net
    payout, plus summary totals.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=403)

        from calendar import month_name
        from datetime import datetime as _dt

        # Resolve the tenant profile so we can bucket the month in the tenant's
        # LOCAL timezone (see below); fall back to None → UTC behaviour.
        try:
            _profile = request.tenant.profile
        except Exception:
            _profile = None

        # Parse year/month, defaulting to the current TENANT-LOCAL month (so the
        # default month matches what the owner sees on their wall clock).
        local_now = _profile_now(_profile) if _profile is not None else timezone.now()
        try:
            year = int(request.query_params.get("year", local_now.year))
            month = int(request.query_params.get("month", local_now.month))
            if not (1 <= month <= 12) or year < 2000:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year/month parameters."}, status=400)

        fmt = request.query_params.get("format", "json").lower()

        # A5: bucket by the TENANT-LOCAL month, not UTC. The old
        # created_at__year/__month filter ran in UTC and mis-bucketed a late-night
        # month-boundary order for a non-UTC tenant (e.g. an order placed 23:30 on
        # the 31st local — already next month in UTC — leaked into the wrong
        # statement). Build the local month's [start, next-month-start) range in the
        # tenant tz (same tenant-tz approach as the OPS-2 Z-report / service_day_window)
        # and filter created_at__gte/__lt on it. created_at is stored tz-aware (UTC),
        # so Django converts these aware bounds correctly for the comparison.
        try:
            from zoneinfo import ZoneInfo
            tz_name = (getattr(_profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
            _tz = ZoneInfo(tz_name)
        except Exception:
            from datetime import timezone as _stdlib_tz
            _tz = _stdlib_tz.utc
        month_start = _dt(year, month, 1, 0, 0, 0, tzinfo=_tz)
        _ny, _nm = (year + 1, 1) if month == 12 else (year, month + 1)
        next_month_start = _dt(_ny, _nm, 1, 0, 0, 0, tzinfo=_tz)

        # Query marketplace orders for this local month.
        #
        # A5-followup FIX 1: EXCLUDE cancelled orders. A cancelled marketplace order
        # has had its food revenue fully refunded (MarketplaceOrderCancelView /
        # _refund_wallet_for_cancelled_order), so the platform must NOT bill
        # commission on it — billing commission on a refunded order would charge the
        # restaurant for revenue it never kept. CANCELLED is the only "no revenue
        # collected" terminal status in Order.Status (there is no separate
        # declined/refunded terminal state; a fully item-voided order keeps its
        # status but its commission is reduced to 0 at void time — FIX 2). COMPLETED
        # and all in-progress states (PENDING/SCHEDULED/CONFIRMED/PREPARING/READY/
        # OUT_FOR_DELIVERY) stay INCLUDED. The exclusion is applied ONCE on the base
        # queryset so the aggregate Sum and the per-order rows below agree.
        qs = (
            Order.objects
            .filter(
                source=Order.Source.MARKETPLACE,
                created_at__gte=month_start,
                created_at__lt=next_month_start,
            )
            .exclude(status=Order.Status.CANCELLED)
            .order_by("created_at")
        )

        # ── Commission BASIS note (A5, step 5) ────────────────────────────────
        # commission_amount is charged on the PRE-discount food_subtotal (see
        # accounts/views.py marketplace checkout), whereas total_revenue below is
        # the sum of Order.total which is POST-discount AND tip-inclusive. So when a
        # discount or tip applies, net_payout = total_revenue - total_commission
        # MIXES bases (commission on pre-discount food vs revenue on post-discount
        # + tip). This is documented, not silently changed: whether to switch
        # commission to the post-discount food total is an OWNER business decision.
        orders_data = [
            {
                "order_number": o.order_number,
                "created_at": o.created_at.isoformat(),
                "customer_name": o.customer_name or "",
                "total": float(o.total),
                # Delivery fee is NOT restaurant revenue — it passes through to the driver
                # (minus platform's delivery commission). net_payout subtracts it so the
                # restaurant sees only what it actually earns.
                "delivery_fee": float(o.delivery_fee),
                "commission_amount": float(o.commission_amount),
                # A5: surface the snapshotted rate so each row's commission is auditable.
                "commission_rate_applied": float(o.commission_rate_applied),
                "net_payout": float((o.total - o.delivery_fee - o.commission_amount).quantize(Decimal("0.01"))),
                "currency": o.currency,
                "status": o.status,
            }
            for o in qs
        ]

        # ── A5-followup FIX 3: per-CURRENCY totals ────────────────────────────────
        # A single marketplace tenant can take orders in more than one ISO currency
        # (a multi-locale storefront, a tenant that re-priced mid-month, etc.).
        # Summing Order.total / Order.commission_amount ACROSS currencies produces a
        # meaningless number (10 MAD + 10 USD ≠ 20 of anything) and the old PDF then
        # stamped EVERY row with orders_data[0]['currency'], mislabelling foreign-
        # currency rows. We therefore bucket totals by currency. We aggregate in
        # Python from the already-materialised rows (one pass, no extra query) using
        # Decimal so the money math is exact, then expose floats in the JSON to match
        # the existing row shape. `per_currency` preserves order of first appearance.
        from collections import OrderedDict
        _by_cur: "OrderedDict[str, dict]" = OrderedDict()
        for o in orders_data:
            cur = o["currency"] or ""
            bucket = _by_cur.get(cur)
            if bucket is None:
                bucket = _by_cur[cur] = {
                    "currency": cur,
                    "order_count": 0,
                    "_revenue": Decimal("0"),
                    "_delivery_fees": Decimal("0"),
                    "_commission": Decimal("0"),
                }
            bucket["order_count"] += 1
            bucket["_revenue"] += Decimal(str(o["total"]))
            bucket["_delivery_fees"] += Decimal(str(o["delivery_fee"]))
            bucket["_commission"] += Decimal(str(o["commission_amount"]))

        per_currency = []
        for bucket in _by_cur.values():
            rev = bucket["_revenue"]
            del_fees = bucket["_delivery_fees"]
            com = bucket["_commission"]
            per_currency.append({
                "currency": bucket["currency"],
                "order_count": bucket["order_count"],
                "total_revenue": float(rev),
                "total_delivery_fees": float(del_fees),
                "total_commission": float(com),
                # net_payout is what the restaurant actually earns: gross revenue minus
                # delivery pass-through (driver's) and the platform food commission.
                "net_payout": float((rev - del_fees - com).quantize(Decimal("0.01"))),
            })

        order_count = len(orders_data)

        # Single-currency case (the common case): keep the historical top-level
        # `summary` shape so existing JSON consumers are unchanged. Mixed-currency
        # months get a summary with currency="" and zeroed cross-currency money to
        # signal that the meaningful breakdown lives in `per_currency` (we refuse to
        # publish a cross-currency sum). `per_currency` is ALWAYS present.
        if len(per_currency) == 1:
            _single = per_currency[0]
            summary = {
                "order_count": order_count,
                "total_revenue": _single["total_revenue"],
                "total_commission": _single["total_commission"],
                "net_payout": _single["net_payout"],
                "currency": _single["currency"],
            }
        else:
            summary = {
                "order_count": order_count,
                "total_revenue": 0.0,
                "total_commission": 0.0,
                "net_payout": 0.0,
                "currency": "",
                "mixed_currency": True,
            }

        if fmt != "pdf":
            return Response({
                "year": year,
                "month": month,
                "month_name": month_name[month],
                "summary": summary,
                "per_currency": per_currency,
                "orders": orders_data,
            })

        # ── PDF ───────────────────────────────────────────────────────────────
        # A5-followup FIX 3: render the summary + totals PER CURRENCY, each labelled
        # with ITS OWN currency code — never orders_data[0]['currency'] for every
        # line (which mislabelled foreign-currency money on a mixed-currency month).

        # Derive the commission label from the per-order snapshotted rates rather
        # than a hardcoded "10%": the platform can set a non-default rate per
        # tenant (Profile.marketplace_commission_pct), so a literal would misstate
        # the rate on an official money document. Show the exact rate only when
        # every order in the month carries the same snapshotted rate; otherwise
        # drop the percentage (mixed rates can't be summarised by one number).
        _distinct_rates = {o["commission_rate_applied"] for o in orders_data}
        if len(_distinct_rates) == 1:
            _pct = next(iter(_distinct_rates)) * 100
            # Trim trailing zeros so 10.00 → "10%" and 12.50 → "12.5%".
            _pct_str = f"{_pct:.2f}".rstrip("0").rstrip(".")
            commission_label = f"Platform commission ({_pct_str}%):"
        else:
            commission_label = "Platform commission:"

        buffer = BytesIO()
        doc = canvas.Canvas(buffer, pagesize=A4)
        page_w, page_h = A4
        margin = 20 * mm

        # Header bar
        doc.setFillColorRGB(0.059, 0.059, 0.314)  # deep indigo
        doc.rect(0, page_h - 38 * mm, page_w, 38 * mm, fill=1, stroke=0)

        doc.setFillColorRGB(1, 1, 1)
        doc.setFont("Helvetica-Bold", 18)
        doc.drawString(margin, page_h - 18 * mm, "Marketplace Commission Statement")
        doc.setFont("Helvetica", 10)
        doc.drawString(margin, page_h - 29 * mm, f"{month_name[month]} {year}")

        y = page_h - 50 * mm

        # Summary box — one sub-block per currency (each labelled with its own code).
        # Height scales with the number of currencies: a header line (order count)
        # plus 4 money lines per currency (gross, delivery pass-through, commission, net),
        # with a blank separator between currencies.
        _n_cur = max(1, len(per_currency))
        _box_h = (3 + _n_cur * 5) * 5 * mm  # rough: count line + 4 money lines × N + spacing
        doc.setFillColorRGB(0.94, 0.95, 0.98)
        doc.rect(margin, y - _box_h, page_w - 2 * margin, _box_h, fill=1, stroke=0)
        doc.setFillColorRGB(0, 0, 0)

        sy = y - 8 * mm
        doc.setFont("Helvetica", 9)
        doc.drawString(margin + 4 * mm, sy, "Orders placed via marketplace:")
        doc.setFont("Helvetica-Bold", 9)
        doc.drawRightString(page_w - margin - 4 * mm, sy, str(order_count))
        sy -= 7 * mm

        for _pc in per_currency:
            _cur = _pc["currency"]
            summary_items = [
                ("Gross order revenue:", f"{_cur} {_pc['total_revenue']:,.2f}"),
                ("  Delivery pass-through:", f"- {_cur} {_pc['total_delivery_fees']:,.2f}"),
                (commission_label, f"- {_cur} {_pc['total_commission']:,.2f}"),
                ("Net payout to restaurant:", f"{_cur} {_pc['net_payout']:,.2f}"),
            ]
            for label, value in summary_items:
                doc.setFont("Helvetica", 9)
                doc.drawString(margin + 4 * mm, sy, label)
                doc.setFont("Helvetica-Bold", 9)
                doc.drawRightString(page_w - margin - 4 * mm, sy, value)
                sy -= 5 * mm
            sy -= 2 * mm  # gap between currency blocks

        y -= _box_h + 7 * mm

        # Table header
        col_widths = [45 * mm, 32 * mm, 35 * mm, 30 * mm, 30 * mm]
        col_labels = ["Order #", "Date", "Revenue", "Commission", "Net Payout"]
        col_x = [margin]
        for w in col_widths[:-1]:
            col_x.append(col_x[-1] + w)

        doc.setFillColorRGB(0.2, 0.2, 0.4)
        doc.rect(margin, y - 7 * mm, page_w - 2 * margin, 7 * mm, fill=1, stroke=0)
        doc.setFillColorRGB(1, 1, 1)
        doc.setFont("Helvetica-Bold", 8)
        for i, label in enumerate(col_labels):
            if i < 2:
                doc.drawString(col_x[i] + 2 * mm, y - 5 * mm, label)
            else:
                doc.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - 5 * mm, label)
        y -= 7 * mm

        # Table rows
        doc.setFillColorRGB(0, 0, 0)
        row_h = 6 * mm
        for idx, o in enumerate(orders_data):
            if y < 25 * mm:  # new page
                doc.showPage()
                y = page_h - 20 * mm
            bg = 0.97 if idx % 2 == 0 else 1.0
            doc.setFillColorRGB(bg, bg, bg)
            doc.rect(margin, y - row_h, page_w - 2 * margin, row_h, fill=1, stroke=0)
            doc.setFillColorRGB(0, 0, 0)
            doc.setFont("Helvetica", 8)
            date_str = o["created_at"][:10]
            row_vals = [o["order_number"], date_str,
                        f"{o['currency']} {o['total']:,.2f}",
                        f"{o['currency']} {o['commission_amount']:,.2f}",
                        f"{o['currency']} {o['net_payout']:,.2f}"]
            for i, val in enumerate(row_vals):
                if i < 2:
                    doc.drawString(col_x[i] + 2 * mm, y - 4.5 * mm, val)
                else:
                    doc.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - 4.5 * mm, val)
            y -= row_h

        # Totals row(s) — one per currency, each labelled with its own code so a
        # mixed-currency month never sums dissimilar currencies into one figure.
        y -= 2 * mm
        doc.line(margin, y, page_w - margin, y)
        y -= 5 * mm
        for _pc in per_currency:
            if y < 20 * mm:  # spill the totals onto a new page if we ran out of room
                doc.showPage()
                y = page_h - 20 * mm
            _cur = _pc["currency"]
            _label = "TOTALS" if len(per_currency) == 1 else f"TOTALS ({_cur})"
            doc.setFont("Helvetica-Bold", 9)
            doc.drawString(margin + 2 * mm, y, _label)
            doc.drawRightString(col_x[2] + col_widths[2] - 2 * mm, y, f"{_cur} {_pc['total_revenue']:,.2f}")
            doc.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y, f"{_cur} {_pc['total_commission']:,.2f}")
            doc.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y, f"{_cur} {_pc['net_payout']:,.2f}")
            y -= 5 * mm

        # Footer
        doc.setFont("Helvetica", 7)
        doc.setFillColorRGB(0.55, 0.55, 0.55)
        doc.drawCentredString(page_w / 2, 12 * mm, "This statement is auto-generated. Contact support for billing queries.")

        doc.save()
        pdf_bytes = buffer.getvalue()
        buffer.close()

        filename = f"commission-{year}-{month:02d}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class OwnerDataExportView(APIView):
    """
    GET /api/owner/data-export/

    Returns a JSON file containing a complete snapshot of all tenant-owned data.
    Intended for GDPR-compliant data portability and backup purposes.

    Requires owner authentication.

    Exported sections:
        - profile              Restaurant settings & branding
        - menu                 Super categories, categories, dishes, option groups
        - orders               All orders with items (capped at 10 000 rows for performance)
        - ratings              All ratings
        - staff                Staff accounts (no password hashes)
        - tables               Table link configurations
        - closure_dates        Holiday / closure date records
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        import json
        from django.db import connection as _conn

        tenant = getattr(request, "tenant", None)
        schema = getattr(_conn, "schema_name", "unknown")
        exported_at = timezone.now().isoformat()

        # ── Profile ──────────────────────────────────────────────────────────
        profile_data = {}
        try:
            from tenancy.models import Profile as _Profile
            p = _Profile.objects.get(tenant=tenant)
            profile_data = {
                "tagline": p.tagline,
                "description": p.description,
                "business_hours": p.business_hours,
                "phone": p.phone,
                "whatsapp": p.whatsapp,
                "address": p.address,
                "google_maps_url": p.google_maps_url,
                "reservation_url": p.reservation_url,
                "facebook_url": p.facebook_url,
                "instagram_url": p.instagram_url,
                "tiktok_url": p.tiktok_url,
                "language": p.language,
                "logo_url": p.logo_url,
                "hero_url": p.hero_url,
                "delivery_enabled": p.delivery_enabled,
                "delivery_fee": str(p.delivery_fee),
                "delivery_base_fee": str(p.delivery_base_fee),
                "delivery_per_km": str(p.delivery_per_km),
                "delivery_free_over": str(p.delivery_free_over),
                "delivery_radius_km": p.delivery_radius_km,
                "delivery_minimum_order": str(p.delivery_minimum_order),
                "delivery_zone_description": p.delivery_zone_description,
                # Restaurant coordinates so the cart can preview a distance-based fee.
                "lat": p.lat,
                "lng": p.lng,
                "receipt_message": p.receipt_message,
                "is_open": p.is_open,
                "is_menu_published": p.is_menu_published,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
        except Exception:
            pass

        # ── Menu ─────────────────────────────────────────────────────────────
        super_cats = list(
            SuperCategory.objects.values(
                "name", "name_i18n", "slug", "position", "is_published"
            )
        )
        categories = list(
            Category.objects.select_related("super_category").values(
                "name", "name_i18n", "slug", "description", "description_i18n",
                "position", "is_published", "super_category__slug",
            )
        )
        dishes = list(
            Dish.objects.select_related("category").values(
                "name", "name_i18n", "slug", "description", "description_i18n",
                "price", "currency", "position", "tags", "allergens",
                "is_published", "is_available", "category__slug",
            )
        )
        option_groups = []
        try:
            for og in OptionGroup.objects.prefetch_related("options").all():
                option_groups.append({
                    "name": og.name,
                    "required": og.required,
                    "multi_select": og.multi_select,
                    "max_selections": og.max_selections,
                    "dish_slug": og.dish.slug if og.dish_id else None,
                    "options": list(og.options.values("name", "price_delta", "currency", "is_available")),
                })
        except Exception:
            pass

        # ── Orders ───────────────────────────────────────────────────────────
        orders_qs = Order.objects.prefetch_related("items").order_by("-created_at")[:10000]
        orders_data = []
        for o in orders_qs:
            orders_data.append({
                "order_number": o.order_number,
                "status": o.status,
                "fulfillment_type": o.fulfillment_type,
                "total": str(o.total),
                "currency": o.currency,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "customer_note": o.customer_note,
                "table_label": o.table_label,
                "delivery_address": getattr(o, "delivery_address", ""),
                "created_at": o.created_at.isoformat(),
                "items": [
                    {
                        "dish_name": item.dish_name,
                        "qty": item.qty,
                        "unit_price": str(item.unit_price),
                        "currency": item.currency,
                    }
                    for item in o.items.all()
                ],
            })

        # ── Ratings ──────────────────────────────────────────────────────────
        ratings_data = list(
            Rating.objects.values("score", "comment", "order__order_number", "created_at")
        )
        for r in ratings_data:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].isoformat()

        # ── Staff ────────────────────────────────────────────────────────────
        staff_data = []
        try:
            from django.db import connection as _c
            from django_tenants.utils import schema_context
            with schema_context("public"):
                from accounts.models import User as _User
                for u in _User.objects.filter(tenant=tenant, role="tenant_staff").values(
                    "email", "name", "is_active",
                    "perm_manage_orders", "perm_view_revenue", "perm_edit_menu",
                ):
                    staff_data.append(dict(u))
        except Exception:
            pass

        # ── Tables ───────────────────────────────────────────────────────────
        tables_data = list(TableLink.objects.values("slug", "label", "is_active", "position"))

        # ── Closure dates ────────────────────────────────────────────────────
        closure_data = []
        try:
            from .models import ClosureDate
            closure_data = [
                {"date": cd.date.isoformat(), "label": cd.label}
                for cd in ClosureDate.objects.order_by("date")
            ]
        except Exception:
            pass

        export = {
            "exported_at": exported_at,
            "schema": schema,
            "profile": profile_data,
            "menu": {
                "super_categories": super_cats,
                "categories": categories,
                "dishes": dishes,
                "option_groups": option_groups,
            },
            "orders": orders_data,
            "ratings": ratings_data,
            "staff": staff_data,
            "tables": tables_data,
            "closure_dates": closure_data,
        }

        filename = f"restaurant-export-{timezone.now().strftime('%Y%m%d')}.json"
        response = HttpResponse(
            json.dumps(export, indent=2, default=str),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ── Capacity helpers ──────────────────────────────────────────────────────────

def _slot_floor(dt, slot_minutes):
    """Floor a datetime to the nearest slot boundary."""
    total = dt.hour * 60 + dt.minute
    start = (total // slot_minutes) * slot_minutes
    return dt.replace(hour=start // 60, minute=start % 60, second=0, microsecond=0)


def _build_day_slots(date_obj, slot_minutes, tz):
    """
    Generate all slot start times for a given calendar date from 09:00 to 22:00.
    Returns a list of timezone-aware datetimes.
    """
    from django.utils.timezone import make_aware
    slots = []
    current_minutes = 9 * 60
    end_minutes = 22 * 60
    while current_minutes < end_minutes:
        h, m = divmod(current_minutes, 60)
        dt = make_aware(
            datetime(date_obj.year, date_obj.month, date_obj.day, h, m, 0),
            tz,
        )
        slots.append(dt)
        current_minutes += slot_minutes
    return slots


class SlotAvailabilityView(APIView):
    """
    GET /api/availability/?date=YYYY-MM-DD
    Public endpoint. Returns reservation slot availability for the given date.
    Only meaningful when max_covers_per_slot > 0 on the restaurant profile.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ReservationAvailabilityThrottle]

    def get(self, request):
        from datetime import date as date_cls
        from django.db.models import Sum
        from django.utils import timezone as tz_utils
        from django_tenants.utils import get_public_schema_name, schema_context as _sc

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        date_raw = request.query_params.get("date", "").strip()
        if not date_raw:
            return Response({"detail": "date parameter is required (YYYY-MM-DD)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            target_date = date_cls.fromisoformat(date_raw)
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        profile = Profile.objects.filter(tenant=tenant).first()
        max_covers = getattr(profile, "max_covers_per_slot", 0) or 0
        slot_minutes = getattr(profile, "slot_duration_minutes", 60) or 60

        local_tz = tz_utils.get_current_timezone()
        slots = _build_day_slots(target_date, slot_minutes, local_tz)

        if not slots:
            return Response({
                "date": date_raw,
                "slots": [],
                "max_covers": max_covers,
                "slot_duration_minutes": slot_minutes,
                "capacity_enabled": max_covers > 0,
            })

        slot_end_dt = slots[-1] + timedelta(minutes=slot_minutes)
        used_by_slot = {}

        if max_covers > 0:
            try:
                with _sc(get_public_schema_name()):
                    from sales.models import Lead as _Lead
                    ACTIVE = {_Lead.Status.NEW, _Lead.Status.CONTACTED, _Lead.Status.WON}
                    qs = _Lead.objects.filter(
                        tenant_id=tenant.id,
                        booked_for__gte=slots[0],
                        booked_for__lt=slot_end_dt,
                        status__in=ACTIVE,
                    ).values("booked_for", "party_size")
                    for row in qs:
                        if row["booked_for"] is None:
                            continue
                        slot_key = _slot_floor(row["booked_for"].astimezone(local_tz), slot_minutes)
                        used_by_slot[slot_key] = used_by_slot.get(slot_key, 0) + (row["party_size"] or 0)
            except Exception:
                pass

        result = []
        for slot_dt in slots:
            used = used_by_slot.get(slot_dt, 0)
            result.append({
                "time": slot_dt.strftime("%H:%M"),
                "datetime": slot_dt.isoformat(),
                "used": used,
                "max": max_covers,
                "available": max(0, max_covers - used) if max_covers > 0 else None,
                "full": (used >= max_covers) if max_covers > 0 else False,
            })

        return Response({
            "date": date_raw,
            "slots": result,
            "max_covers": max_covers,
            "slot_duration_minutes": slot_minutes,
            "capacity_enabled": max_covers > 0,
        })


class WaitlistJoinView(APIView):
    """
    POST /api/waitlist/
    Public endpoint. Adds a customer to the waitlist for a full time slot.
    Body: { name, phone, email, booked_for (ISO datetime), party_size, notes, hp }
    """
    permission_classes = [AllowAny]
    throttle_classes = [WaitlistJoinThrottle]

    def post(self, request):
        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import make_aware, is_naive

        name = str(request.data.get("name") or "").strip()
        phone = str(request.data.get("phone") or "").strip()
        email = str(request.data.get("email") or "").strip()
        booked_for_raw = str(request.data.get("booked_for") or "").strip()
        party_size_raw = request.data.get("party_size") or 1
        notes = str(request.data.get("notes") or "").strip()

        if not name or len(name) < 2:
            return Response({"detail": "name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not phone and not email:
            return Response({"detail": "phone or email is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not booked_for_raw:
            return Response({"detail": "booked_for is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            booked_for = parse_datetime(booked_for_raw)
            if booked_for is None:
                raise ValueError("unparseable")
            if is_naive(booked_for):
                booked_for = make_aware(booked_for)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid booked_for datetime."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            party_size = max(1, int(party_size_raw))
        except (TypeError, ValueError):
            party_size = 1

        # Honeypot check
        if str(request.data.get("hp") or "").strip():
            return Response({"status": "ok"})

        entry = WaitlistEntry.objects.create(
            booked_for=booked_for,
            party_size=party_size,
            name=name,
            phone=phone,
            email=email,
            notes=notes,
        )
        return Response({"status": "waitlisted", "id": entry.id}, status=status.HTTP_201_CREATED)


class OwnerWaitlistView(APIView):
    """
    GET /api/owner/waitlist/?date=YYYY-MM-DD
    Owner only. Returns waitlist entries (filtered by date if provided).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import date as date_cls
        from django.utils.timezone import make_aware, get_current_timezone

        if not _is_tenant_owner(request):
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        date_raw = request.query_params.get("date", "").strip()
        qs = WaitlistEntry.objects.all()

        if date_raw:
            try:
                target_date = date_cls.fromisoformat(date_raw)
            except ValueError:
                return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)
            local_tz = get_current_timezone()
            day_start = make_aware(
                datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0), local_tz
            )
            day_end = day_start + timedelta(days=1)
            qs = qs.filter(booked_for__gte=day_start, booked_for__lt=day_end)

        entries = list(qs.values(
            "id", "booked_for", "party_size", "name", "phone", "email",
            "notes", "status", "notified_at", "created_at",
        ))
        for e in entries:
            for field in ("booked_for", "notified_at", "created_at"):
                if e.get(field):
                    e[field] = e[field].isoformat()

        return Response({"results": entries, "count": len(entries)})


# ── Web Push notification endpoints ───────────────────────────────────────────


class OwnerPushVapidKeyView(APIView):
    """
    GET /api/owner/push-vapid-key/
    Returns the VAPID public key for frontend subscription registration.
    Public endpoint — needed before the user is authenticated to register the SW.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        vapid_public = (settings.VAPID_PUBLIC_KEY or "").strip()
        if not vapid_public:
            return Response({"enabled": False, "public_key": None})
        return Response({"enabled": True, "public_key": vapid_public})


class OwnerPushSubscribeView(APIView):
    """
    POST   /api/owner/push-subscribe/   — register a browser push subscription
    DELETE /api/owner/push-subscribe/   — remove a browser push subscription
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        endpoint = (request.data.get("endpoint") or "").strip()
        p256dh = (request.data.get("p256dh") or "").strip()
        auth_key = (request.data.get("auth") or "").strip()

        if not all([endpoint, p256dh, auth_key]):
            return Response(
                {"detail": "endpoint, p256dh, and auth are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .models import PushSubscription
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user_id": request.user.id, "p256dh": p256dh, "auth": auth_key},
        )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        endpoint = (request.data.get("endpoint") or "").strip()
        if endpoint:
            from .models import PushSubscription
            PushSubscription.objects.filter(endpoint=endpoint).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Owner Customer CRM ────────────────────────────────────────────────────────

class OwnerCustomerListView(APIView):
    """
    GET /api/owner/customers/

    Returns aggregated customer profiles from Order data, merging:
      • Linked orders  — grouped by customer_id (platform accounts)
      • Anonymous orders — grouped by customer_phone (no account)

    Query params:
      segment  = all | new | returning | at_risk   (default: all)
      search   = free-text match on name / phone / email
      sort     = last_order | total_spend | order_count   (default: last_order)
      order    = asc | desc                                 (default: desc)
      format   = json | csv                                 (default: json)
    """

    permission_classes = [IsAuthenticated]

    # Statuses that count as real completed orders
    _COUNTED = [
        "confirmed", "preparing", "ready", "out_for_delivery",
        "delivered", "completed",
    ]
    _AT_RISK_DAYS = 30   # days since last order before considered at-risk
    _NEW_THRESHOLD = 1   # ≤ this many orders → "new"

    # Default page size for the paginated JSON response (CSV is always full).
    _DEFAULT_LIMIT = 100
    _MAX_LIMIT = 500

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Count, Sum, Max, Avg, FloatField, Q
        from django.db.models.functions import Coalesce
        from django.utils import timezone as _tz
        import datetime, csv
        from io import StringIO

        now = _tz.now()
        at_risk_cutoff = now - datetime.timedelta(days=self._AT_RISK_DAYS)

        # ── OPS-4 B: server-side search filter (name / phone / email) ───────────
        # Applied at the DB layer so only matching rows are aggregated, avoiding
        # the previous pattern of fetching all 3k customers and filtering in Python.
        #
        # Email is NOT stored on Order — it belongs to the platform Customer
        # account (public schema, FK from Order.customer).  For linked customers
        # we can reach it via the FK join (customer__email__icontains); for
        # anonymous orders (no FK) there is no email to search.
        search = (request.query_params.get("search") or "").strip().lower()
        segment = (request.query_params.get("segment") or "all").strip().lower()

        # Push segment predicate to SQL (HAVING on aggregated annotation) so that
        # a filtered request does not materialise every customer row in Python.
        # "all" fetches everything; specific segments add a HAVING clause.
        _seg_having: dict = {}
        if segment == "at_risk":
            _seg_having = {"last_order_at__lt": at_risk_cutoff, "order_count__gt": self._NEW_THRESHOLD}
        elif segment == "new":
            _seg_having = {"order_count__lte": self._NEW_THRESHOLD}
        elif segment == "returning":
            _seg_having = {"order_count__gt": self._NEW_THRESHOLD, "last_order_at__gte": at_risk_cutoff}

        _linked_base_q = Q(customer_id__isnull=False, status__in=self._COUNTED)
        _anon_base_q = Q(customer_id__isnull=True, customer_phone__gt="", status__in=self._COUNTED)
        if search:
            # When the search term looks like a phone number (6+ stripped digits), use
            # the indexed customer_phone_digits column for an exact btree lookup on the
            # last 9 digits. Otherwise fall back to icontains for name/email-style terms.
            _search_digits = "".join(c for c in search if c.isdigit())
            if len(_search_digits) >= 6:
                _phone_q = Q(customer_phone_digits=_search_digits[-9:])
            else:
                _phone_q = Q(customer_phone__icontains=search)
            # Linked: name OR phone OR email (via FK join to platform Customer).
            _linked_search_q = (
                Q(customer_name__icontains=search)
                | _phone_q
                | Q(customer__email__icontains=search)
            )
            _linked_base_q &= _linked_search_q
            # Anon: name OR phone only (no customer account → no email).
            _anon_base_q &= Q(customer_name__icontains=search) | _phone_q

        # ── 1. Aggregate linked orders (customer_id is set) ──────────────────
        # OPS-4 B: evaluate once into a list — prevents the double GROUP BY that
        # occurred when the queryset was iterated once for linked_customer_ids
        # then again for the build loop (two separate DB round-trips, same GROUP BY).
        linked_rows = list(
            Order.objects
            .filter(_linked_base_q)
            .values("customer_id")
            .annotate(
                order_count=Count("id"),
                total_spend=Coalesce(Sum("total"), 0, output_field=FloatField()),
                last_order_at=Max("created_at"),
                avg_order_value=Coalesce(Avg("total"), 0, output_field=FloatField()),
                last_name=Max("customer_name"),
                last_phone=Max("customer_phone"),
                currency=Max("currency"),
            )
            .filter(**_seg_having)
        )

        # ── 2. Aggregate anonymous orders (no customer_id, phone only) ───────
        anon_rows = list(
            Order.objects
            .filter(_anon_base_q)
            .values("customer_phone")
            .annotate(
                order_count=Count("id"),
                total_spend=Coalesce(Sum("total"), 0, output_field=FloatField()),
                last_order_at=Max("created_at"),
                avg_order_value=Coalesce(Avg("total"), 0, output_field=FloatField()),
                last_name=Max("customer_name"),
                currency=Max("currency"),
            )
            .filter(**_seg_having)
        )

        # ── 3. Fetch CustomerRating for linked customers (public schema) ──────
        linked_customer_ids = [r["customer_id"] for r in linked_rows]
        rating_map = {}  # customer_id → avg_score
        if linked_customer_ids:
            try:
                from django.db import connection as _conn
                from accounts.models import CustomerRating
                ratings = (
                    CustomerRating.objects
                    .filter(customer_id__in=linked_customer_ids)
                    .values("customer_id")
                    .annotate(avg_score=Avg("score"))
                )
                rating_map = {r["customer_id"]: float(r["avg_score"] or 0) for r in ratings}
            except Exception:
                pass

        # ── 3b. Aggregate review scores from Rating (tenant schema) ──────────
        review_map = {}  # customer_id → {"review_count": int, "avg_review": float|None}
        if linked_customer_ids:
            try:
                review_agg = (
                    Rating.objects
                    .filter(customer_id__in=linked_customer_ids)
                    .values("customer_id")
                    .annotate(
                        review_count=Count("id"),
                        avg_score=Avg("score"),
                    )
                )
                review_map = {
                    r["customer_id"]: {
                        "review_count": r["review_count"],
                        "avg_review": round(float(r["avg_score"]), 1) if r["avg_score"] is not None else None,
                    }
                    for r in review_agg
                }
            except Exception:
                pass

        # ── 4. Fetch platform account emails + wallet balance for linked customers
        email_map = {}
        wallet_map = {}  # customer_id → wallet_balance string
        loyalty_map = {}  # customer_id → loyalty_points int
        if linked_customer_ids:
            try:
                from accounts.models import Customer as PlatformCustomer
                accounts = PlatformCustomer.objects.filter(id__in=linked_customer_ids).values("id", "email", "wallet_balance", "loyalty_points")
                for a in accounts:
                    email_map[a["id"]] = a["email"]
                    wallet_map[a["id"]] = str(a["wallet_balance"] or "0.00")
                    loyalty_map[a["id"]] = int(a["loyalty_points"] or 0)
            except Exception:
                pass

        # ── 4b. Fetch per-tenant owner notes for linked customers ─────────────
        notes_map = {}  # customer_id → notes string
        if linked_customer_ids:
            try:
                note_rows = CustomerNote.objects.filter(
                    customer_id__in=linked_customer_ids
                ).values("customer_id", "notes")
                notes_map = {n["customer_id"]: n["notes"] for n in note_rows}
            except Exception:
                pass

        # ── 5. Build unified list — single pass over already-evaluated lists ────
        # OPS-4 B: linked_rows and anon_rows are already Python lists (evaluated
        # once above). Iterating them here does NOT re-trigger the GROUP BY query.
        customers = []

        for row in linked_rows:
            cid = row["customer_id"]
            rv = review_map.get(cid, {})
            customers.append({
                "id": f"acc-{cid}",
                "type": "account",
                "customer_id": cid,
                "name": (row["last_name"] or "").strip() or "—",
                "phone": (row["last_phone"] or "").strip(),
                "email": email_map.get(cid, ""),
                "wallet_balance": wallet_map.get(cid, "0.00"),
                "loyalty_points": loyalty_map.get(cid, 0),
                "order_count": row["order_count"],
                "total_spend": float(row["total_spend"]),
                "avg_order_value": float(row["avg_order_value"]),
                "last_order_at": row["last_order_at"].isoformat() if row["last_order_at"] else None,
                "currency": row["currency"] or "",
                "trust_score": rating_map.get(cid),
                "review_count": rv.get("review_count", 0),
                "avg_review": rv.get("avg_review"),
                "owner_notes": notes_map.get(cid, ""),
            })

        for row in anon_rows:
            phone = (row["customer_phone"] or "").strip()
            customers.append({
                "id": f"anon-{phone}",
                "type": "anonymous",
                "customer_id": None,
                "name": (row["last_name"] or "").strip() or "—",
                "phone": phone,
                "email": "",
                "order_count": row["order_count"],
                "total_spend": float(row["total_spend"]),
                "avg_order_value": float(row["avg_order_value"]),
                "last_order_at": row["last_order_at"].isoformat() if row["last_order_at"] else None,
                "currency": row["currency"] or "",
                "trust_score": None,
                "review_count": 0,
                "avg_review": None,
            })

        # ── 6. Segment tagging ────────────────────────────────────────────────
        for c in customers:
            last_at = c["last_order_at"]
            if last_at:
                import datetime as _dt
                last_dt = _dt.datetime.fromisoformat(last_at)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=_dt.timezone.utc)
                is_stale = last_dt < at_risk_cutoff.replace(tzinfo=_dt.timezone.utc) if at_risk_cutoff.tzinfo is None else last_dt < at_risk_cutoff
            else:
                is_stale = True

            if c["order_count"] <= self._NEW_THRESHOLD:
                c["segment"] = "new"
            elif is_stale:
                c["segment"] = "at_risk"
            else:
                c["segment"] = "returning"

        # ── 7. Filter — DB HAVING already filtered; Python pass is a safety net ──
        if segment in ("new", "returning", "at_risk"):
            customers = [c for c in customers if c["segment"] == segment]

        # ── 8. Sort ───────────────────────────────────────────────────────────
        sort_field_map = {
            "last_order": "last_order_at",
            "total_spend": "total_spend",
            "order_count": "order_count",
        }
        sort_key = sort_field_map.get(
            (request.query_params.get("sort") or "last_order").strip().lower(),
            "last_order_at",
        )
        reverse = (request.query_params.get("order") or "desc").strip().lower() != "asc"
        customers.sort(key=lambda c: (c[sort_key] or ""), reverse=reverse)

        # ── 9. Summary stats ─────────────────────────────────────────────────
        total_count = len(customers)
        new_count = sum(1 for c in customers if c["segment"] == "new")
        returning_count = sum(1 for c in customers if c["segment"] == "returning")
        at_risk_count = sum(1 for c in customers if c["segment"] == "at_risk")

        # ── 10. CSV export ────────────────────────────────────────────────────
        if (request.query_params.get("format") or "").strip().lower() == "csv":
            buf = StringIO()
            buf.write("﻿")  # UTF-8 BOM for Excel on Windows
            writer = csv.writer(buf)
            writer.writerow([
                "Name", "Phone", "Email", "Type", "Segment",
                "Orders", "Total Spend", "Avg Order", "Currency",
                "Last Order", "Trust Score", "Review Count", "Avg Review",
            ])
            for c in customers:
                writer.writerow([
                    _csv_safe(c["name"]), _csv_safe(c["phone"]), _csv_safe(c["email"]),
                    c["type"], c["segment"],
                    c["order_count"], f"{c['total_spend']:.2f}",
                    f"{c['avg_order_value']:.2f}", c["currency"],
                    (c["last_order_at"] or "")[:10],
                    f"{c['trust_score']:.1f}" if c["trust_score"] is not None else "",
                    c.get("review_count", 0),
                    f"{c['avg_review']:.1f}" if c.get("avg_review") is not None else "",
                ])
            from django.http import HttpResponse
            response = HttpResponse(buf.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="customers.csv"'
            return response

        # ── 10b. Pagination (JSON path only; CSV always returns full list) ──────
        try:
            _c_limit = int(request.query_params.get("limit") or self._DEFAULT_LIMIT)
            _c_limit = max(1, min(_c_limit, self._MAX_LIMIT))
        except (ValueError, TypeError):
            _c_limit = self._DEFAULT_LIMIT
        try:
            _c_offset = int(request.query_params.get("offset") or 0)
            _c_offset = max(0, _c_offset)
        except (ValueError, TypeError):
            _c_offset = 0
        _page = customers[_c_offset: _c_offset + _c_limit]
        _has_more = total_count > _c_offset + _c_limit

        return Response({
            "results": _page,
            "has_more": _has_more,
            "limit": _c_limit,
            "offset": _c_offset,
            "summary": {
                "total": total_count,
                "new": new_count,
                "returning": returning_count,
                "at_risk": at_risk_count,
            },
        })


class OwnerCustomerNotesView(APIView):
    """PATCH /api/owner/customers/<customer_id>/notes/

    Upsert the restaurant's private note for a specific customer.
    Body: { "notes": "<text>" }
    Response: { "customer_id": N, "notes": "<text>" }

    The note lives in the tenant schema (CustomerNote) and is never shared
    with other restaurants that may have served the same customer.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, customer_id, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        notes_text = (request.data.get("notes") or "").strip()
        obj, _ = CustomerNote.objects.update_or_create(
            customer_id=customer_id,
            defaults={"notes": notes_text},
        )
        return Response({"customer_id": customer_id, "notes": obj.notes})


class OwnerCustomerLoyaltyGrantView(APIView):
    """POST /api/owner/customers/<customer_id>/loyalty-grant/

    Manually adjust a customer's loyalty-points balance.
    Body: { "delta": <int>, "reason": "<text>" }
      delta > 0  → grant points
      delta < 0  → deduct points  (balance is floored at 0)
      delta == 0 → no-op (returns current balance)

    Response: { "customer_id": N, "loyalty_points": <new balance> }
    """

    permission_classes = [IsAuthenticated]
    _MAX_DELTA = 100_000   # sanity cap per single grant

    def post(self, request, customer_id, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        raw_delta = request.data.get("delta")
        try:
            delta = int(raw_delta)
        except (TypeError, ValueError):
            return Response(
                {"detail": "'delta' must be an integer.", "code": "invalid_delta"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if abs(delta) > self._MAX_DELTA:
            return Response(
                {"detail": f"Adjustment magnitude exceeds the per-call cap of {self._MAX_DELTA} points."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from accounts.models import Customer as _PlatformCustomer
        from django.db import transaction as _tx

        try:
            with _tx.atomic():
                cust = _PlatformCustomer.objects.select_for_update().get(pk=customer_id)
                new_balance = max(0, cust.loyalty_points + delta)
                cust.loyalty_points = new_balance
                cust.save(update_fields=["loyalty_points", "updated_at"])
        except _PlatformCustomer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": f"Could not update loyalty points: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"customer_id": customer_id, "loyalty_points": new_balance})


class OwnerLoyaltyView(APIView):
    """GET /api/owner/loyalty/  — retrieve loyalty config (creates default if missing).
       PATCH /api/owner/loyalty/ — update loyalty config."""

    permission_classes = [IsAuthenticated]

    def _get_or_create_config(self):
        cfg, _ = LoyaltyConfig.objects.get_or_create(
            pk=1,
            defaults={
                "enabled": False,
                "points_per_unit": 10,
                "redeem_threshold": 100,
                "points_value": "0.0100",
            },
        )
        return cfg

    def _serialize(self, cfg, include_stats=False):
        data = {
            "enabled": cfg.enabled,
            "points_per_unit": cfg.points_per_unit,
            "redeem_threshold": cfg.redeem_threshold,
            "points_value": str(cfg.points_value),
            "updated_at": cfg.updated_at.isoformat(),
        }
        if include_stats:
            qs = Order.objects.filter(points_earned__gt=0)
            data["stats"] = {
                "enrolled_customers": qs.values("customer_id").distinct().count(),
                "total_points_issued": qs.aggregate(t=Sum("points_earned"))["t"] or 0,
            }
        return data

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        cfg = self._get_or_create_config()
        return Response(self._serialize(cfg, include_stats=True))

    def patch(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        from decimal import Decimal as _Dec, InvalidOperation
        cfg = self._get_or_create_config()
        data = request.data
        if "enabled" in data:
            cfg.enabled = bool(data["enabled"])
        if "points_per_unit" in data:
            try:
                val = max(1, int(data["points_per_unit"]))
                cfg.points_per_unit = val
            except (TypeError, ValueError):
                pass
        if "redeem_threshold" in data:
            try:
                val = max(1, int(data["redeem_threshold"]))
                cfg.redeem_threshold = val
            except (TypeError, ValueError):
                pass
        if "points_value" in data:
            try:
                val = _Dec(str(data["points_value"])).quantize(_Dec("0.0001"))
                if val > _Dec("0"):
                    cfg.points_value = val
            except (InvalidOperation, TypeError, ValueError):
                pass
        cfg.save()
        return Response(self._serialize(cfg))


class CustomerLoyaltyConfigView(APIView):
    """GET /api/customer/loyalty/config/ — public loyalty config for the current tenant.
    Used by the customer account page to display points info and redemption options.
    No authentication required."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            cfg = LoyaltyConfig.objects.filter(pk=1).first()
        except Exception:
            cfg = None
        if not cfg or not cfg.enabled:
            return Response({"enabled": False})
        return Response({
            "enabled": cfg.enabled,
            "points_per_unit": cfg.points_per_unit,
            "redeem_threshold": cfg.redeem_threshold,
            "points_value": str(cfg.points_value),
        })


class CustomerLoyaltyRedeemView(APIView):
    """POST /api/customer/loyalty/redeem/ — convert loyalty points into wallet credits.
    Requires authenticated customer. Body: { points: int }"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [LoyaltyRedeemThrottle]  # OPS-5g: per-customer money-movement cap

    def post(self, request, *args, **kwargs):
        from decimal import Decimal as _Dec
        from accounts.models import Customer as _CustM, WalletTransaction as _WTM
        from django.db import connection as _dbc

        # Resolve the platform Customer from the authenticated request
        try:
            _customer = _CustM.objects.get(pk=request.user.customer_id)
        except (AttributeError, _CustM.DoesNotExist):
            return Response({"detail": "Customer account not found."}, status=status.HTTP_404_NOT_FOUND)
        # No verified phone → no wallet: can't redeem points into wallet credit.
        if not _customer.phone_verified:
            return Response(
                {"detail": "Verify your phone number to use your wallet.", "code": "phone_unverified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get loyalty config
        try:
            _cfg = LoyaltyConfig.objects.filter(enabled=True).first()
        except Exception:
            _cfg = None
        if not _cfg:
            return Response({"detail": "Loyalty programme is not active.", "code": "loyalty_disabled"}, status=status.HTTP_400_BAD_REQUEST)

        # Parse requested points
        try:
            _requested_pts = max(1, int(request.data.get("points") or 0))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid points value."}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotent replay: a retried submit (e.g. a lost-response resubmit) with the
        # same key must not redeem a second time. Checked BEFORE the threshold guard,
        # because the first redemption already spent the points — re-validating would
        # wrongly reject the replay as "below threshold".
        #
        # OPS-5g/5h: WalletTransaction is PUBLIC-schema (accounts is a SHARED_APP), so
        # idempotency_key is a GLOBAL namespace. The client key here is TENANT-SCHEMA-LOCAL,
        # so server-namespace it with this tenant's schema — like the sibling money paths
        # (order-pay-{schema}-…, orderpay:{schema}:…, voiditem:{schema}:…, ownercharge:…,
        # ownertopup:…). Without this, the SAME customer reusing the SAME client key across
        # tenant A then tenant B would get tenant-A's row back as a "duplicate" and the
        # legitimate tenant-B redemption would be silently refused (credits nothing). Build
        # the namespaced key ONCE; the pre-flight read, the create, and the IntegrityError
        # refetch all use _idem.
        _raw_idem = str(request.data.get("idempotency_key") or "").strip()[:120] or None
        _idem = f"loyalty:{_dbc.schema_name}:{_raw_idem}" if _raw_idem else None
        if _idem:
            # OPS-5g IDOR: idempotency_key is a GLOBAL namespace on the shared-schema
            # WalletTransaction table and is CLIENT-supplied here. Scope the replay lookup
            # to THIS customer — otherwise an attacker who guesses/replays another
            # customer's key reads that customer's redemption (amount + points) back out.
            _prior = _WTM.objects.filter(
                idempotency_key=_idem, type=_WTM.Type.LOYALTY, customer_id=_customer.id
            ).first()
            if _prior is not None:
                _prior_pts = 0
                try:
                    _prior_pts = int(str(_prior.reference or "").split(":")[1].replace("pts", ""))
                except (IndexError, ValueError):
                    _prior_pts = 0
                return Response({
                    "redeemed_points": _prior_pts,
                    "credit_amount": str(_prior.amount),
                    "new_points_balance": _customer.loyalty_points,
                    "new_wallet_balance": str(_customer.wallet_balance),
                    "duplicate": True,
                })

        # Validate threshold and balance
        if _customer.loyalty_points < _cfg.redeem_threshold:
            return Response(
                {"detail": f"You need at least {_cfg.redeem_threshold} points to redeem. You have {_customer.loyalty_points}.",
                 "code": "below_threshold"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _redeemable = min(_requested_pts, _customer.loyalty_points)
        _credit_amount = (_Dec(str(_redeemable)) * _Dec(str(_cfg.points_value))).quantize(_Dec("0.01"))
        if _credit_amount <= _Dec("0"):
            return Response({"detail": "Redemption amount too small."}, status=status.HTTP_400_BAD_REQUEST)

        # Atomically deduct points and credit wallet
        try:
            from django.db import transaction as _dbtx
            with _dbtx.atomic():
                _locked = _CustM.objects.select_for_update().get(pk=_customer.pk)
                if not _locked.phone_verified:
                    return Response(
                        {"detail": "A verified phone number is required to use a wallet.", "code": "unverified_phone"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                if _locked.loyalty_points < _redeemable:
                    return Response({"detail": "Insufficient points.", "code": "insufficient_points"}, status=status.HTTP_400_BAD_REQUEST)
                _locked.loyalty_points -= _redeemable
                _locked.wallet_balance = _Dec(str(_locked.wallet_balance or "0")) + _credit_amount
                _locked.save(update_fields=["loyalty_points", "wallet_balance", "updated_at"])
                tenant_id = getattr(_dbc.tenant, "id", None)
                _WTM.objects.create(
                    customer=_locked,
                    type=_WTM.Type.LOYALTY,
                    amount=_credit_amount,
                    reference=f"loyalty:{_redeemable}pts",
                    tenant_id=tenant_id,
                    note=f"Redeemed {_redeemable} loyalty points",
                    balance_after=_locked.wallet_balance,
                    idempotency_key=_idem,
                )
        except IntegrityError:
            # Concurrent duplicate with the same idempotency_key — the other request
            # won the unique constraint. Treat this as an idempotent replay.
            _customer.refresh_from_db()
            # OPS-5g IDOR: same customer-scoping as the pre-flight replay lookup above —
            # never hand back another customer's redemption on the concurrent-replay path.
            _prior = (
                _WTM.objects.filter(
                    idempotency_key=_idem, type=_WTM.Type.LOYALTY, customer_id=_customer.id
                ).first()
                if _idem else None
            )
            return Response({
                "redeemed_points": 0,
                "credit_amount": str(_prior.amount) if _prior else "0.00",
                "new_points_balance": _customer.loyalty_points,
                "new_wallet_balance": str(_customer.wallet_balance),
                "duplicate": True,
            })
        except Exception as _exc:
            return Response({"detail": "Redemption failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "redeemed_points": _redeemable,
            "credit_amount": str(_credit_amount),
            "new_points_balance": _locked.loyalty_points,
            "new_wallet_balance": str(_locked.wallet_balance),
        })


class PromoCodeCheckView(APIView):
    """GET /api/promo-code-check/?code=XXX
    Returns promo validity and a preview of the discount without placing an order.
    Accessible to any authenticated customer (or unauthenticated for simplicity).
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        from decimal import Decimal as _Dec
        code = str(request.query_params.get("code") or "").strip().upper()
        if not code:
            return Response({"valid": False, "detail": "No code provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            promo = Promotion.objects.get(code__iexact=code, is_active=True)
        except Promotion.DoesNotExist:
            return Response({"valid": False, "detail": "Promo code not found."})

        # Check usage cap
        if promo.max_uses is not None and promo.use_count >= promo.max_uses:
            return Response({"valid": False, "detail": "Promo code has reached its usage limit."})

        # Check schedule — evaluate the window in the TENANT's local wall-clock time
        # (a promo "Tue 14:00–16:00" means tenant-local), not the server's. If the
        # tenant profile can't be resolved, fall back to the wrapper's consistent UTC
        # clock (now_local=None) — still tz-consistent, just not tenant-local.
        _now_local = None
        try:
            _tenant = getattr(request, "tenant", None)
            _profile = Profile.objects.filter(tenant=_tenant).first() if _tenant else None
            if _profile is not None:
                _now_local = _profile_now(_profile)
        except Exception:
            _now_local = None
        if not _is_promo_active_now(promo, now_local=_now_local):
            return Response({"valid": False, "detail": "Promo code is not active at this time."})

        return Response({
            "valid": True,
            "name": promo.name,
            "description": promo.description or "",
            "promo_type": promo.promo_type,
            "discount_value": str(promo.discount_value),
            "min_order_amount": str(promo.min_order_amount),
        })


# ── CSV template columns ──────────────────────────────────────────────────────
_CSV_COLUMNS = ["category_name", "dish_name", "description", "price", "tags", "allergens"]
_CSV_EXAMPLE_ROWS = [
    ["Starters", "Spring Rolls", "Crispy veggie rolls with sweet chilli dip", "6.50", "vegetarian", "gluten"],
    ["Starters", "Soup of the Day", "Ask your waiter for today's selection", "5.00", "", ""],
    ["Mains", "Grilled Salmon", "Atlantic salmon with lemon butter sauce", "18.00", "", "fish"],
    ["Mains", "Chicken Burger", "Free-range chicken with house slaw", "13.50", "", "gluten,dairy"],
    ["Desserts", "Chocolate Fondant", "Warm fondant with vanilla ice cream", "7.00", "vegetarian", "gluten,dairy,eggs"],
]


class OwnerMenuImportView(APIView):
    """POST /api/owner/menu/import/   — import dishes from a CSV upload.
       GET  /api/owner/menu/import/   — download a CSV template."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Return a ready-to-fill CSV template."""
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        import io as _io
        buf = _io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_CSV_COLUMNS)
        writer.writerows(_CSV_EXAMPLE_ROWS)
        response = HttpResponse(buf.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="menu_import_template.csv"'
        return response

    def post(self, request, *args, **kwargs):
        """Parse an uploaded CSV and create categories + dishes."""
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "No file uploaded.", "code": "no_file"}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded.name.lower().endswith(".csv"):
            return Response({"detail": "Only CSV files are accepted.", "code": "bad_format"}, status=status.HTTP_400_BAD_REQUEST)
        if uploaded.size > 2 * 1024 * 1024:  # 2 MB hard cap
            return Response({"detail": "File too large (max 2 MB).", "code": "too_large"}, status=status.HTTP_400_BAD_REQUEST)

        import io as _io
        from decimal import Decimal as _Dec, InvalidOperation
        from django.utils.text import slugify as _slugify

        try:
            text = uploaded.read().decode("utf-8-sig")  # utf-8-sig strips BOM if present
        except UnicodeDecodeError:
            return Response({"detail": "Could not decode file. Please save as UTF-8 CSV.", "code": "decode_error"}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(_io.StringIO(text))
        # Normalise header names: lowercase + strip
        reader.fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

        required = {"category_name", "dish_name", "price"}
        missing = required - set(reader.fieldnames)
        if missing:
            return Response(
                {"detail": f"Missing required columns: {', '.join(sorted(missing))}.", "code": "missing_columns"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_categories = 0
        created_dishes = 0
        skipped = 0
        errors = []
        category_cache = {}  # name.lower() → Category instance

        # Fetch the default super-category (position=0 / first) or create one for imports
        try:
            default_super_cat = SuperCategory.objects.order_by("position", "id").first()
            if default_super_cat is None:
                default_super_cat = SuperCategory.objects.create(
                    name="Menu",
                    slug=_make_unique_slug("menu", SuperCategory),
                    position=0,
                )
        except Exception as _e:
            return Response({"detail": f"Could not access menu structure: {_e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            cat_name = str(row.get("category_name") or "").strip()[:150]
            dish_name = str(row.get("dish_name") or "").strip()[:200]
            price_raw = str(row.get("price") or "").strip()

            if not cat_name or not dish_name:
                skipped += 1
                continue

            try:
                price = _Dec(price_raw).quantize(_Dec("0.01"))
                if price < _Dec("0"):
                    raise ValueError("negative price")
            except (InvalidOperation, ValueError):
                errors.append(f"Row {row_num}: invalid price '{price_raw}' for '{dish_name}' — skipped.")
                skipped += 1
                continue

            # Get or create category
            cat_key = cat_name.lower()
            if cat_key not in category_cache:
                existing = Category.objects.filter(name__iexact=cat_name).first()
                if existing:
                    category_cache[cat_key] = existing
                else:
                    cat_slug = _make_unique_slug(cat_name, Category)
                    new_cat = Category.objects.create(
                        super_category=default_super_cat,
                        name=cat_name,
                        slug=cat_slug,
                        position=Category.objects.count(),
                    )
                    category_cache[cat_key] = new_cat
                    created_categories += 1

            category = category_cache[cat_key]

            # Skip duplicate dish names in the same category
            if Dish.objects.filter(category=category, name__iexact=dish_name).exists():
                skipped += 1
                errors.append(f"Row {row_num}: '{dish_name}' already exists in '{cat_name}' — skipped.")
                continue

            description = str(row.get("description") or "").strip()
            # tags: comma-separated, e.g. "vegetarian,spicy"
            raw_tags = str(row.get("tags") or "").strip()
            tags = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
            # allergens: same format
            raw_allergens = str(row.get("allergens") or "").strip()
            allergens = [a.strip().lower() for a in raw_allergens.split(",") if a.strip()]

            dish_slug = _make_unique_slug(dish_name, Dish)
            Dish.objects.create(
                category=category,
                name=dish_name,
                slug=dish_slug,
                description=description,
                price=price,
                tags=tags,
                allergens=allergens,
                position=Dish.objects.filter(category=category).count(),
            )
            created_dishes += 1

        return Response({
            "created_categories": created_categories,
            "created_dishes": created_dishes,
            "skipped": skipped,
            "errors": errors[:20],  # cap at 20 to avoid huge payloads
        })


class ApplyTemplateView(APIView):
    """GET  /api/owner/apply-template/ — list the available starter templates.
       POST /api/owner/apply-template/ — apply one (theme + optional sample menu).

    A template sets the tenant's theme (colours + menu presentation) and
    business_type, and optionally seeds a ready-to-edit sample menu. Sample
    categories/dishes are matched by name, so re-applying never duplicates.
    Body: { "template": <key>, "with_sample_content"?: bool (default true) }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        from .menu_templates import template_summaries
        return Response({"templates": template_summaries()})

    def post(self, request, *args, **kwargs):
        if not _can_edit_menu(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from decimal import Decimal as _Dec
        from django.db import transaction as _txn
        from .menu_templates import TEMPLATES

        key = str(request.data.get("template") or "").strip().lower()
        tpl = TEMPLATES.get(key)
        if not tpl:
            return Response(
                {"detail": "Unknown template.", "code": "unknown_template"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with_content = request.data.get("with_sample_content", True)
        if isinstance(with_content, str):
            with_content = with_content.strip().lower() in ("1", "true", "yes")
        else:
            with_content = bool(with_content)

        tenant = getattr(request, "tenant", None)
        theme = tpl["theme"]

        created_categories = 0
        created_dishes = 0
        with _txn.atomic():
            # 1. Apply the theme + business_type to the tenant profile.
            profile = Profile.objects.filter(tenant=tenant).first() if tenant else None
            if profile is not None:
                profile.primary_color = theme["primary_color"]
                profile.secondary_color = theme["secondary_color"]
                profile.menu_theme = theme["menu_theme"]
                profile.menu_card_layout = theme["menu_card_layout"]
                profile.business_type = tpl["business_type"]
                # NOTE: Profile has no updated_at field — listing one here makes
                # Django's save() raise ValueError and 500 the whole apply.
                profile.save(update_fields=[
                    "primary_color", "secondary_color", "menu_theme",
                    "menu_card_layout", "business_type",
                ])
                # business_type is listing-relevant (serialized in the public
                # directory/marketplace + a member of LISTING_RELEVANT_FIELDS) and this
                # owner-reachable write bypasses ProfileView's bust, so refresh the
                # GLOBAL public-list cache — otherwise the listing card's category stays
                # stale for the 90s TTL. Best-effort + lazy import (avoids menu->accounts
                # import cycle at module load).
                try:
                    from accounts.views import _bust_public_list_cache
                    _bust_public_list_cache()
                except Exception:
                    pass

            # 2. Optionally seed the sample menu (idempotent by name).
            if with_content:
                default_super_cat = SuperCategory.objects.order_by("position", "id").first()
                if default_super_cat is None:
                    default_super_cat = SuperCategory.objects.create(
                        name=tpl.get("super_category", "Menu"),
                        slug=_make_unique_slug(tpl.get("super_category", "menu"), SuperCategory),
                        position=0,
                    )
                for cat in tpl["categories"]:
                    category = Category.objects.filter(name__iexact=cat["name"]).first()
                    if category is None:
                        category = Category.objects.create(
                            super_category=default_super_cat,
                            name=cat["name"],
                            slug=_make_unique_slug(cat["name"], Category),
                            position=Category.objects.count(),
                        )
                        created_categories += 1
                    for d in cat["dishes"]:
                        if Dish.objects.filter(category=category, name__iexact=d["name"]).exists():
                            continue
                        try:
                            price = _Dec(str(d["price"])).quantize(_Dec("0.01"))
                        except Exception:
                            continue
                        Dish.objects.create(
                            category=category,
                            name=d["name"],
                            slug=_make_unique_slug(d["name"], Dish),
                            description=d.get("description", ""),
                            price=price,
                            position=Dish.objects.filter(category=category).count(),
                        )
                        created_dishes += 1

        return Response({
            "applied": key,
            "business_type": tpl["business_type"],
            "theme": theme,
            "created_categories": created_categories,
            "created_dishes": created_dishes,
        })


def _make_unique_slug(name: str, model_class, max_length: int = 200) -> str:
    """Generate a slug from name that doesn't collide with existing rows."""
    from django.utils.text import slugify as _slugify
    base = _slugify(name)[:max_length - 8] or "item"
    slug = base
    suffix = 1
    while model_class.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


# ─────────────────────────────────────────────────────────────────────────────
# Currency rates — public endpoint
# ─────────────────────────────────────────────────────────────────────────────

class CurrencyRateListView(APIView):
    """
    GET /api/currency-rates/

    Returns all active CurrencyRate rows so the frontend can do client-side
    price conversion from MAD to the customer's preferred display currency.
    No authentication required.
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        rates = CurrencyRate.objects.filter(is_active=True).values(
            "code", "name", "symbol", "mad_per_unit"
        )
        data = [
            {
                "code": r["code"],
                "name": r["name"],
                "symbol": r["symbol"],
                "mad_per_unit": float(r["mad_per_unit"]),
            }
            for r in rates
        ]
        return Response(data)


# ── Owner wallet top-up ────────────────────────────────────────────────────────

class OwnerWalletResolveTokenView(APIView):
    """POST /api/owner/wallet/resolve-token/ — resolve a customer's wallet pay-code (QR).

    Body: { "token": "<signed token from the customer's QR>" }

    Validates the short-lived token and returns the customer IF they have ordered at
    this restaurant — the same gate as the manual top-up. Lets the owner scan a QR to
    instantly pull up a customer for a fast top-up instead of searching by phone.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Waiter capability: resolving a pay code is part of taking payment.
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from django.core import signing
        from accounts.models import Customer
        from accounts.views import _WALLET_PAY_SALT, _WALLET_PAY_TTL

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        token = str(request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required.", "code": "missing_token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = signing.loads(token, salt=_WALLET_PAY_SALT, max_age=_WALLET_PAY_TTL)
        except signing.SignatureExpired:
            return Response({"detail": "This pay code has expired. Ask the customer to refresh it.", "code": "expired"}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({"detail": "Invalid pay code.", "code": "invalid"}, status=status.HTTP_400_BAD_REQUEST)

        customer_id = payload.get("cid")
        # Same gate as manual top-up: only customers who have ordered at this restaurant.
        # We are already in this restaurant's schema, so Order.objects is scoped to it
        # (Order has no tenant FK — it's isolated by schema).
        if not Order.objects.filter(customer_id=customer_id).exists():
            return Response({"detail": "Customer has no orders at this restaurant.", "code": "no_orders"}, status=status.HTTP_404_NOT_FOUND)
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "customer_id": customer.id,
            "name": customer.name or "",
            "phone": customer.phone or "",
            "wallet_balance": str(customer.wallet_balance),
        })


def _settle_order_if_wallet_covers(order_number):
    """Flip an order to PAID once its accumulated wallet payments cover the total.
    This is what lets paying a (dine-in) tab from the wallet actually close the
    bill. Best-effort — the wallet ledger is the source of truth regardless.
    """
    if not order_number:
        return
    try:
        o = Order.objects.filter(order_number=order_number).only(
            "id", "total", "wallet_amount_paid", "payment_status", "paid_at"
        ).first()
        if (
            o is not None
            and o.payment_status != Order.PaymentStatus.PAID
            and o.total > Decimal("0")
            and o.wallet_amount_paid >= o.total
        ):
            o.mark_paid()  # sets payment_status=PAID + paid_at + saves
            _broadcast_order_change(o)
    except Exception:
        pass


class CustomerOrderPayWalletView(APIView):
    """POST /api/orders/<order_number>/pay-wallet/

    The signed-in customer settles their OWN unpaid order from their wallet
    balance — e.g. paying a dine-in tab at the end. Their session both identifies
    and authorises them (the tap is consent, so no approval threshold). Idempotent
    on the wallet debit, so a double-tap never double-charges.
    """

    permission_classes = [AllowAny]  # gated below: session customer must own the order

    def post(self, request, order_number, *args, **kwargs):
        order_number = (order_number or "").strip().upper()
        order = Order.objects.filter(order_number=order_number).first()
        if order is None:
            return Response({"detail": "Order not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)

        session_customer_id = request.session.get("customer_id")
        try:
            owns = bool(session_customer_id) and bool(order.customer_id) and int(session_customer_id) == int(order.customer_id)
        except (TypeError, ValueError):
            owns = False
        if not owns:
            return Response({"detail": "Sign in to pay this order.", "code": "not_owner"}, status=status.HTTP_403_FORBIDDEN)

        if order.payment_status == Order.PaymentStatus.PAID:
            return Response({"status": "paid", "payment_status": order.payment_status})

        outstanding = (order.total or Decimal("0")) - (order.wallet_amount_paid or Decimal("0"))
        if outstanding <= Decimal("0"):
            order.mark_paid()
            return Response({"status": "paid", "payment_status": order.payment_status})

        tenant = getattr(request, "tenant", None)
        from accounts.wallet_service import debit_wallet, InsufficientFunds, WalletError
        from accounts.models import Customer as _Cust
        from django.db import connection as _ws_conn
        # OPS-5g: WalletTransaction lives in the PUBLIC schema, so idempotency_key is a
        # GLOBAL namespace across tenants. order_number is only tenant-schema-unique, so a
        # bare f"order-pay-{order_number}" could collide with another tenant's order of the
        # same number — the OPS-5f customer-match guard would PASS (same customer can hold
        # orders in two tenants) and silently replay, marking THIS order PAID with no money
        # moved. Namespace the key with the tenant schema. The order already-PAID guard
        # above (and the customer's wallet ledger) is the durable backstop against double
        # payment; the namespacing just stops the cross-tenant collision.
        _schema = _ws_conn.schema_name
        try:
            tx = debit_wallet(
                order.customer_id, outstanding,
                reference=order_number, tenant_id=(tenant.id if tenant else None),
                note="Order payment", idempotency_key=f"order-pay-{_schema}-{order_number}",
            )
        except InsufficientFunds:
            cust = _Cust.objects.filter(pk=order.customer_id).first()
            return Response(
                {"detail": "Insufficient wallet balance.", "code": "insufficient",
                 "balance": str(cust.wallet_balance) if cust else "0.00",
                 "outstanding": str(outstanding)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order.wallet_amount_paid = (order.wallet_amount_paid or Decimal("0")) + outstanding
        order.mark_paid(save=False)
        order.save(update_fields=["wallet_amount_paid", "payment_status", "paid_at", "updated_at"])
        _broadcast_order_change(order)

        return Response({
            "status": "paid",
            "payment_status": order.payment_status,
            "amount_paid": str(outstanding),
            "new_balance": str(getattr(tx, "balance_after", "")) if tx is not None else "",
        })


class OwnerWalletChargeView(APIView):
    """POST /api/owner/wallet/charge/ — charge a customer's wallet for an in-person order.

    Body: { token, amount, order_number?, note?, idempotency_key? }

    The pay-code token (from the customer's QR) is their consent; this debits their
    wallet for the amount (a payment to this restaurant). Fails with 402 if the balance
    is short, returning the balance so staff can collect the remainder in cash.
    Owner/staff only. No order-history gate — the customer is present and authorising.
    """

    permission_classes = [IsAuthenticated]
    # The pay-token (5-min QR) is the only consent for the instant sub-threshold path,
    # so a compromised/abusive waiter session could fire many small debits against a
    # present customer inside that window. This per-actor rate backstop caps the burst;
    # the per-(customer, pay-token) instant-charge cap below is the absolute velocity gate.
    throttle_classes = [OwnerWalletChargeThrottle]

    # Absolute cap on the instant (sub-threshold, token-only-consent) charge path,
    # scoped to a single (customer, pay-token) pair. Beyond either ceiling the charge
    # is refused and must go through the normal above-threshold approval flow (which
    # asks the customer for explicit per-amount consent). This bounds how much an
    # abused session can extract on one scan even while under the per-charge threshold.
    INSTANT_CHARGE_MAX_COUNT = 5          # at most N instant charges per scan
    INSTANT_CHARGE_MAX_TOTAL = Decimal("100.00")  # …and at most this cumulative total

    def post(self, request, *args, **kwargs):
        # Waiter capability: charging a customer's wallet is taking payment for an order.
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from decimal import Decimal as _Dec, InvalidOperation
        from django.core import signing
        from accounts.models import Customer
        from accounts.views import _WALLET_PAY_SALT, _WALLET_PAY_TTL
        from accounts.wallet_service import debit_wallet, InsufficientFunds, WalletError

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        token = str(request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "token is required.", "code": "missing_token"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payload = signing.loads(token, salt=_WALLET_PAY_SALT, max_age=_WALLET_PAY_TTL)
        except signing.SignatureExpired:
            return Response({"detail": "This pay code has expired. Ask the customer to refresh it.", "code": "expired"}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({"detail": "Invalid pay code.", "code": "invalid"}, status=status.HTTP_400_BAD_REQUEST)
        customer_id = payload.get("cid")

        try:
            amount = _Dec(str(request.data.get("amount"))).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= _Dec("0"):
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)

        order_number = str(request.data.get("order_number") or "").strip()[:100]
        note = str(request.data.get("note") or "").strip()[:200]
        _raw_idem = str(request.data.get("idempotency_key") or "").strip()[:120] or None
        # Server-namespace the externally-supplied key with the TENANT schema so one
        # tenant's body-supplied key can never collide with another tenant's (or with
        # server-generated keys like cashout:/orderpay:). Without this, a caller could
        # supply a key that aliases an existing transaction and trigger an idempotent
        # replay of money that wasn't theirs.
        idem = (
            f"ownercharge:{getattr(tenant, 'schema_name', '')}:{_raw_idem}"
            if _raw_idem else None
        )

        # Above the instant-charge threshold → the customer must approve before any money
        # moves. The QR scan identified them; this asks explicit consent for the amount.
        # (At or below the threshold, a scan is consent enough for a small tap.) The
        # threshold is admin-editable (PlatformConfig); fall back to the env setting.
        from django.conf import settings as _settings
        try:
            from accounts.models import PlatformConfig as _PC
            _threshold = _PC.get_solo().wallet_charge_approval_threshold
        except Exception:
            _threshold = _Dec(str(getattr(_settings, "WALLET_CHARGE_APPROVAL_THRESHOLD", "50") or "0"))
        if amount > _threshold:
            from accounts.models import WalletChargeRequest
            from django.utils import timezone as _tz
            from django.utils.crypto import get_random_string
            from datetime import timedelta as _td
            _ttl = int(getattr(_settings, "WALLET_CHARGE_REQUEST_TTL", 300))
            cr, _created = WalletChargeRequest.objects.get_or_create(
                idempotency_key=(idem or f"cr-{get_random_string(24)}"),
                defaults={
                    "customer_id": customer_id,
                    "tenant_id": tenant.id,
                    "restaurant_name": getattr(tenant, "name", "") or "",
                    "amount": amount,
                    "order_number": order_number,
                    "note": note,
                    "status": WalletChargeRequest.Status.PENDING,
                    "actor_user_id": getattr(request.user, "id", None),
                    "expires_at": _tz.now() + _td(seconds=_ttl),
                },
            )
            if _created:
                # Best-effort push nudge so the customer sees the approval prompt even if
                # their app is backgrounded. The in-app modal + polling is the fallback.
                try:
                    from accounts.push import push_charge_request
                    push_charge_request(customer_id, getattr(tenant, "name", "") or "", str(amount))
                except Exception:
                    pass
            return Response({
                "status": "pending",
                "request_id": cr.id,
                "customer_id": int(customer_id),
                "amount": str(amount),
                "expires_at": cr.expires_at.isoformat(),
            }, status=status.HTTP_202_ACCEPTED)

        # ── Instant (sub-threshold) path: absolute velocity / amount cap ───────────
        # The only consent here is the still-valid pay-token; a single scan must not be
        # turned into an unbounded stream of small debits. Cap both the COUNT of instant
        # charges and their CUMULATIVE total per (customer, pay-token). Past either
        # ceiling the waiter must use the above-threshold approval flow (explicit
        # per-amount customer consent). Keyed on a digest of the token so every charge
        # under the same scan shares one bucket; TTL = the pay-token window so the cap
        # resets naturally when the customer refreshes their QR.
        import hashlib as _hashlib
        from django.core.cache import cache as _cache
        _tok_digest = _hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
        _cap_key = f"ownercharge_instant:{int(customer_id)}:{_tok_digest}"
        _seen = _cache.get(_cap_key) or {"count": 0, "total": "0"}
        try:
            _prior_total = _Dec(str(_seen.get("total") or "0"))
            _prior_count = int(_seen.get("count") or 0)
        except (InvalidOperation, TypeError, ValueError):
            _prior_total, _prior_count = _Dec("0"), 0
        if (_prior_count + 1 > self.INSTANT_CHARGE_MAX_COUNT
                or _prior_total + amount > self.INSTANT_CHARGE_MAX_TOTAL):
            return Response(
                {"detail": "Instant-charge limit reached for this pay code. Ask the customer "
                           "to approve this charge.", "code": "instant_cap"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            tx = debit_wallet(
                customer_id, amount,
                reference=order_number, tenant_id=tenant.id, note=note, idempotency_key=idem,
            )
        except InsufficientFunds:
            cust = Customer.objects.filter(pk=customer_id).first()
            return Response(
                {"detail": "Insufficient wallet balance.", "code": "insufficient",
                 "balance": str(cust.wallet_balance) if cust else "0.00", "requested": str(amount)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Record the completed instant charge against the per-(customer, pay-token) cap.
        # Only successful debits count, so an InsufficientFunds 402 never burns a slot
        # (and an idempotent retry of the SAME idem key re-counts harmlessly — the cap
        # is a velocity ceiling, not an exact-charge ledger). TTL = pay-token window.
        try:
            _seen = _cache.get(_cap_key) or {"count": 0, "total": "0"}
            _new_total = (_Dec(str(_seen.get("total") or "0")) + amount).quantize(_Dec("0.01"))
            _new_count = int(_seen.get("count") or 0) + 1
            _cache.set(
                _cap_key,
                {"count": _new_count, "total": str(_new_total)},
                int(getattr(_settings, "WALLET_PAY_TTL", _WALLET_PAY_TTL) or _WALLET_PAY_TTL),
            )
        except Exception:
            pass  # cap accounting is best-effort; never fail a completed charge over it

        # If this charge settles a specific order, reflect it on the order's bill.
        if order_number:
            try:
                from django.db.models import F as _F
                Order.objects.filter(order_number=order_number).update(
                    wallet_amount_paid=_F("wallet_amount_paid") + amount
                )
                _settle_order_if_wallet_covers(order_number)
            except Exception:
                pass  # the payment is recorded regardless; bill update is best-effort

        return Response({
            "status": "charged",
            "customer_id": int(customer_id),
            "amount": str(amount),
            "new_balance": str(tx.balance_after),
        })


def _sync_charged_request_bills(tenant_id, order_numbers):
    """Apply approved-but-unsynced wallet charge requests to their tenant Order bills.

    A customer approves an above-threshold charge in the PUBLIC schema, which can't reach
    the tenant-schema Order. This runs in tenant context to keep the bill in sync. Each
    request is claimed atomically (flip bill_synced) before its amount is applied, so two
    concurrent callers (the owner's status poll and the order list) can never double-apply
    the same charge. Returns {order_number: amount_applied}.
    """
    from accounts.models import WalletChargeRequest as _WCR
    from django.db.models import F as _F
    applied = {}
    nums = [n for n in (order_numbers or []) if n]
    if not nums:
        return applied
    pending = list(_WCR.objects.filter(
        tenant_id=tenant_id, status=_WCR.Status.CHARGED, bill_synced=False, order_number__in=nums
    ).values_list("id", "order_number", "amount"))
    for cr_id, onum, amount in pending:
        # Atomic claim: only the caller that flips bill_synced False->True applies the bill.
        if not _WCR.objects.filter(pk=cr_id, bill_synced=False).update(bill_synced=True):
            continue
        try:
            Order.objects.filter(order_number=onum).update(
                wallet_amount_paid=_F("wallet_amount_paid") + amount
            )
            _settle_order_if_wallet_covers(onum)
            applied[onum] = applied.get(onum, Decimal("0")) + amount
        except Exception:
            pass  # best-effort; the payment is recorded in the wallet ledger regardless
    return applied


class OwnerWalletChargeRequestStatusView(APIView):
    """GET /api/owner/wallet/charge-request/<id>/ — poll a pending charge's outcome.

    The owner/staff poll this after creating an above-threshold charge request until the
    customer approves (charged), declines, or it expires. When it becomes charged and is
    tied to an order, this — running in the tenant schema — applies the bill update once
    (the customer's approval runs in the public schema and can't reach the tenant Order).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, request_id, *args, **kwargs):
        # Waiter capability: polling the outcome of a charge they initiated.
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from accounts.models import WalletChargeRequest, Customer
        from django.utils import timezone as _tz

        tenant = getattr(request, "tenant", None)
        cr = WalletChargeRequest.objects.filter(pk=request_id).first()
        if cr is None or (tenant is not None and cr.tenant_id != tenant.id):
            return Response({"detail": "Charge request not found."}, status=status.HTTP_404_NOT_FOUND)

        # Lazy-expire a stale pending request.
        if cr.status == WalletChargeRequest.Status.PENDING and cr.expires_at <= _tz.now():
            cr.status = WalletChargeRequest.Status.EXPIRED
            cr.resolved_at = _tz.now()
            cr.save(update_fields=["status", "resolved_at"])

        # Apply the bill update once now that we're in tenant context (claim-safe helper).
        if (cr.status == WalletChargeRequest.Status.CHARGED and cr.order_number
                and not cr.bill_synced):
            _sync_charged_request_bills(cr.tenant_id, [cr.order_number])
            cr.bill_synced = True  # reflect locally; helper already persisted it

        data = {"status": cr.status, "request_id": cr.id, "amount": str(cr.amount)}
        if cr.status == WalletChargeRequest.Status.CHARGED:
            cust = Customer.objects.filter(pk=cr.customer_id).first()
            data["new_balance"] = str(cust.wallet_balance) if cust else None
        return Response(data)


class OwnerWalletTopupView(APIView):
    """
    POST /api/owner/wallet/topup/
    Body: { "customer_id": 42, "amount": "10.00", "note": "Goodwill credit" }

    Top-up a customer's wallet from the restaurant's prepaid float.  Owner can only
    credit customers who have placed at least one order at their restaurant, and only
    up to the funded float — the transfer is blocked (402) if the float is too low.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        from decimal import Decimal as _Dec, InvalidOperation
        from accounts.models import Customer
        from accounts.wallet_service import (
            transfer_to_customer,
            InsufficientFunds,
            UnverifiedWallet,
            WalletError,
        )

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        customer_id = request.data.get("customer_id")
        if not customer_id:
            return Response({"detail": "customer_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Security: only allow topping up customers who have ordered at this restaurant.
        # Already in this restaurant's schema, so Order.objects is scoped to it (Order
        # has no tenant FK — schema isolation does the scoping).
        has_orders = Order.objects.filter(customer_id=customer_id).exists()
        if not has_orders:
            return Response(
                {"detail": "Customer has no orders at this restaurant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_amount = request.data.get("amount")
        try:
            amount = _Dec(str(raw_amount)).quantize(_Dec("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= _Dec("0"):
            return Response({"detail": "Amount must be positive."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note") or "Owner credit").strip()[:200]
        # OPS-5e: WalletTransaction/TenantFloatTransaction live in the PUBLIC schema
        # (accounts is a SHARED_APP), so idempotency_key is a GLOBAL namespace across
        # tenants. Server-namespace the body-supplied key with this tenant's schema —
        # like OwnerWalletCharge (ownercharge:) and AdminFundTenant (adminfund:) — so a
        # chosen value can't collide with another tenant's transfer (silent no-op +
        # cross-tenant balance leak on the idempotent-replay path).
        _raw_idem = str(request.data.get("idempotency_key") or "").strip()[:120]
        idempotency_key = (
            f"ownertopup:{getattr(tenant, 'schema_name', '')}:{_raw_idem}"
            if _raw_idem else None
        )

        try:
            float_tx, wallet_tx = transfer_to_customer(
                tenant.id,
                customer_id,
                amount,
                actor_user_id=getattr(request.user, "id", None),
                note=note,
                idempotency_key=idempotency_key,
            )
        except InsufficientFunds:
            tenant.refresh_from_db(fields=["float_balance"])
            return Response(
                {
                    "detail": "Insufficient restaurant float. Ask the platform to top up your float first.",
                    "float_balance": str(tenant.float_balance),
                    "requested": str(amount),
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except UnverifiedWallet:
            return Response(
                {"detail": "This customer hasn't verified their phone number yet, so they can't receive wallet credit.",
                 "code": "recipient_unverified"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)
        except WalletError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # On an idempotent replay the customer-side leg is looked up by key; fall back to
        # the customer's current balance if it isn't returned.
        if wallet_tx is not None:
            new_balance = str(wallet_tx.balance_after)
        else:
            new_balance = str(Customer.objects.get(pk=customer_id).wallet_balance)

        return Response({
            "customer_id": int(customer_id),
            "new_balance": new_balance,
            "amount": str(amount),
            "note": note,
            "float_balance": str(float_tx.balance_after),
        })


class OwnerWalletHistoryView(APIView):
    """
    GET /api/owner/wallet/history/<customer_id>/

    Returns the last 20 wallet transactions for a customer, scoped to
    customers who have placed at least one order at this restaurant.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        # Security: only expose history for customers who ordered at this restaurant.
        # Already scoped to this restaurant's schema (Order has no tenant FK).
        has_orders = Order.objects.filter(customer_id=customer_id).exists()
        if not has_orders:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        from accounts.models import Customer, WalletTransaction
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

        # Privacy: the wallet is shared across all restaurants on the platform, but an
        # owner must only see activity at THEIR restaurant — never a customer's spend or
        # top-ups elsewhere. Scope the history to this tenant (the balance is the total).
        txs = (
            WalletTransaction.objects
            .filter(customer=customer, tenant_id=tenant.id)
            .order_by("-created_at")[:20]
        )
        return Response({
            "customer_id": customer.id,
            "wallet_balance": str(customer.wallet_balance),
            "transactions": [
                {
                    "id": tx.id,
                    "type": tx.type,
                    "amount": str(tx.amount),
                    "note": tx.note,
                    "reference": tx.reference,
                    "created_at": tx.created_at.isoformat(),
                }
                for tx in txs
            ],
        })


class OwnerWalletFloatView(APIView):
    """
    GET /api/owner/wallet/float/

    Returns the restaurant's current distributable float balance plus the last 30
    float movements (platform fundings + client distributions). Lets the owner see
    how much they can still hand out and where it went.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        from accounts.models import TenantFloatTransaction

        txs = (
            TenantFloatTransaction.objects
            .filter(tenant_id=tenant.id)
            .select_related("customer")
            .order_by("-created_at")[:30]
        )
        return Response({
            "float_balance": str(tenant.float_balance),
            "transactions": [
                {
                    "id": tx.id,
                    "type": tx.type,
                    "amount": str(tx.amount),
                    "balance_after": (str(tx.balance_after) if tx.balance_after is not None else None),
                    "customer_id": tx.customer_id,
                    "customer_name": (tx.customer.name if tx.customer_id else ""),
                    "note": tx.note,
                    "reference": tx.reference,
                    "created_at": tx.created_at.isoformat(),
                }
                for tx in txs
            ],
        })


# ── Admin wallet list ──────────────────────────────────────────────────────────

class AdminWalletListView(APIView):
    """
    GET /api/admin/wallets/

    Returns customers who have a wallet balance or transaction history.
    Query params:
      search      — filter by name, phone, email
      min_balance — only show customers with balance >= this value (default: 0)
      page, page_size
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not (user and (user.is_superuser or getattr(user, "is_platform_admin", False))):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        from accounts.models import Customer
        from decimal import Decimal as _Dec

        search = (request.query_params.get("search") or "").strip()
        try:
            min_balance = _Dec(str(request.query_params.get("min_balance") or "0"))
        except Exception:
            min_balance = _Dec("0")

        qs = Customer.objects.filter(wallet_balance__gte=min_balance).order_by("-wallet_balance")

        if search:
            from django.db.models import Q
            # Customer holds its own name/email/phone (there is no linked User relation).
            _digits = "".join(c for c in search if c.isdigit())
            _phone_q = Q(phone_digits=_digits[-9:]) if len(_digits) >= 5 else Q(phone__icontains=search)
            qs = qs.filter(Q(name__icontains=search) | Q(email__icontains=search) | _phone_q)

        try:
            page = max(1, int(request.query_params.get("page") or 1))
            page_size = min(100, max(1, int(request.query_params.get("page_size") or 50)))
        except (ValueError, TypeError):
            page, page_size = 1, 50

        start = (page - 1) * page_size
        total = qs.count()
        customers = qs[start: start + page_size]

        data = []
        for c in customers:
            data.append({
                "id": c.id,
                "name": c.name or f"Customer #{c.id}",
                "email": c.email or "",
                "phone": c.phone or "",
                "wallet_balance": str(c.wallet_balance),
            })

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": data,
        })


# ── Owner campaign broadcasts ────────────────────────────────────────────────

_CAMPAIGN_DAILY_CAP = 2  # hard per-tenant per-day limit


def _campaign_day_window(tenant):
    """Return (day_start_utc, day_end_utc) for TODAY in the tenant's timezone.

    Mirrors the _tenant_yesterday helper in send_daily_summary but returns the
    CURRENT day, so the campaign cap counts campaigns already sent today.
    """
    from datetime import timezone as _tz
    try:
        from zoneinfo import ZoneInfo
        profile = getattr(tenant, "profile", None)
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = _tz.utc

    from datetime import datetime as _dt, timedelta as _td
    now_local = _dt.now(tz)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_local = day_start_local + _td(days=1)
    return day_start_local.astimezone(_tz.utc), day_end_local.astimezone(_tz.utc)


class OwnerCampaignView(APIView):
    """
    GET  /api/owner/campaigns/  — audience estimate, today's remaining cap, last 20 campaigns.
    POST /api/owner/campaigns/  — broadcast a campaign to opted-in past customers (push + email).

    Owner-only (same _is_tenant_owner gate as closure-date / commission-statement views).

    POST body: { "title": str(<=80), "message": str(<=200) }

    POST 201 response: campaign row fields.
    POST 409 codes:
      "campaign_cap"  — 2 campaigns already sent today.
      "no_audience"   — zero opted-in past customers reachable by EITHER push or email.
    POST 400: title/message length validation.

    Audience definition (strictly tenant-isolated) — B1 dual-channel:
      Distinct customer_ids with >= 1 Order in this tenant schema
      AND notify_promotions=True on the public Customer row
      AND reachable by push (>= 1 CustomerPushSubscription) OR email (non-empty Customer.email).

    Dispatch (B1): per audience customer, a push (accounts.tasks.campaign_push, if subscribed)
    AND/OR an email (if an email is on file). audience_count = the union reachable count.
    sent_count equals audience_count at enqueue time (fire-and-forget; delivery is not
    guaranteed — web push / SMTP may fail per-recipient silently).
    record_notification rows written per dispatch (channel push / email).
    """

    permission_classes = [IsAuthenticated]

    def _audience_ids(self):
        """Return a list of distinct customer_ids eligible for a PUSH campaign.

        Three set-intersection queries — no per-customer loop.
        Isolation: orderer_ids come ONLY from this tenant's Order rows.
        """
        from accounts.models import Customer, CustomerPushSubscription

        # Step 1: all distinct customer_ids that have >= 1 order in this tenant.
        # We are already inside the tenant schema (request cycle), so no context switch.
        all_orderer_ids = set(
            Order.objects.values_list("customer_id", flat=True)
            .distinct()
            .exclude(customer_id__isnull=True)
        )
        if not all_orderer_ids:
            return []

        # Step 2: filter to opted-in customers (public schema).
        with schema_context("public"):
            opted_in_ids = set(
                Customer.objects.filter(
                    id__in=all_orderer_ids,
                    notify_promotions=True,
                ).values_list("id", flat=True)
            )
            if not opted_in_ids:
                return []

            # Step 3: filter to customers with at least one push subscription.
            subscribed_ids = set(
                CustomerPushSubscription.objects.filter(
                    customer_id__in=opted_in_ids,
                ).values_list("customer_id", flat=True).distinct()
            )

        return list(subscribed_ids)

    def _email_audience(self):
        """Return ``{customer_id: email}`` for opted-in past customers with an
        email on file (B1 — the email delivery channel for campaigns).

        Same tenant-scoped, opted-in audience as ``_audience_ids`` but keyed by
        email reachability instead of a push subscription. Customers with BOTH a
        push subscription and an email appear in both audiences (dual-send).
        """
        from accounts.models import Customer

        all_orderer_ids = set(
            Order.objects.values_list("customer_id", flat=True)
            .distinct()
            .exclude(customer_id__isnull=True)
        )
        if not all_orderer_ids:
            return {}

        with schema_context("public"):
            return {
                cid: email
                for cid, email in Customer.objects.filter(
                    id__in=all_orderer_ids,
                    notify_promotions=True,
                    email_verified=True,
                ).exclude(email="").values_list("id", "email")
                if email
            }

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        tenant = request.tenant
        day_start, day_end = _campaign_day_window(tenant)
        today_count = Campaign.objects.filter(
            created_at__gte=day_start, created_at__lt=day_end,
        ).count()
        today_remaining = max(0, _CAMPAIGN_DAILY_CAP - today_count)

        # B1: the preview must match what POST actually sends — the UNION of push-
        # reachable + email-reachable opted-in customers (POST stores audience_count =
        # len(reachable_ids)). A push-only estimate undercounts email-only customers.
        audience_ids = self._audience_ids()
        audience_estimate = len(set(audience_ids) | set(self._email_audience().keys()))

        campaigns = list(Campaign.objects.order_by("-created_at")[:20])
        campaigns_data = [
            {
                "id": c.id,
                "title": c.title,
                "message": c.message,
                "created_by_user_id": c.created_by_user_id,
                "audience_count": c.audience_count,
                "sent_count": c.sent_count,
                "created_at": c.created_at.isoformat(),
            }
            for c in campaigns
        ]
        return Response({
            "audience_estimate": audience_estimate,
            "today_remaining": today_remaining,
            "campaigns": campaigns_data,
        })

    def post(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=status.HTTP_403_FORBIDDEN)

        # ── Validate inputs ───────────────────────────────────────────────────
        title = (request.data.get("title") or "").strip()
        message = (request.data.get("message") or "").strip()
        if not title or len(title) > 80:
            return Response(
                {"detail": "title is required and must be <= 80 characters.", "code": "invalid_title"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not message or len(message) > 200:
            return Response(
                {"detail": "message is required and must be <= 200 characters.", "code": "invalid_message"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Daily cap check (with cache mutex to close TOCTOU) ───────────────
        tenant = request.tenant
        _lock_key = f"campaign_lock:{getattr(tenant, 'schema_name', None) or tenant.id}"
        if not cache.add(_lock_key, 1, 10):
            # A concurrent request holds the mutex — this is a transient lock,
            # NOT the daily cap; the caller can simply retry in a moment.
            return Response(
                {
                    "detail": "Another announcement is being sent — try again in a moment.",
                    "code": "campaign_locked",
                },
                status=status.HTTP_409_CONFLICT,
            )
        try:
            day_start, day_end = _campaign_day_window(tenant)
            today_count = Campaign.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end,
            ).count()
            if today_count >= _CAMPAIGN_DAILY_CAP:
                return Response(
                    {
                        "detail": f"Daily campaign limit of {_CAMPAIGN_DAILY_CAP} reached. Try again tomorrow.",
                        "code": "campaign_cap",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # ── Audience (B1 — push OR email reachable) ───────────────────────
            audience_ids = self._audience_ids()           # push-subscribed
            email_audience = self._email_audience()        # {cid: email}
            reachable_ids = set(audience_ids) | set(email_audience.keys())
            if not reachable_ids:
                return Response(
                    {"detail": "No opted-in subscribers found among your past customers.", "code": "no_audience"},
                    status=status.HTTP_409_CONFLICT,
                )

            # ── Create campaign row ───────────────────────────────────────────
            # Count reflects total reach across both channels (a customer with
            # BOTH push and email is counted once).
            campaign = Campaign.objects.create(
                title=title,
                message=message,
                created_by_user_id=request.user.pk,
                audience_count=len(reachable_ids),
                sent_count=len(reachable_ids),  # fire-and-forget: equals audience_count at enqueue
            )
        finally:
            cache.delete(_lock_key)

        # ── Dispatch per audience customer (push + email; B1) ─────────────────
        # Both channels go through the same async enqueue path the campaign push
        # already used, so the request never blocks on SMTP. Push re-checks the
        # subscription/opt-out at send time; email re-checks the opt-out + reads
        # the address from the public Customer row at send time.
        tenant_name = getattr(tenant, "name", "") or getattr(tenant, "slug", "")
        tenant_slug = getattr(tenant, "slug", "")
        tenant_id = getattr(tenant, "id", None)
        push_url = f"/order/{tenant_slug}"
        from accounts.push import push_campaign_to_customer, email_campaign_to_customer
        for cid in audience_ids:
            push_campaign_to_customer(cid, tenant_name, title, message, push_url)
        for cid in email_audience:
            email_campaign_to_customer(cid, tenant_name, title, message, tenant_id)

        # ── Audit trail (one row per channel per campaign, not per customer) ──
        try:
            from accounts.notifications import record_notification
            record_notification(
                channel="push",
                event="campaign",
                status="sent",
                recipient=f"{len(audience_ids)} customers",
                detail=title,
                tenant_id=tenant_id,
            )
            record_notification(
                channel="email",
                event="campaign",
                status="sent",
                recipient=f"{len(email_audience)} customers",
                detail=title,
                tenant_id=tenant_id,
            )
        except Exception:
            pass

        return Response(
            {
                "id": campaign.id,
                "title": campaign.title,
                "message": campaign.message,
                "created_by_user_id": campaign.created_by_user_id,
                "audience_count": campaign.audience_count,
                "sent_count": campaign.sent_count,
                "created_at": campaign.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
