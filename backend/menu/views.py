from datetime import datetime, timedelta
from decimal import Decimal
import csv
from io import BytesIO, StringIO
import re
from urllib.parse import quote_plus
import zipfile

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count
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

from .models import AnalyticsEvent, Category, Dish, DishOption, OptionGroup, Order, OrderItem, SuperCategory, TableLink
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

    def list(self, request, *args, **kwargs):
        blocked = self._enforce_public_menu_policy()
        if blocked is not None:
            return blocked
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        blocked = self._enforce_public_menu_policy()
        if blocked is not None:
            return blocked
        return super().retrieve(request, *args, **kwargs)


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
            qs = qs.filter(is_published=True, category__is_published=True)
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
        if profile.is_open is False and not can_preview:
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
                "total": str(total),
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
        if profile.is_open is False and not can_preview:
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


def _generate_order_number() -> str:
    """Generate a unique order number like ORD-A3F2C1."""
    for _ in range(10):
        candidate = f"ORD-{_secrets.token_hex(3).upper()}"
        if not Order.objects.filter(order_number=candidate).exists():
            return candidate
    raise RuntimeError("Could not generate unique order number after 10 attempts.")


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
        if profile.is_open is False and not can_preview:
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
            slug__in=slugs, is_published=True, category__is_published=True
        ).select_related("category")}

        missing = [s for s in slugs if s not in dishes_map]
        if missing:
            return Response({"detail": "Some items are unavailable.", "code": "items_unavailable", "slugs": missing}, status=status.HTTP_400_BAD_REQUEST)

        options_map = {}
        if all_option_ids:
            options_map = {o.id: o for o in DishOption.objects.filter(id__in=all_option_ids)}

        # Build order items and compute total
        order_items_data = []
        total = Decimal("0")
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
            total += subtotal
            order_items_data.append({
                "dish_slug": dish.slug,
                "dish_name": dish.name,
                "unit_price": unit_price,
                "qty": qty,
                "note": item_input.get("note", ""),
                "options": option_snapshots,
                "subtotal": subtotal,
            })

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

        # For delivery, enrich order with customer identity; for pickup/table use payload values
        if fulfillment_type == Order.FulfillmentType.DELIVERY and _linked_customer:
            _customer_name = _linked_customer.name or validated.get("customer_name", "")
            _customer_phone = _linked_customer.phone or validated.get("customer_phone", "")
        else:
            _customer_name = validated.get("customer_name", "")
            _customer_phone = validated.get("customer_phone", "")

        try:
            with transaction.atomic():
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
                    currency=currency,
                )
                for item_data in order_items_data:
                    OrderItem.objects.create(order=order, **item_data)
        except IntegrityError:
            # Rare TOCTOU race: two requests generated the same order number.
            # Return 503 so the client can retry; a fresh number will be picked.
            return Response(
                {"detail": "Order could not be placed due to a conflict. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Notify the tenant owner — outside the atomic block so SMTP latency
        # never holds the DB transaction open.
        _send_owner_new_order_email(request.tenant, order)

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "total": str(order.total),
            "currency": order.currency,
            "estimated_ready_minutes": order.estimated_ready_minutes,
        }, status=status.HTTP_201_CREATED)


class CustomerOrderStatusView(APIView):
    """GET /api/order-status/<order_number>/ — customer polls order status."""
    permission_classes = [AllowAny]

    def get(self, request, order_number, *args, **kwargs):
        order_number = (order_number or "").strip().upper()
        order = Order.objects.filter(order_number=order_number).prefetch_related("items").first()
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

        return Response({
            "order_number": order.order_number,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "table_label": order.table_label,
            "customer_name": order.customer_name,
            "delivery_address": order.delivery_address,
            "delivery_location_url": order.delivery_location_url,
            "total": str(order.total),
            "currency": order.currency,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "items_count": sum(i["qty"] for i in items),
            "items": items,
            "created_at": order.created_at.isoformat(),
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
        })


def _send_owner_new_order_email(tenant, order) -> None:
    """Send a plain-text new-order notification to the tenant owner.

    Fails silently — a broken SMTP config must never prevent order creation.
    """
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

        fulfillment = str(order.fulfillment_type).title()
        items_lines = "\n".join(
            f"  {i.qty}× {i.dish_name}" for i in order.items.all()
        )
        customer_line = ""
        if order.customer_name:
            customer_line = f"Customer: {order.customer_name}"
            if order.customer_phone:
                customer_line += f" ({order.customer_phone})"
            customer_line += "\n"

        table_line = f"Table: {order.table_label}\n" if order.table_label else ""

        body = (
            f"New order received — #{order.order_number}\n"
            f"{'=' * 40}\n"
            f"Type: {fulfillment}\n"
            f"{table_line}"
            f"{customer_line}"
            f"\nItems:\n{items_lines}\n\n"
            f"Total: {order.total} {order.currency}\n"
        )

        send_mail(
            subject=f"New order #{order.order_number} — {tenant.name}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )
    except Exception:  # noqa: BLE001
        pass  # Never let email failure block order creation


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

        orders = []
        for order in qs[:200]:
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
            })

        return Response({"results": orders, "count": len(orders)})


class OwnerOrderDetailView(APIView):
    """GET /api/owner/orders/<id>/ — single order detail."""
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id, *args, **kwargs):
        if not _can_edit_tenant_order(request):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        order = Order.objects.select_related("customer").prefetch_related("items").filter(id=order_id).first()
        if order is None:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

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
        })


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

        order = Order.objects.filter(id=order_id).first()
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

        return Response({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "owner_note": order.owner_note,
            "estimated_ready_minutes": order.estimated_ready_minutes,
            "status_updated_at": order.status_updated_at.isoformat() if order.status_updated_at else None,
        })


