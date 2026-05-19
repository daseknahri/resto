from datetime import datetime, timedelta
from decimal import Decimal
import csv
import hashlib
from io import BytesIO, StringIO
import re
import threading
from urllib.parse import quote_plus
import zipfile

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, F
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

from tenancy.models import Profile

from .models import AnalyticsEvent, Category, Dish, DishOption, OptionGroup, Order, OrderItem, Promotion, Rating, SuperCategory, TableLink, WaitlistEntry
from .permissions import IsTenantEditorOrReadOnly
from .serializers import (
    CategorySerializer,
    DishOptionSerializer,
    DishSerializer,
    OptionGroupSerializer,
    SuperCategorySerializer,
    TableLinkSerializer,
)
from .throttles import AnalyticsEventThrottle, CheckoutIntentThrottle, OrderHandoffThrottle, PlaceOrderThrottle, StaffOrderListThrottle


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


def _schedule_open(profile) -> bool | None:
    """Check *profile.business_hours_schedule* against the current UTC time.

    Returns:
      True  — schedule exists and says the restaurant is open right now.
      False — schedule exists and says the restaurant is currently closed.
      None  — no schedule configured (or no enabled days) — caller falls back
               to the manual ``profile.is_open`` boolean.

    NOTE: Comparison is done in **UTC**.  A per-restaurant ``timezone`` field
    would make this more accurate; add that when rolling out timezone support.
    """
    schedule = getattr(profile, "business_hours_schedule", None)
    if not schedule or not isinstance(schedule, dict):
        return None

    # Check whether any day has been enabled; if none, treat as unconfigured.
    if not any(
        isinstance(v, dict) and v.get("enabled", False)
        for v in schedule.values()
    ):
        return None

    now_utc = datetime.utcnow()
    day_key = _WEEKDAY_TO_KEY.get(now_utc.weekday())
    entry = schedule.get(day_key)

    if not entry or not isinstance(entry, dict):
        return False  # today not represented → closed today

    if not entry.get("enabled", False):
        return False

    open_str = (entry.get("open") or "").strip()
    close_str = (entry.get("close") or "").strip()
    if not open_str or not close_str:
        return False

    current_hhmm = now_utc.strftime("%H:%M")
    return open_str <= current_hhmm < close_str


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
        if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
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

        # Serve from cache when available (public requests only)
        key = self._menu_list_cache_key()
        if key is not None:
            hit = cache.get(key)
            if hit is not None:
                return Response(hit)

        response = super().list(request, *args, **kwargs)
        if key is not None and response.status_code == 200:
            cache.set(key, response.data, timeout=_MENU_CACHE_TTL)
        return response

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
            .prefetch_related("dishes__options", "dishes__option_groups__options")
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
                super_category__is_published=True,
                super_category__is_temporarily_disabled=False,
            )
        return qs.order_by("super_category__position", "position", "name")

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return super().get_permissions()


class DishViewSet(PublishAccessMixin, viewsets.ModelViewSet):
    serializer_class = DishSerializer
    permission_classes = [IsTenantEditorOrReadOnly]

    def get_queryset(self):
        qs = Dish.objects.select_related("category", "category__super_category").prefetch_related("options", "option_groups__options").all()
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
        return ctx

    def perform_create(self, serializer):
        """Enforce per-plan dish limit before saving."""
        tenant = getattr(self.request, "tenant", None)
        if tenant is not None:
            try:
                from django_tenants.utils import get_public_schema_name, schema_context
                from tenancy.models import Plan
                with schema_context(get_public_schema_name()):
                    plan = Plan.objects.filter(
                        tenants__id=tenant.id
                    ).values_list("max_dishes", flat=True).first()
                max_dishes = plan if plan is not None else 0
                if max_dishes and max_dishes > 0:
                    current_count = Dish.objects.count()
                    if current_count >= max_dishes:
                        from rest_framework.exceptions import ValidationError
                        raise ValidationError(
                            {
                                "detail": f"Your plan allows a maximum of {max_dishes} dishes. "
                                          f"You have {current_count}. Upgrade to add more.",
                                "code": "dish_limit_reached",
                                "limit": max_dishes,
                                "current": current_count,
                            }
                        )
            except Exception as exc:
                if getattr(exc, "detail", None):
                    raise
        serializer.save()


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


class TableLinkViewSet(viewsets.ModelViewSet):
    serializer_class = TableLinkSerializer
    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def get_queryset(self):
        return TableLink.objects.all().order_by("position", "label", "id")

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
                csv_writer.writerow([table.label, table.slug, short_url, full_url, "true" if table.is_active else "false"])
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


class AnalyticsSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def _can_view(self, request, tenant) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
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
        choices=("pickup", "delivery"),
        required=False,
        allow_blank=True,
    )
    customer_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    delivery_address = serializers.CharField(max_length=180, required=False, allow_blank=True)
    delivery_location_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    delivery_lat = serializers.FloatField(required=False, allow_null=True)
    delivery_lng = serializers.FloatField(required=False, allow_null=True)

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
        if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
            return True
        if getattr(user, "tenant_id", None) != tenant.id:
            return False
        return user.role in {user.Roles.TENANT_OWNER, user.Roles.TENANT_STAFF}

    def _fetch_dishes(self, slugs, can_preview):
        qs = Dish.objects.filter(slug__in=slugs).select_related("category")
        if not can_preview:
            qs = qs.filter(is_published=True, is_available=True, category__is_published=True)
        return {dish.slug: dish for dish in qs}

    def _fetch_options(self, option_ids, can_preview):
        if not option_ids:
            return {}
        qs = DishOption.objects.filter(id__in=option_ids).select_related("dish", "dish__category")
        if not can_preview:
            qs = qs.filter(dish__is_published=True, dish__category__is_published=True)
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
                        "detail": "Some selected options are unavailable for this dish.",
                        "code": "invalid_options",
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
                        "detail": "Some selected options are unavailable for this dish.",
                        "code": "invalid_options",
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


def _is_promo_active_now(promo) -> bool:
    """Return True if a Promotion is currently active (schedule + date boundaries)."""
    from datetime import datetime as _dt, date as _date
    _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    today = _date.today()
    if promo.active_from and today < promo.active_from:
        return False
    if promo.active_until and today > promo.active_until:
        return False
    allowed_days = promo.days or []
    if allowed_days:
        if _WDAY[_dt.utcnow().weekday()] not in allowed_days:
            return False
    ts = (promo.time_start or "").strip()
    te = (promo.time_end or "").strip()
    if ts and te:
        now_hhmm = _dt.utcnow().strftime("%H:%M")
        if not (ts <= now_hhmm < te):
            return False
    return True


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


def _notify_restaurant_new_order(order, tenant_name: str, whatsapp_phone: str) -> None:
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

    except Exception as exc:
        # Never fail the order — just log the issue
        _log = _logging.getLogger(__name__)
        _log.warning("Could not send new-order WhatsApp notification: %s", exc)


class PlaceOrderView(APIView):
    """POST /api/place-order/ — customer submits an in-app order."""
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
            user.is_superuser or user.is_staff or
            getattr(user, "is_platform_admin", False) or
            (getattr(user, "tenant_id", None) == tenant.id)
        ))

        if profile.is_menu_temporarily_disabled and not can_preview:
            return Response({"detail": "Menu is temporarily unavailable.", "code": "menu_temporarily_disabled"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not profile.is_menu_published and not can_preview:
            return Response({"detail": "Menu is not published yet.", "code": "menu_unpublished"}, status=status.HTTP_403_FORBIDDEN)
        if not can_preview and not _is_restaurant_currently_open(profile):
            return Response(
                {"detail": "Restaurant is currently closed.", "code": "restaurant_closed"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = OrderHandoffSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        items_input = validated["items"]

        slugs = [i["slug"] for i in items_input]
        all_option_ids = [oid for i in items_input for oid in i.get("option_ids", [])]

        dishes_map = {d.slug: d for d in Dish.objects.filter(
            slug__in=slugs, is_published=True, is_available=True, category__is_published=True
        ).select_related("category")}

        missing = [s for s in slugs if s not in dishes_map]
        if missing:
            return Response({"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing}, status=status.HTTP_400_BAD_REQUEST)

        options_map = {}
        if all_option_ids:
            options_map = {o.id: o for o in DishOption.objects.filter(id__in=all_option_ids)}

        # Build order items and compute total
        order_items_data = []
        _food_subtotal = Decimal("0")
        currency = "USD"

        for item_input in items_input:
            dish = dishes_map[item_input["slug"]]
            currency = dish.currency or "USD"
            unit_price = Decimal(str(dish.price))

            option_snapshots = []
            for oid in item_input.get("option_ids", []):
                opt = options_map.get(oid)
                if opt:
                    unit_price += Decimal(str(opt.price_delta))
                    option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})

            qty = item_input["qty"]
            subtotal = unit_price * qty
            _food_subtotal += subtotal
            order_items_data.append({
                "dish_slug": dish.slug,
                "dish_name": dish.name,
                "unit_price": unit_price,
                "qty": qty,
                "note": item_input.get("note", ""),
                "options": option_snapshots,
                "subtotal": subtotal,
            })

        # Collect dishes that track stock so we can decrement inside the transaction
        _stock_updates = []  # list of (dish_pk, ordered_qty)
        _pk_to_slug = {}
        for _item_d in order_items_data:
            _d = dishes_map[_item_d["dish_slug"]]
            _pk_to_slug[_d.pk] = _d.slug
            if _d.stock_qty is not None:
                _stock_updates.append((_d.pk, _item_d["qty"]))

        table_slug = (validated.get("table_slug") or "").strip()
        fulfillment_type = (validated.get("fulfillment_type") or "")
        table_label = (validated.get("table_label") or "").strip()
        if table_slug:
            fulfillment_type = Order.FulfillmentType.TABLE
            resolved_table = TableLink.objects.filter(slug=table_slug, is_active=True).first()
            if resolved_table is None:
                return Response(
                    {"detail": "Table link is unavailable.", "code": "table_unavailable"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Use DB label as authoritative source; fall back to client-supplied label
            table_label = resolved_table.label or table_label

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

        # Apply delivery fee for delivery orders
        _delivery_fee = Decimal("0")
        if fulfillment_type == Order.FulfillmentType.DELIVERY:
            try:
                _delivery_fee = Decimal(str(profile.delivery_fee or "0"))
            except Exception:
                _delivery_fee = Decimal("0")

        # Apply best currently-active promotion (highest discount wins)
        _best_promo = None
        _promo_discount = Decimal("0")
        for _promo in Promotion.objects.filter(is_active=True):
            if _promo.max_uses is not None and _promo.use_count >= _promo.max_uses:
                continue
            if Decimal(str(_promo.min_order_amount or "0")) > _food_subtotal:
                continue
            if not _is_promo_active_now(_promo):
                continue
            _d = _compute_promo_discount(_promo, _food_subtotal, _delivery_fee)
            if _d > _promo_discount:
                _promo_discount = _d
                _best_promo = _promo

        total = max(Decimal("0"), _food_subtotal + _delivery_fee - _promo_discount)

        # Wallet payment — customer may opt in to paying with their credits balance
        _use_wallet = bool(request.data.get("use_wallet")) and _linked_customer is not None
        _wallet_deduction = Decimal("0")
        if _use_wallet:
            _available = Decimal(str(_linked_customer.wallet_balance or "0"))
            _wallet_deduction = min(_available, total)
            if _wallet_deduction <= Decimal("0"):
                _use_wallet = False
                _wallet_deduction = Decimal("0")

        class _OutOfStock(Exception):
            """Raised inside the atomic block when a dish's stock is exhausted."""
            def __init__(self, slug):
                self.slug = slug

        try:
            with transaction.atomic():
                # --- Stock check + decrement (before creating the order so a failed
                #     stock check never leaves a dangling order row) ---
                if _stock_updates:
                    _locked_dishes = {
                        d.pk: d
                        for d in Dish.objects.select_for_update().filter(
                            pk__in=[pk for pk, _ in _stock_updates]
                        )
                    }
                    # Validate sufficient stock for every item in this order
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked_dishes.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered_qty:
                            raise _OutOfStock(_pk_to_slug.get(_dish_pk, ""))
                    # Atomically decrement; mark sold-out when stock reaches zero
                    for _dish_pk, _ordered_qty in _stock_updates:
                        _ld = _locked_dishes.get(_dish_pk)
                        if _ld and _ld.stock_qty is not None:
                            _new_qty = max(0, _ld.stock_qty - _ordered_qty)
                            if _new_qty == 0:
                                Dish.objects.filter(pk=_dish_pk).update(
                                    stock_qty=0, is_available=False
                                )
                            else:
                                Dish.objects.filter(pk=_dish_pk).update(stock_qty=_new_qty)

                order_number = _generate_order_number()
                order = Order.objects.create(
                    order_number=order_number,
                    status=Order.Status.PENDING,
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
                    total=total,
                    delivery_fee=_delivery_fee,
                    currency=currency,
                    promotion_discount=_promo_discount,
                    applied_promotion_name=_best_promo.name if _best_promo else "",
                )
                for item_data in order_items_data:
                    OrderItem.objects.create(order=order, **item_data)

                # Increment promo use_count atomically
                if _best_promo is not None:
                    Promotion.objects.filter(pk=_best_promo.pk).update(
                        use_count=models.F("use_count") + 1
                    )

                # Deduct wallet balance (select_for_update prevents race conditions)
                if _use_wallet and _wallet_deduction > Decimal("0"):
                    from accounts.models import Customer as _CustM, WalletTransaction as _WTM
                    _cust_locked = _CustM.objects.select_for_update().get(pk=_linked_customer.pk)
                    # Re-check available balance under lock
                    _actual = min(Decimal(str(_cust_locked.wallet_balance or "0")), _wallet_deduction)
                    if _actual > Decimal("0"):
                        _cust_locked.wallet_balance = _cust_locked.wallet_balance - _actual
                        _cust_locked.save(update_fields=["wallet_balance", "updated_at"])
                        _WTM.objects.create(
                            customer=_cust_locked,
                            type=_WTM.Type.PAYMENT,
                            amount=_actual,
                            reference=order.order_number,
                            tenant_id=tenant.id,
                        )
                        order.wallet_amount_paid = _actual
                        order.save(update_fields=["wallet_amount_paid"])
        except _OutOfStock as _e:
            return Response(
                {"detail": "Item sold out.", "code": "items_unavailable", "slugs": [_e.slug]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            # Rare TOCTOU race: two requests generated the same order number.
            # Return 503 so the client can retry; a fresh number will be picked.
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

        # Send WhatsApp notification to the restaurant (truly non-blocking daemon thread).
        # The order is already committed — a slow/failed Twilio call must never delay
        # the customer-facing 201 response.
        _wa_number = (getattr(profile, "whatsapp", "") or getattr(profile, "phone", "") or "").strip()
        if _wa_number:
            threading.Thread(
                target=_notify_restaurant_new_order,
                args=(order,),
                kwargs={"tenant_name": getattr(tenant, "name", ""), "whatsapp_phone": _wa_number},
                daemon=True,
            ).start()

        # Send Web Push notification to subscribed owner/staff (daemon thread).
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

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "estimated_ready_minutes": order.estimated_ready_minutes,
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
            }

        # Pull the receipt message from the tenant profile (safe fallback to "").
        receipt_message = ""
        try:
            receipt_message = getattr(request.tenant.profile, "receipt_message", "") or ""
        except Exception:
            pass

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "table_label": order.table_label,
            "customer_name": order.customer_name,
            # NOTE: customer_phone is intentionally omitted — this endpoint is
            # AllowAny so exposing phone numbers would let anyone enumerate PII
            # by guessing order numbers (ORD-XXXXXX ≈ 16M space).
            "delivery_address": order.delivery_address,
            "total": str(order.total),
            "delivery_fee": str(order.delivery_fee),
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "items_count": sum(i["qty"] for i in items),
            "items": items,
            "created_at": order.created_at.isoformat(),
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
            # Rating state — frontend shows 1–5 star prompt when status=completed and has_rating=false
            "has_rating": existing_rating is not None,
            "rating": rating_data,
            # Thank-you message written by the restaurant owner (shown for confirmed/ready/completed).
            "receipt_message": receipt_message,
        })



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
            .filter(customer_phone__icontains=digits[-9:], created_at__gte=since)
            .prefetch_related("items")
            .order_by("-created_at")[:20]
        )

        results = []
        for order in orders:
            results.append({
                "order_number": order.order_number,
                "status": order.status,
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
    try:
        customer_email = order.customer.email if order.customer else None
        if not customer_email:
            return

        status_labels = {
            Order.Status.CONFIRMED: "confirmed",
            Order.Status.PREPARING: "being prepared",
            Order.Status.READY: "ready",
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
                lines.append("Your order is on its way!")
            elif order.fulfillment_type == Order.FulfillmentType.PICKUP:
                lines.append("Your order is ready for pickup.")
            else:
                lines.append("Your order is ready.")

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
    except Exception:  # noqa: BLE001
        pass


def _can_edit_tenant_order(request) -> bool:
    user = getattr(request, "user", None)
    tenant = getattr(request, "tenant", None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
        return True
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    from accounts.models import User
    return user.role in {User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF}


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
    ]

    def get(self, request):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

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

        orders = []
        for order in qs[:100]:
            orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "fulfillment_type": order.fulfillment_type,
                "table_label": order.table_label,
                "customer_name": order.customer_name,
                "customer_note": order.customer_note,
                "owner_note": order.owner_note,
                "estimated_ready_minutes": order.estimated_ready_minutes,
                "total": str(order.total),
                "delivery_fee": str(order.delivery_fee),
                "currency": order.currency,
                "items_count": sum(i.qty for i in order.items.all()),
                "items": [
                    {
                        "dish_name": i.dish_name,
                        "qty": i.qty,
                        "options": i.options,
                        "note": i.note,
                    }
                    for i in order.items.all()
                ],
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            })

        return Response({"results": orders, "count": len(orders)})


class StaffShiftSummaryView(APIView):
    """GET /api/staff/shift-summary/ — end-of-shift stats for the waiter view.

    Query params:
      - since: ISO-8601 datetime marking shift start. Defaults to 8 hours ago.

    Returns:
      orders_handled   — count of orders that reached 'completed' within the window
      total_revenue    — sum of their totals (Decimal string)
      currency         — currency code (from first order, or empty)
      average_prep_time_minutes — mean seconds from created_at → status_updated_at (null if none)
      since            — ISO-8601 of the window start actually used
      period_hours     — float hours covered
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

        qs = Order.objects.filter(
            status=Order.Status.COMPLETED,
            status_updated_at__gte=since_dt,
        )

        from django.db.models import Avg, Count, Sum
        agg = qs.aggregate(
            total_count=Count("id"),
            total_revenue=Sum("total"),
        )

        orders_handled = agg["total_count"] or 0
        total_revenue = agg["total_revenue"] or Decimal("0.00")

        # Average prep time: mean of (status_updated_at - created_at) in minutes
        avg_prep_minutes = None
        if orders_handled > 0:
            total_seconds = 0
            count_with_both = 0
            for o in qs.only("created_at", "status_updated_at"):
                if o.status_updated_at and o.created_at:
                    delta = (o.status_updated_at - o.created_at).total_seconds()
                    if delta >= 0:
                        total_seconds += delta
                        count_with_both += 1
            if count_with_both > 0:
                avg_prep_minutes = round(total_seconds / count_with_both / 60, 1)

        currency = ""
        first = qs.only("currency").first()
        if first:
            currency = first.currency or ""

        now = timezone.now()
        period_hours = round((now - since_dt).total_seconds() / 3600, 1)

        return Response({
            "orders_handled": orders_handled,
            "total_revenue": str(total_revenue),
            "currency": currency,
            "average_prep_time_minutes": avg_prep_minutes,
            "since": since_dt.isoformat(),
            "period_hours": period_hours,
        })


class OwnerOrderListView(APIView):
    """GET /api/owner/orders/ — owner lists all orders, optionally filtered by status."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get("status", "").strip().lower()
        valid_statuses = {s.value for s in Order.Status}

        qs = Order.objects.select_related("customer").prefetch_related("items").order_by("-created_at")
        if status_filter and status_filter in valid_statuses:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        all_orders = list(qs[:200])

        # ── Batch-load customer trust scores ─────────────────────────────────
        from accounts.models import CustomerRating as _CR
        from django.db.models import Avg as _Avg, Count as _Count2
        tenant = getattr(request, "tenant", None)
        tenant_id = tenant.id if tenant else None

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
                        "restaurant_driver_rating": _dj.restaurant_driver_rating,
                        "restaurant_driver_note": _dj.restaurant_driver_note,
                    }

        orders = []
        for order in all_orders:
            orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "fulfillment_type": order.fulfillment_type,
                "table_label": order.table_label,
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
                "currency": order.currency,
                "owner_note": order.owner_note,
                "estimated_ready_minutes": order.estimated_ready_minutes,
                "items_count": sum(i.qty for i in order.items.all()),
                "items": [
                    {
                        "dish_name": i.dish_name,
                        "dish_slug": i.dish_slug,
                        "qty": i.qty,
                        "unit_price": str(i.unit_price),
                        "subtotal": str(i.subtotal),
                        "options": i.options,
                        "note": i.note,
                    }
                    for i in order.items.all()
                ],
                "created_at": order.created_at.isoformat(),
                "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
                # Platform-level customer trust data (public schema, cross-tenant)
                "customer_id": order.customer_id,
                "customer_trust": trust_map.get(order.customer_id) if order.customer_id else None,
                "my_customer_rating": my_rating_map.get(order.order_number),
                # Order source, commission & promotion
                "source": order.source,
                "commission_amount": str(order.commission_amount),
                "promotion_discount": str(order.promotion_discount),
                "applied_promotion_name": order.applied_promotion_name,
                # Delivery job (marketplace orders with active delivery)
                "delivery_job": delivery_job_map.get(order.order_number),
            })

        return Response({"results": orders, "count": len(orders), "total": total, "has_more": total > len(orders)})


class OwnerOrderDetailView(APIView):
    """GET /api/owner/orders/<id>/ — single order detail."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").prefetch_related("items").filter(id=order_id).first()
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
            "wallet_amount_paid": str(order.wallet_amount_paid),
            "currency": order.currency,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
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
        })


class OwnerCustomerRatingView(APIView):
    """
    POST /api/owner/orders/<order_id>/customer-rating/

    Owner rates a customer's trustworthiness after a completed order.
    The rating is stored in the public schema (shared across tenants) and is
    never shown directly to customers — it contributes to an aggregate trust
    score visible to restaurants when the same customer orders again.

    Request body:
        { "score": 1–5, "note": "optional text" }

    Responses:
        200 OK — rating saved or updated; body: {score, note, avg_score, rating_count}
        400 Bad Request — invalid score or order has no linked customer
        403 Forbidden — caller is not a tenant editor
        404 Not Found — unknown order_id
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").filter(id=order_id).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

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
        "created_at": p.created_at.isoformat(),
    }


class OwnerPromotionListCreateView(APIView):
    """GET /api/owner/promotions/ — list promotions.
       POST /api/owner/promotions/ — create a promotion."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        promos = Promotion.objects.all()
        return Response([_serialize_promotion(p) for p in promos])

    def post(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
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
        )
        return Response(_serialize_promotion(promo), status=status.HTTP_201_CREATED)


class OwnerPromotionDetailView(APIView):
    """GET /api/owner/promotions/<id>/ — retrieve.
       PATCH /api/owner/promotions/<id>/ — update.
       DELETE /api/owner/promotions/<id>/ — delete."""

    permission_classes = [IsAuthenticated]

    def _get_promo(self, request, promo_id):
        if not _can_edit_tenant_order(request):
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
        p.save()
        return Response(_serialize_promotion(p))

    def delete(self, request, promo_id, *args, **kwargs):
        p, err = self._get_promo(request, promo_id)
        if err:
            return err
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _refund_wallet_for_cancelled_order(order) -> None:
    """Credit the customer's wallet when a wallet-paid order is cancelled.
    Idempotent — checks for an existing refund transaction before writing.
    """
    from decimal import Decimal as _Dec
    from django.db import transaction as _dbtx
    from accounts.models import Customer as _CustM, WalletTransaction as _WTM

    if not order.customer_id:
        return
    refund_amount = _Dec(str(order.wallet_amount_paid or "0"))
    if refund_amount <= _Dec("0"):
        return
    # Idempotency guard
    if _WTM.objects.filter(
        customer_id=order.customer_id,
        type=_WTM.Type.REFUND,
        reference=order.order_number,
    ).exists():
        return
    with _dbtx.atomic():
        _cust = _CustM.objects.select_for_update().get(pk=order.customer_id)
        _cust.wallet_balance = _cust.wallet_balance + refund_amount
        _cust.save(update_fields=["wallet_balance", "updated_at"])
        _WTM.objects.create(
            customer=_cust,
            type=_WTM.Type.REFUND,
            amount=refund_amount,
            reference=order.order_number,
            note="Refund for cancelled order",
        )


class OwnerOrderStatusUpdateView(APIView):
    """PATCH /api/owner/orders/<id>/status/ — owner updates order status."""
    permission_classes = [IsAuthenticated]

    ALLOWED_TRANSITIONS = {
        Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
        Order.Status.CONFIRMED: {Order.Status.PREPARING, Order.Status.CANCELLED},
        Order.Status.PREPARING: {Order.Status.READY, Order.Status.CANCELLED},
        Order.Status.READY: {Order.Status.COMPLETED, Order.Status.CANCELLED},
        Order.Status.COMPLETED: set(),
        Order.Status.CANCELLED: set(),
    }

    def patch(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").filter(id=order_id).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = (request.data.get("status") or "").strip().lower()
        owner_note = request.data.get("owner_note")
        estimated_ready_minutes = request.data.get("estimated_ready_minutes")

        if new_status:
            allowed = self.ALLOWED_TRANSITIONS.get(order.status, set())
            if new_status not in {s.value for s in allowed}:
                return Response(
                    {"detail": f"Cannot transition from '{order.status}' to '{new_status}'.", "code": "invalid_transition"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.status = new_status
            order.status_updated_at = timezone.now()

        if owner_note is not None:
            order.owner_note = str(owner_note).strip()[:500]

        if estimated_ready_minutes is not None:
            try:
                mins = int(estimated_ready_minutes)
                order.estimated_ready_minutes = max(0, mins) if mins >= 0 else None
            except (TypeError, ValueError):
                order.estimated_ready_minutes = None

        order.save(update_fields=["status", "status_updated_at", "owner_note", "estimated_ready_minutes", "updated_at"])

        # Auto-refund wallet credits when an order is cancelled
        if new_status == Order.Status.CANCELLED:
            try:
                _refund_wallet_for_cancelled_order(order)
            except Exception:
                pass  # Non-fatal — refund failure must not block the status update response

        tenant = getattr(request, "tenant", None)
        if new_status in {Order.Status.CONFIRMED, Order.Status.PREPARING, Order.Status.READY, Order.Status.CANCELLED}:
            if tenant:
                _send_order_status_email(order, tenant, new_status)

        # SMS notification — only when transitioning to "ready"
        if new_status == Order.Status.READY and tenant:
            try:
                profile = tenant.profile
            except Exception:
                profile = None
            if profile and getattr(profile, "sms_notifications_enabled", False):
                customer_phone = (getattr(order, "customer_phone", "") or "").strip()
                if customer_phone:
                    from menu.sms import send_order_ready_sms  # noqa: PLC0415
                    send_order_ready_sms(
                        phone=customer_phone,
                        tenant_name=getattr(tenant, "name", ""),
                        order_number=order.order_number,
                    )

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
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

        qs = Order.objects.prefetch_related("items").order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        tenant_slug = getattr(getattr(request, "tenant", None), "slug", "export")
        filename = f"{tenant_slug}-orders-{timezone.now():%Y%m%d}.csv"

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            "order_number", "created_at", "status", "fulfillment_type",
            "table_label", "customer_name", "customer_phone",
            "customer_note", "delivery_address",
            "items", "subtotal", "delivery_fee", "total", "currency",
        ])

        for order in qs[:5000]:
            items_text = " | ".join(
                f"{i.qty}x {i.dish_name}"
                + (
                    f" ({', '.join(o.get('name', '') for o in (i.options or []) if o.get('name'))})"
                    if i.options
                    else ""
                )
                for i in order.items.all()
            )
            subtotal = order.total - order.delivery_fee
            writer.writerow([
                order.order_number,
                timezone.localtime(order.created_at).isoformat(),
                order.status,
                order.fulfillment_type or "",
                order.table_label or "",
                order.customer_name or "",
                order.customer_phone or "",
                order.customer_note or "",
                order.delivery_address or "",
                items_text,
                str(subtotal),
                str(order.delivery_fee),
                str(order.total),
                order.currency or "",
            ])

        return response


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
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        clear_stock = bool(request.data.get("clear_stock", False))

        # Re-enable all published dishes that are currently sold-out (is_available=False)
        restored_count = Dish.objects.filter(
            is_published=True, is_available=False
        ).update(is_available=True)

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
        404 Not Found — unknown order_number
    """

    permission_classes = [AllowAny]

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


class OwnerRatingListView(APIView):
    """
    GET /api/owner/ratings/

    Returns all ratings for the current tenant, newest first.
    Supports ?format=csv for a spreadsheet export.

    Requires: authenticated tenant owner or staff.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            Rating.objects
            .select_related("order")
            .order_by("-created_at")
        )

        # CSV export
        if request.query_params.get("format", "").lower() == "csv":
            return self._csv_response(qs)

        # Aggregate summary
        from django.db.models import Avg, Count
        agg = Rating.objects.aggregate(avg=Avg("score"), total=Count("id"))
        average = round(float(agg["avg"]), 1) if agg["avg"] is not None else None

        ratings = [
            {
                "id": r.id,
                "order_number": r.order.order_number,
                "customer_name": r.order.customer_name,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at.isoformat(),
            }
            for r in qs[:500]
        ]

        return Response({
            "count": agg["total"],
            "average": average,
            "ratings": ratings,
        })

    def _csv_response(self, qs):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Order Number", "Customer", "Score", "Comment"])
        for r in qs:
            writer.writerow([
                r.created_at.strftime("%Y-%m-%d %H:%M"),
                r.order.order_number,
                r.order.customer_name,
                r.score,
                r.comment,
            ])
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ratings.csv"'
        return response


# ── Closure dates (holiday / one-off closures) ────────────────────────────────

def _is_tenant_owner(request) -> bool:
    """Return True if the requesting user has owner or above access on this tenant."""
    user = request.user
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or getattr(user, "is_platform_admin", False):
        return True
    tenant = getattr(request, "tenant", None)
    if tenant is None or getattr(user, "tenant_id", None) != tenant.id:
        return False
    return user.role in {user.Roles.TENANT_OWNER, user.Roles.TENANT_STAFF}


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
    food subtotal, commission charged (10 %), and net payout, plus summary totals.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not _is_tenant_owner(request):
            return Response({"detail": "Owner access required."}, status=403)

        from django.db.models import Sum, Count, Avg
        from calendar import month_name

        # Parse year/month, defaulting to current month
        now = timezone.now()
        try:
            year = int(request.query_params.get("year", now.year))
            month = int(request.query_params.get("month", now.month))
            if not (1 <= month <= 12) or year < 2000:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year/month parameters."}, status=400)

        fmt = request.query_params.get("format", "json").lower()

        # Query marketplace orders for this month
        qs = (
            Order.objects
            .filter(
                source=Order.Source.MARKETPLACE,
                created_at__year=year,
                created_at__month=month,
            )
            .order_by("created_at")
        )

        agg = qs.aggregate(
            order_count=Count("id"),
            total_revenue=Sum("total"),
            total_commission=Sum("commission_amount"),
        )
        order_count = agg["order_count"] or 0
        total_revenue = float(agg["total_revenue"] or 0)
        total_commission = float(agg["total_commission"] or 0)
        net_payout = round(total_revenue - total_commission, 2)

        orders_data = [
            {
                "order_number": o.order_number,
                "created_at": o.created_at.isoformat(),
                "customer_name": o.customer_name or "",
                "total": float(o.total),
                "commission_amount": float(o.commission_amount),
                "net_payout": round(float(o.total) - float(o.commission_amount), 2),
                "currency": o.currency,
                "status": o.status,
            }
            for o in qs
        ]

        if fmt != "pdf":
            return Response({
                "year": year,
                "month": month,
                "month_name": month_name[month],
                "summary": {
                    "order_count": order_count,
                    "total_revenue": total_revenue,
                    "total_commission": total_commission,
                    "net_payout": net_payout,
                },
                "orders": orders_data,
            })

        # ── PDF ───────────────────────────────────────────────────────────────
        currency = orders_data[0]["currency"] if orders_data else ""

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

        # Summary box
        doc.setFillColorRGB(0.94, 0.95, 0.98)
        doc.rect(margin, y - 28 * mm, page_w - 2 * margin, 28 * mm, fill=1, stroke=0)
        doc.setFillColorRGB(0, 0, 0)

        summary_items = [
            ("Orders placed via marketplace:", str(order_count)),
            ("Total revenue:", f"{currency} {total_revenue:,.2f}"),
            ("Platform commission (10%):", f"{currency} {total_commission:,.2f}"),
            ("Net payout to restaurant:", f"{currency} {net_payout:,.2f}"),
        ]
        sy = y - 8 * mm
        for label, value in summary_items:
            doc.setFont("Helvetica", 9)
            doc.drawString(margin + 4 * mm, sy, label)
            doc.setFont("Helvetica-Bold", 9)
            doc.drawRightString(page_w - margin - 4 * mm, sy, value)
            sy -= 5 * mm

        y -= 35 * mm

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

        # Totals row
        y -= 2 * mm
        doc.line(margin, y, page_w - margin, y)
        y -= 5 * mm
        doc.setFont("Helvetica-Bold", 9)
        doc.drawString(margin + 2 * mm, y, "TOTALS")
        doc.drawRightString(col_x[2] + col_widths[2] - 2 * mm, y, f"{currency} {total_revenue:,.2f}")
        doc.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y, f"{currency} {total_commission:,.2f}")
        doc.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y, f"{currency} {net_payout:,.2f}")

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
                "delivery_minimum_order": str(p.delivery_minimum_order),
                "delivery_zone_description": p.delivery_zone_description,
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
