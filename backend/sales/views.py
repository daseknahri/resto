import csv
from datetime import date
from math import ceil
from urllib.parse import quote_plus

from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tenancy.models import Plan, Tenant
from tenancy.tiering import external_plan_code, plan_display_name, plan_tier_order, is_plan_upgrade

from .audit import log_admin_action
from .models import AdminAuditLog, Lead, ProvisioningJob, ReservationReminder, ReservationTimelineEvent, TierUpgradeRequest
from .permissions import IsPlatformAdmin, IsTenantEditor
from .serializers import (
    AdminTenantSerializer,
    AdminAuditLogSerializer,
    LeadSerializer,
    OwnerReservationBulkReminderSerializer,
    OwnerReservationBulkReminderResultSerializer,
    OwnerReservationBulkUpdateSerializer,
    ReservationReminderResultSerializer,
    ReservationReminderSerializer,
    OwnerReservationSerializer,
    ReservationTimelineCreateSerializer,
    ReservationTimelineEventSerializer,
    OwnerReservationUpdateSerializer,
    ProvisioningJobSerializer,
    TierUpgradeDecisionSerializer,
    TenantLifecycleUpdateSerializer,
    TierUpgradeTargetSerializer,
    TierUpgradeRequestCreateSerializer,
    TierUpgradeRequestSerializer,
)
from .sla import (
    RESERVATION_SOURCES,
    reservation_due_soon_cutoff,
    reservation_due_soon_minutes,
    reservation_overdue_cutoff,
    reservation_sla_minutes,
)
from .services import (
    create_tier_upgrade_request,
    decide_tier_upgrade_request,
    onboarding_package_for_lead,
    preview_lead_provision,
    provision_lead,
    resend_activation_for_lead,
)


OWNER_RESERVATION_STATUSES = {
    Lead.Status.NEW,
    Lead.Status.CONTACTED,
    Lead.Status.WON,
    Lead.Status.LOST,
}
OWNER_REMINDER_STATUSES = {
    ReservationReminder.Statuses.SENT,
    ReservationReminder.Statuses.OPENED,
    ReservationReminder.Statuses.FAILED,
    "none",
}
DEFAULT_OWNER_RESERVATION_PAGE_SIZE = 20
MAX_OWNER_RESERVATION_PAGE_SIZE = 100
DEFAULT_ADMIN_AUDIT_PAGE_SIZE = 50
MAX_ADMIN_AUDIT_PAGE_SIZE = 200
DEFAULT_ADMIN_TENANT_PAGE_SIZE = 25
MAX_ADMIN_TENANT_PAGE_SIZE = 200


def _parse_iso_date(value: str):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _owner_reservations_queryset(tenant_id, *, status_filter="", reminder_filter="", search="", from_date=None, to_date=None):
    queryset = _with_reservation_reminder_metrics(
        Lead.objects.filter(
            tenant_id=tenant_id,
            source__in=RESERVATION_SOURCES,
            archived_at__isnull=True,
        ).select_related("tenant")
    )

    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if reminder_filter:
        if reminder_filter == "none":
            queryset = queryset.filter(reminder_count=0)
        else:
            queryset = queryset.filter(last_reminder_status=reminder_filter)
    if search:
        term = search[:120]
        queryset = queryset.filter(
            Q(name__icontains=term)
            | Q(email__icontains=term)
            | Q(phone__icontains=term)
            | Q(notes__icontains=term)
        )
    if from_date:
        queryset = queryset.filter(created_at__date__gte=from_date)
    if to_date:
        queryset = queryset.filter(created_at__date__lte=to_date)
    return queryset


def _with_reservation_reminder_metrics(queryset):
    latest_reminder_rows = ReservationReminder.objects.filter(lead_id=OuterRef("pk")).order_by("-created_at")
    return queryset.annotate(
        last_reminder_status=Subquery(latest_reminder_rows.values("status")[:1]),
        last_reminder_at=Subquery(latest_reminder_rows.values("created_at")[:1]),
        reminder_count=Count("reminders"),
        reminder_opened_count=Count(
            "reminders",
            filter=Q(reminders__status=ReservationReminder.Statuses.OPENED),
        ),
        reminder_failed_count=Count(
            "reminders",
            filter=Q(reminders__status=ReservationReminder.Statuses.FAILED),
        ),
    )


def _parse_positive_int(value: str, *, default: int, min_value: int = 1, max_value: int | None = None) -> int:
    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    if parsed < min_value:
        parsed = min_value
    if max_value is not None and parsed > max_value:
        parsed = max_value
    return parsed


def _owner_reservation_counts(tenant_id, *, reminder_filter="", search="", from_date=None, to_date=None):
    counts = {
        "total": 0,
        Lead.Status.NEW: 0,
        Lead.Status.CONTACTED: 0,
        Lead.Status.WON: 0,
        Lead.Status.LOST: 0,
        "overdue_new": 0,
    }
    counts["total"] = _owner_reservations_queryset(
        tenant_id,
        reminder_filter=reminder_filter,
        search=search,
        from_date=from_date,
        to_date=to_date,
    ).count()
    for status_code in (Lead.Status.NEW, Lead.Status.CONTACTED, Lead.Status.WON, Lead.Status.LOST):
        counts[status_code] = _owner_reservations_queryset(
            tenant_id,
            status_filter=status_code,
            reminder_filter=reminder_filter,
            search=search,
            from_date=from_date,
            to_date=to_date,
        ).count()
    counts["overdue_new"] = (
        _owner_reservations_queryset(
            tenant_id,
            status_filter=Lead.Status.NEW,
            reminder_filter=reminder_filter,
            search=search,
            from_date=from_date,
            to_date=to_date,
        )
        .filter(created_at__lte=reservation_overdue_cutoff())
        .count()
    )
    return counts


def _log_reservation_timeline_event(
    *,
    lead,
    tenant,
    actor,
    action,
    note="",
    previous_status="",
    new_status="",
):
    actor_id = getattr(actor, "pk", None) if getattr(actor, "is_authenticated", False) else None
    ReservationTimelineEvent.objects.create(
        lead_id=getattr(lead, "id", None),
        tenant_id=getattr(tenant, "id", None),
        actor_id=actor_id,
        action=action,
        note=note,
        previous_status=previous_status or "",
        new_status=new_status or "",
    )


def _reservation_phone_digits(phone_value: str) -> str:
    return "".join(ch for ch in str(phone_value or "") if ch.isdigit())


def _build_whatsapp_reservation_reminder(*, lead, tenant):
    phone_digits = _reservation_phone_digits(getattr(lead, "phone", "") or "")
    if not phone_digits:
        return None
    guest_name = (str(getattr(lead, "name", "") or "").strip() or "there")
    restaurant_name = (str(getattr(tenant, "name", "") or "").strip() or "our restaurant")
    message = (
        f"Hi {guest_name},\n"
        f"This is {restaurant_name}.\n"
        "We are following up on your table reservation request.\n"
        "Please reply with your preferred date and time so we can confirm your booking."
    )
    whatsapp_link = f"https://wa.me/{phone_digits}?text={quote_plus(message)}"
    return {
        "phone": phone_digits,
        "message": message,
        "whatsapp_link": whatsapp_link,
    }


class LeadViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Lead.objects.filter(archived_at__isnull=True).order_by("-created_at")
    serializer_class = LeadSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsPlatformAdmin()]

    def get_queryset(self):
        queryset = _with_reservation_reminder_metrics(
            Lead.objects.filter(archived_at__isnull=True)
            .select_related("plan", "tenant")
            .order_by("-created_at")
        )
        source = (self.request.query_params.get("source") or "").strip()
        if source:
            queryset = queryset.filter(source=source)
        tenant_slug = (self.request.query_params.get("tenant") or "").strip().lower()
        if tenant_slug:
            queryset = queryset.filter(tenant__slug=tenant_slug)
        status_filter = (self.request.query_params.get("status") or "").strip().lower()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = getattr(request, "tenant", None)
        tenant_for_lead = None
        if tenant is not None and getattr(tenant, "schema_name", None) != get_public_schema_name():
            tenant_for_lead = tenant
        lead = serializer.save(status=Lead.Status.NEW, tenant=tenant_for_lead)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(lead).data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        lead = self.get_object()
        if lead.archived_at is None:
            lead.archived_at = timezone.now()
            lead.save(update_fields=["archived_at", "updated_at"])
            log_admin_action(
                action=AdminAuditLog.Actions.LEAD_ARCHIVED,
                request=request,
                lead=lead,
                target_repr=f"lead:{lead.id}",
                metadata={"lead_status": lead.status},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProvisionLeadViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsPlatformAdmin]

    def update(self, request, *args, **kwargs):
        lead = self.get_object()
        domain_suffix = request.data.get("domain_suffix", "localhost")
        requested_slug = request.data.get("requested_slug")
        try:
            result = provision_lead(lead, domain_suffix=domain_suffix, requested_slug=requested_slug)
        except ValueError as exc:
            log_admin_action(
                action=AdminAuditLog.Actions.LEAD_PROVISIONED,
                request=request,
                lead=lead,
                target_repr=f"lead:{lead.id}",
                metadata={"status": "failed", "reason": str(exc)},
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_admin_action(
            action=AdminAuditLog.Actions.LEAD_PROVISIONED,
            request=request,
            tenant=result.tenant,
            lead=lead,
            target_repr=f"tenant:{result.tenant.slug}",
            metadata={
                "status": "success",
                "tenant_url": result.tenant_url,
                "admin_url": result.admin_url,
            },
        )
        return Response(
            {
                "detail": "Provisioned",
                "tenant": result.tenant.slug,
                "tenant_url": result.tenant_url,
                "admin_url": result.admin_url,
                "activation_url": result.activation_url,
                "activation_token": result.activation_token.token,
                "job_id": result.job.id,
                "whatsapp_link": result.whatsapp_link,
                "whatsapp_message_template": result.whatsapp_message_template,
            }
        )


class ProvisioningJobViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = ProvisioningJob.objects.order_by("-created_at")
    serializer_class = ProvisioningJobSerializer
    permission_classes = [IsPlatformAdmin]


class AdminAuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = AdminAuditLog.objects.select_related("actor", "tenant", "lead").order_by("-created_at")
    serializer_class = AdminAuditLogSerializer
    permission_classes = [IsPlatformAdmin]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        action_filter = (request.query_params.get("action") or "").strip().lower()
        if action_filter:
            queryset = queryset.filter(action=action_filter)

        tenant_slug = (request.query_params.get("tenant") or "").strip().lower()
        if tenant_slug:
            queryset = queryset.filter(tenant__slug=tenant_slug)

        search = (request.query_params.get("q") or "").strip()
        if search:
            term = search[:120]
            queryset = queryset.filter(
                Q(action__icontains=term)
                | Q(target_repr__icontains=term)
                | Q(actor__username__icontains=term)
                | Q(tenant__slug__icontains=term)
                | Q(lead__name__icontains=term)
            )

        page_size = _parse_positive_int(
            request.query_params.get("page_size"),
            default=DEFAULT_ADMIN_AUDIT_PAGE_SIZE,
            min_value=1,
            max_value=MAX_ADMIN_AUDIT_PAGE_SIZE,
        )
        page = _parse_positive_int(
            request.query_params.get("page"),
            default=1,
            min_value=1,
        )

        total = queryset.count()
        total_pages = max(1, ceil(total / page_size)) if total else 1
        if page > total_pages:
            page = total_pages

        offset = (page - 1) * page_size
        rows = queryset[offset : offset + page_size]
        data = self.get_serializer(rows, many=True).data
        return Response(
            {
                "results": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }
        )


class AdminTenantListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter and status_filter not in {
            Tenant.LifecycleStatus.ACTIVE,
            Tenant.LifecycleStatus.SUSPENDED,
            Tenant.LifecycleStatus.CANCELED,
        }:
            return Response({"detail": "Invalid status filter."}, status=status.HTTP_400_BAD_REQUEST)

        search = (request.query_params.get("q") or "").strip()
        page = _parse_positive_int(
            request.query_params.get("page"),
            default=1,
            min_value=1,
        )
        page_size = _parse_positive_int(
            request.query_params.get("page_size"),
            default=DEFAULT_ADMIN_TENANT_PAGE_SIZE,
            min_value=1,
            max_value=MAX_ADMIN_TENANT_PAGE_SIZE,
        )

        with schema_context(get_public_schema_name()):
            queryset = Tenant.objects.select_related("plan", "owner").prefetch_related("domains").order_by("slug")
            queryset = queryset.exclude(schema_name=get_public_schema_name())
            if status_filter:
                queryset = queryset.filter(lifecycle_status=status_filter)
            if search:
                term = search[:120]
                queryset = queryset.filter(
                    Q(name__icontains=term)
                    | Q(slug__icontains=term)
                    | Q(schema_name__icontains=term)
                    | Q(owner__username__icontains=term)
                    | Q(domains__domain__icontains=term)
                ).distinct()

            total = queryset.count()
            total_pages = max(1, ceil(total / page_size)) if total else 1
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * page_size
            rows = queryset[offset : offset + page_size]
            data = AdminTenantSerializer(rows, many=True).data

        return Response(
            {
                "results": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }
        )


class AdminTenantLifecycleView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, tenant_id):
        serializer = TenantLifecycleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")

        with schema_context(get_public_schema_name()):
            tenant = get_object_or_404(Tenant.objects.select_related("plan", "owner").prefetch_related("domains"), pk=tenant_id)
            if getattr(tenant, "schema_name", "") == get_public_schema_name():
                return Response({"detail": "Public tenant lifecycle cannot be changed."}, status=status.HTTP_400_BAD_REQUEST)

            update_fields = []
            now = timezone.now()
            if action == "suspend":
                if tenant.lifecycle_status == Tenant.LifecycleStatus.CANCELED:
                    return Response(
                        {"detail": "Canceled tenant cannot be suspended. Reactivate first if needed."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                tenant.is_active = False
                tenant.lifecycle_status = Tenant.LifecycleStatus.SUSPENDED
                tenant.suspended_at = now
                update_fields = ["is_active", "lifecycle_status", "suspended_at"]
                detail = "Tenant suspended."
                audit_action = AdminAuditLog.Actions.TENANT_DEACTIVATED
            elif action == "reactivate":
                tenant.is_active = True
                tenant.lifecycle_status = Tenant.LifecycleStatus.ACTIVE
                tenant.suspended_at = None
                tenant.canceled_at = None
                tenant.canceled_reason = ""
                update_fields = ["is_active", "lifecycle_status", "suspended_at", "canceled_at", "canceled_reason"]
                detail = "Tenant reactivated."
                audit_action = AdminAuditLog.Actions.TENANT_REACTIVATED
            else:
                tenant.is_active = False
                tenant.lifecycle_status = Tenant.LifecycleStatus.CANCELED
                tenant.canceled_at = now
                tenant.canceled_reason = reason
                tenant.suspended_at = None
                update_fields = ["is_active", "lifecycle_status", "canceled_at", "canceled_reason", "suspended_at"]
                detail = "Tenant canceled."
                audit_action = AdminAuditLog.Actions.TENANT_DEACTIVATED

            tenant.save(update_fields=update_fields)
            log_admin_action(
                action=audit_action,
                request=request,
                actor=request.user,
                tenant=tenant,
                target_repr=f"tenant:{tenant.slug}",
                metadata={
                    "tenant_name": tenant.name,
                    "lifecycle_action": action,
                    "lifecycle_status": tenant.lifecycle_status,
                    "reason": reason,
                },
            )
            payload = AdminTenantSerializer(tenant).data

        return Response({"detail": detail, "tenant": payload}, status=status.HTTP_200_OK)


class LeadProvisionPreviewView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        domain_suffix = request.query_params.get("domain_suffix", "localhost")
        requested_slug = request.query_params.get("requested_slug")
        return Response(preview_lead_provision(lead, domain_suffix=domain_suffix, requested_slug=requested_slug))


class LeadResendActivationView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        try:
            result = resend_activation_for_lead(lead)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_admin_action(
            action=AdminAuditLog.Actions.ACTIVATION_RESENT,
            request=request,
            tenant=result.tenant,
            lead=lead,
            target_repr=f"tenant:{result.tenant.slug}",
            metadata={"activation_url": result.activation_url},
        )
        return Response(
            {
                "detail": "Activation resent",
                "tenant": result.tenant.slug,
                "tenant_url": result.tenant_url,
                "admin_url": result.admin_url,
                "activation_url": result.activation_url,
                "activation_token": result.activation_token.token,
                "whatsapp_link": result.whatsapp_link,
                "whatsapp_message_template": result.whatsapp_message_template,
            }
        )


class LeadOnboardingPackageView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, pk=lead_id)
        refresh_token = request.query_params.get("refresh_token") in {"1", "true", "yes"}
        try:
            result = onboarding_package_for_lead(lead, refresh_token=refresh_token)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log_admin_action(
            action=AdminAuditLog.Actions.ONBOARDING_PACKAGE_SENT,
            request=request,
            tenant=result.tenant,
            lead=lead,
            target_repr=f"tenant:{result.tenant.slug}",
            metadata={"refresh_token": refresh_token, "activation_url": result.activation_url},
        )
        return Response(
            {
                "detail": "Onboarding package ready",
                "tenant": result.tenant.slug,
                "tenant_url": result.tenant_url,
                "admin_url": result.admin_url,
                "activation_url": result.activation_url,
                "activation_token": result.activation_token.token,
                "whatsapp_link": result.whatsapp_link,
                "whatsapp_message_template": result.whatsapp_message_template,
            }
        )


class AdminReservationAlertsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        state_filter = (request.query_params.get("state") or "all").strip().lower()
        if state_filter not in {"all", "overdue", "due_soon"}:
            return Response({"detail": "Invalid state filter."}, status=status.HTTP_400_BAD_REQUEST)
        tenant_slug = (request.query_params.get("tenant") or "").strip().lower()
        limit = _parse_positive_int(request.query_params.get("limit"), default=30, min_value=1, max_value=200)

        with schema_context(get_public_schema_name()):
            now = timezone.now()
            overdue_cutoff = reservation_overdue_cutoff(now=now)
            due_soon_cutoff = reservation_due_soon_cutoff(now=now)

            scope = Lead.objects.filter(
                source__in=RESERVATION_SOURCES,
                status=Lead.Status.NEW,
                archived_at__isnull=True,
            ).select_related("tenant", "plan")
            scope = _with_reservation_reminder_metrics(scope)
            if tenant_slug:
                scope = scope.filter(tenant__slug=tenant_slug)

            overdue_queryset = scope.filter(created_at__lte=overdue_cutoff)
            due_soon_queryset = scope.filter(created_at__gt=overdue_cutoff, created_at__lte=due_soon_cutoff)
            if state_filter == "overdue":
                rows = overdue_queryset.order_by("created_at")
            elif state_filter == "due_soon":
                rows = due_soon_queryset.order_by("created_at")
            else:
                rows = scope.filter(created_at__lte=due_soon_cutoff).order_by("created_at")

            overdue_count = overdue_queryset.count()
            due_soon_count = due_soon_queryset.count()
            results = LeadSerializer(rows[:limit], many=True, context={"_reservation_sla_now": now}).data

        return Response(
            {
                "generated_at": now,
                "filters": {
                    "state": state_filter,
                    "tenant": tenant_slug,
                    "limit": limit,
                },
                "thresholds": {
                    "overdue_minutes": reservation_sla_minutes(),
                    "due_soon_minutes": reservation_due_soon_minutes(),
                },
                "counts": {
                    "overdue": overdue_count,
                    "due_soon": due_soon_count,
                    "total_alerts": overdue_count + due_soon_count,
                },
                "results": results,
            }
        )


class OwnerReservationListView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter and status_filter not in OWNER_RESERVATION_STATUSES:
            return Response({"detail": "Invalid status filter."}, status=status.HTTP_400_BAD_REQUEST)
        reminder_filter = (request.query_params.get("reminder_status") or "").strip().lower()
        if reminder_filter and reminder_filter not in OWNER_REMINDER_STATUSES:
            return Response({"detail": "Invalid reminder_status filter."}, status=status.HTTP_400_BAD_REQUEST)
        search = (request.query_params.get("q") or "").strip()
        from_date_raw = request.query_params.get("from")
        to_date_raw = request.query_params.get("to")
        from_date = _parse_iso_date(from_date_raw or "")
        to_date = _parse_iso_date(to_date_raw or "")
        if from_date_raw and from_date is None:
            return Response({"detail": "Invalid 'from' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if to_date_raw and to_date is None:
            return Response({"detail": "Invalid 'to' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if from_date and to_date and from_date > to_date:
            return Response({"detail": "'from' date cannot be after 'to' date."}, status=status.HTTP_400_BAD_REQUEST)
        page = _parse_positive_int(
            request.query_params.get("page"),
            default=1,
            min_value=1,
        )
        page_size = _parse_positive_int(
            request.query_params.get("page_size"),
            default=DEFAULT_OWNER_RESERVATION_PAGE_SIZE,
            min_value=1,
            max_value=MAX_OWNER_RESERVATION_PAGE_SIZE,
        )

        with schema_context(get_public_schema_name()):
            queryset = _owner_reservations_queryset(
                tenant.id,
                status_filter=status_filter,
                reminder_filter=reminder_filter,
                search=search,
                from_date=from_date,
                to_date=to_date,
            )
            total = queryset.count()
            pages = max(1, ceil(total / page_size)) if total else 1
            page = min(page, pages)
            start = (page - 1) * page_size
            end = start + page_size
            rows = queryset.order_by("-created_at")[start:end]
            data = OwnerReservationSerializer(rows, many=True).data
            counts = _owner_reservation_counts(
                tenant.id,
                reminder_filter=reminder_filter,
                search=search,
                from_date=from_date,
                to_date=to_date,
            )
        return Response(
            {
                "results": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "pages": pages,
                    "has_next": page < pages,
                    "has_prev": page > 1,
                },
                "counts": {
                    "total": counts["total"],
                    "new": counts[Lead.Status.NEW],
                    "overdue_new": counts["overdue_new"],
                    "contacted": counts[Lead.Status.CONTACTED],
                    "won": counts[Lead.Status.WON],
                    "lost": counts[Lead.Status.LOST],
                },
            }
        )


class OwnerReservationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def put(self, request, lead_id):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OwnerReservationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with schema_context(get_public_schema_name()):
            lead = get_object_or_404(
                Lead,
                pk=lead_id,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            previous_status = lead.status
            lead.status = serializer.validated_data["status"]
            lead.save(update_fields=["status", "updated_at"])
            if previous_status != lead.status:
                _log_reservation_timeline_event(
                    lead=lead,
                    tenant=tenant,
                    actor=request.user,
                    action=ReservationTimelineEvent.Actions.STATUS_CHANGE,
                    previous_status=previous_status,
                    new_status=lead.status,
                    note=f"Status updated from {previous_status} to {lead.status}.",
                )
            payload = OwnerReservationSerializer(lead).data

        return Response(payload)


class OwnerReservationBulkStatusView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OwnerReservationBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        status_value = serializer.validated_data["status"]

        with schema_context(get_public_schema_name()):
            queryset = Lead.objects.filter(
                id__in=ids,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            leads = list(queryset.only("id", "status"))
            found_ids = [lead.id for lead in leads]
            found_set = set(found_ids)
            missing_ids = sorted([item for item in ids if item not in found_set])
            changed_ids = [lead.id for lead in leads if lead.status != status_value]
            timestamp = timezone.now()
            updated_count = queryset.filter(id__in=changed_ids).update(status=status_value, updated_at=timestamp)
            if changed_ids:
                actor_id = getattr(request.user, "pk", None) if getattr(request.user, "is_authenticated", False) else None
                events = []
                for lead in leads:
                    if lead.id not in changed_ids:
                        continue
                    events.append(
                        ReservationTimelineEvent(
                            lead_id=lead.id,
                            tenant_id=getattr(tenant, "id", None),
                            actor_id=actor_id,
                            action=ReservationTimelineEvent.Actions.BULK_STATUS_CHANGE,
                            note=f"Bulk status update from {lead.status} to {status_value}.",
                            previous_status=lead.status,
                            new_status=status_value,
                        )
                    )
                ReservationTimelineEvent.objects.bulk_create(events)

        return Response(
            {
                "updated_count": updated_count,
                "status": status_value,
                "ids": sorted(found_ids),
                "missing_ids": missing_ids,
            }
        )


class OwnerReservationBulkReminderView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OwnerReservationBulkReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        require_failed_last_reminder = serializer.validated_data.get("require_failed_last_reminder", False)

        with schema_context(get_public_schema_name()):
            queryset = Lead.objects.filter(
                id__in=ids,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            leads = list(_with_reservation_reminder_metrics(queryset))
            found_ids = [lead.id for lead in leads]
            found_set = set(found_ids)
            missing_ids = sorted([item for item in ids if item not in found_set])
            skipped_unavailable_ids = []
            skipped_no_phone_ids = []
            skipped_not_failed_ids = []
            results = []

            for lead in leads:
                if lead.status == Lead.Status.LOST:
                    skipped_unavailable_ids.append(lead.id)
                    continue
                if require_failed_last_reminder and getattr(lead, "last_reminder_status", "") != ReservationReminder.Statuses.FAILED:
                    skipped_not_failed_ids.append(lead.id)
                    continue
                payload = _build_whatsapp_reservation_reminder(lead=lead, tenant=tenant)
                if payload is None:
                    skipped_no_phone_ids.append(lead.id)
                    continue

                reminder = ReservationReminder.objects.create(
                    lead_id=lead.id,
                    tenant_id=getattr(tenant, "id", None),
                    actor_id=getattr(request.user, "pk", None) if getattr(request.user, "is_authenticated", False) else None,
                    channel=ReservationReminder.Channels.WHATSAPP,
                    status=ReservationReminder.Statuses.SENT,
                    phone=payload["phone"],
                    message=payload["message"],
                    whatsapp_link=payload["whatsapp_link"],
                )
                _log_reservation_timeline_event(
                    lead=lead,
                    tenant=tenant,
                    actor=request.user,
                    action=ReservationTimelineEvent.Actions.NOTE,
                    note=f"Bulk WhatsApp reminder sent (tracking id: {reminder.id}).",
                )
                results.append(
                    {
                        "lead_id": lead.id,
                        "reminder_id": reminder.id,
                        "phone": payload["phone"],
                        "whatsapp_link": payload["whatsapp_link"],
                    }
                )

        return Response(
            {
                "prepared_count": len(results),
                "require_failed_last_reminder": bool(require_failed_last_reminder),
                "ids": sorted(found_ids),
                "missing_ids": missing_ids,
                "skipped_unavailable_ids": sorted(skipped_unavailable_ids),
                "skipped_no_phone_ids": sorted(skipped_no_phone_ids),
                "skipped_not_failed_ids": sorted(skipped_not_failed_ids),
                "results": results,
            }
        )


class OwnerReservationTimelineView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def get(self, request, lead_id):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)
        limit = _parse_positive_int(
            request.query_params.get("limit"),
            default=50,
            min_value=1,
            max_value=200,
        )

        with schema_context(get_public_schema_name()):
            lead = get_object_or_404(
                Lead,
                pk=lead_id,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            events = (
                ReservationTimelineEvent.objects.filter(lead_id=lead.id)
                .select_related("actor")
                .order_by("-created_at", "-id")[:limit]
            )
            data = ReservationTimelineEventSerializer(events, many=True).data
        return Response(data)

    def post(self, request, lead_id):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ReservationTimelineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data["note"].strip()

        with schema_context(get_public_schema_name()):
            lead = get_object_or_404(
                Lead,
                pk=lead_id,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            event = ReservationTimelineEvent.objects.create(
                lead_id=getattr(lead, "id", None),
                tenant_id=getattr(tenant, "id", None),
                actor_id=getattr(request.user, "pk", None) if getattr(request.user, "is_authenticated", False) else None,
                action=ReservationTimelineEvent.Actions.NOTE,
                note=note,
            )
            data = ReservationTimelineEventSerializer(event).data
        return Response(data, status=status.HTTP_201_CREATED)


class OwnerReservationReminderView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def post(self, request, lead_id):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(get_public_schema_name()):
            lead = get_object_or_404(
                Lead,
                pk=lead_id,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            if lead.status == Lead.Status.LOST:
                return Response({"detail": "Cannot send reminder for unavailable reservations."}, status=status.HTTP_400_BAD_REQUEST)

            payload = _build_whatsapp_reservation_reminder(lead=lead, tenant=tenant)
            if payload is None:
                return Response(
                    {"detail": "Reservation has no valid phone number for WhatsApp reminder."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reminder = ReservationReminder.objects.create(
                lead_id=lead.id,
                tenant_id=getattr(tenant, "id", None),
                actor_id=getattr(request.user, "pk", None) if getattr(request.user, "is_authenticated", False) else None,
                channel=ReservationReminder.Channels.WHATSAPP,
                status=ReservationReminder.Statuses.SENT,
                phone=payload["phone"],
                message=payload["message"],
                whatsapp_link=payload["whatsapp_link"],
            )

            _log_reservation_timeline_event(
                lead=lead,
                tenant=tenant,
                actor=request.user,
                action=ReservationTimelineEvent.Actions.NOTE,
                note=f"WhatsApp reminder sent (tracking id: {reminder.id}).",
            )

        return Response(ReservationReminderSerializer(reminder).data, status=status.HTTP_201_CREATED)


class OwnerReservationReminderResultView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def post(self, request, lead_id):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ReservationReminderResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reminder_id = serializer.validated_data["reminder_id"]
        result_status = serializer.validated_data["status"]
        result_error = serializer.validated_data.get("error", "").strip()

        with schema_context(get_public_schema_name()):
            lead = get_object_or_404(
                Lead,
                pk=lead_id,
                tenant_id=tenant.id,
                source__in=RESERVATION_SOURCES,
                archived_at__isnull=True,
            )
            reminder = get_object_or_404(
                ReservationReminder,
                pk=reminder_id,
                lead_id=lead.id,
                tenant_id=tenant.id,
            )
            reminder.status = result_status
            if result_status == ReservationReminder.Statuses.FAILED and result_error:
                reminder.failure_reason = result_error[:255]
            elif result_status != ReservationReminder.Statuses.FAILED:
                reminder.failure_reason = ""
            reminder.save(update_fields=["status", "failure_reason", "updated_at"])

            note = f"Reminder {reminder.id} marked {result_status}."
            if reminder.failure_reason:
                note = f"{note} Reason: {reminder.failure_reason}"
            _log_reservation_timeline_event(
                lead=lead,
                tenant=tenant,
                actor=request.user,
                action=ReservationTimelineEvent.Actions.NOTE,
                note=note,
            )

        return Response(ReservationReminderSerializer(reminder).data)


class OwnerReservationBulkReminderResultView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OwnerReservationBulkReminderResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["items"]

        updated = []
        missing = []
        with schema_context(get_public_schema_name()):
            for item in items:
                lead_id = item["lead_id"]
                reminder_id = item["reminder_id"]
                result_status = item["status"]
                result_error = item.get("error", "").strip()
                try:
                    lead = get_object_or_404(
                        Lead,
                        pk=lead_id,
                        tenant_id=tenant.id,
                        source__in=RESERVATION_SOURCES,
                        archived_at__isnull=True,
                    )
                    reminder = get_object_or_404(
                        ReservationReminder,
                        pk=reminder_id,
                        lead_id=lead.id,
                        tenant_id=tenant.id,
                    )
                except Http404:
                    missing.append(
                        {
                            "lead_id": lead_id,
                            "reminder_id": reminder_id,
                        }
                    )
                    continue

                reminder.status = result_status
                if result_status == ReservationReminder.Statuses.FAILED and result_error:
                    reminder.failure_reason = result_error[:255]
                elif result_status != ReservationReminder.Statuses.FAILED:
                    reminder.failure_reason = ""
                reminder.save(update_fields=["status", "failure_reason", "updated_at"])

                note = f"Reminder {reminder.id} marked {result_status} (bulk reconciliation)."
                if reminder.failure_reason:
                    note = f"{note} Reason: {reminder.failure_reason}"
                _log_reservation_timeline_event(
                    lead=lead,
                    tenant=tenant,
                    actor=request.user,
                    action=ReservationTimelineEvent.Actions.NOTE,
                    note=note,
                )
                updated.append(
                    {
                        "lead_id": lead.id,
                        "reminder_id": reminder.id,
                        "status": reminder.status,
                    }
                )

        return Response(
            {
                "updated_count": len(updated),
                "missing_count": len(missing),
                "updated": updated,
                "missing": missing,
            }
        )


class OwnerReservationExportView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        status_filter = (request.query_params.get("status") or "").strip().lower()
        if status_filter and status_filter not in OWNER_RESERVATION_STATUSES:
            return Response({"detail": "Invalid status filter."}, status=status.HTTP_400_BAD_REQUEST)
        reminder_filter = (request.query_params.get("reminder_status") or "").strip().lower()
        if reminder_filter and reminder_filter not in OWNER_REMINDER_STATUSES:
            return Response({"detail": "Invalid reminder_status filter."}, status=status.HTTP_400_BAD_REQUEST)
        search = (request.query_params.get("q") or "").strip()
        from_date_raw = request.query_params.get("from")
        to_date_raw = request.query_params.get("to")
        from_date = _parse_iso_date(from_date_raw or "")
        to_date = _parse_iso_date(to_date_raw or "")
        if from_date_raw and from_date is None:
            return Response({"detail": "Invalid 'from' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if to_date_raw and to_date is None:
            return Response({"detail": "Invalid 'to' date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if from_date and to_date and from_date > to_date:
            return Response({"detail": "'from' date cannot be after 'to' date."}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(get_public_schema_name()):
            rows = (
                _owner_reservations_queryset(
                    tenant.id,
                    status_filter=status_filter,
                    reminder_filter=reminder_filter,
                    search=search,
                    from_date=from_date,
                    to_date=to_date,
                )
                .order_by("-created_at")[:2000]
            )

            response = HttpResponse(content_type="text/csv; charset=utf-8")
            filename = f"{getattr(tenant, 'slug', 'tenant')}-reservations-{timezone.now():%Y%m%d}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            writer = csv.writer(response)
            writer.writerow(["id", "created_at", "status", "name", "phone", "email", "source", "notes"])
            for lead in rows:
                writer.writerow(
                    [
                        getattr(lead, "id", ""),
                        timezone.localtime(getattr(lead, "created_at", timezone.now())).isoformat()
                        if getattr(lead, "created_at", None)
                        else "",
                        getattr(lead, "status", ""),
                        getattr(lead, "name", ""),
                        getattr(lead, "phone", ""),
                        getattr(lead, "email", ""),
                        getattr(lead, "source", ""),
                        getattr(lead, "notes", ""),
                    ]
                )

        return response


class TierUpgradeRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)
        with schema_context(get_public_schema_name()):
            rows = (
                TierUpgradeRequest.objects.select_related(
                    "tenant",
                    "requester",
                    "approved_by",
                    "current_plan",
                    "target_plan",
                )
                .filter(tenant_id=tenant.id)
                .order_by("-requested_at")
            )
            data = TierUpgradeRequestSerializer(rows, many=True).data
        return Response(data)

    def post(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TierUpgradeRequestCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)

        try:
            upgrade_request = create_tier_upgrade_request(
                tenant=tenant,
                requester=request.user,
                target_plan_code=serializer.validated_data["target_plan"].code,
                payment_method=serializer.validated_data.get("payment_method", "cash"),
                payment_reference=serializer.validated_data.get("payment_reference", ""),
                customer_note=serializer.validated_data.get("customer_note", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_admin_action(
            action=AdminAuditLog.Actions.TIER_UPGRADE_REQUESTED,
            request=request,
            actor=request.user,
            tenant=upgrade_request.tenant,
            target_repr=f"tier-upgrade-request:{upgrade_request.id}",
            metadata={
                "current_plan": upgrade_request.current_plan.code,
                "target_plan": upgrade_request.target_plan.code,
                "payment_method": upgrade_request.payment_method,
            },
        )
        return Response(TierUpgradeRequestSerializer(upgrade_request).data, status=status.HTTP_201_CREATED)


class TierUpgradeTargetsView(APIView):
    permission_classes = [IsAuthenticated, IsTenantEditor]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant not resolved."}, status=status.HTTP_400_BAD_REQUEST)

        with schema_context(get_public_schema_name()):
            tenant_obj = Tenant.objects.select_related("plan").get(pk=tenant.id)
            current_plan = tenant_obj.plan
            pending_exists = TierUpgradeRequest.objects.filter(
                tenant_id=tenant_obj.id,
                status=TierUpgradeRequest.Status.PENDING,
            ).exists()

            plans = list(Plan.objects.all())
            targets = []
            for plan in plans:
                if not is_plan_upgrade(getattr(current_plan, "code", ""), getattr(plan, "code", "")):
                    continue
                targets.append(
                    TierUpgradeTargetSerializer.from_plan(
                        plan,
                        can_request=not pending_exists,
                    )
                )

            targets.sort(key=lambda item: (plan_tier_order(item["code"]), item["name"].lower()))

        return Response(
            {
                "current_tier_code": external_plan_code(getattr(current_plan, "code", "")),
                "current_tier_name": plan_display_name(
                    getattr(current_plan, "code", ""),
                    fallback=getattr(current_plan, "name", ""),
                ),
                "has_pending_request": pending_exists,
                "targets": targets,
            }
        )


class AdminTierUpgradeRequestListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        status_filter = (request.query_params.get("status") or "").strip().lower()
        with schema_context(get_public_schema_name()):
            rows = TierUpgradeRequest.objects.select_related(
                "tenant",
                "requester",
                "approved_by",
                "current_plan",
                "target_plan",
            ).order_by("-requested_at")
            if status_filter:
                rows = rows.filter(status=status_filter)
            data = TierUpgradeRequestSerializer(rows[:200], many=True).data
        return Response(data)


class AdminTierUpgradeRequestDecisionView(APIView):
    permission_classes = [IsPlatformAdmin]

    def put(self, request, request_id):
        serializer = TierUpgradeDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        admin_note = serializer.validated_data.get("admin_note", "")
        payment_reference = serializer.validated_data.get("payment_reference", "")

        try:
            result = decide_tier_upgrade_request(
                request_id=request_id,
                decision=decision,
                actor=request.user,
                admin_note=admin_note,
                payment_reference=payment_reference,
            )
        except TierUpgradeRequest.DoesNotExist:
            return Response({"detail": "Upgrade request not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        action = (
            AdminAuditLog.Actions.TIER_UPGRADE_APPROVED
            if decision == "approve"
            else AdminAuditLog.Actions.TIER_UPGRADE_REJECTED
        )
        log_admin_action(
            action=action,
            request=request,
            actor=request.user,
            tenant=result.tenant,
            target_repr=f"tier-upgrade-request:{result.upgrade_request.id}",
            metadata={
                "decision": decision,
                "previous_plan": getattr(result.previous_plan, "code", ""),
                "new_plan": getattr(result.new_plan, "code", ""),
                "payment_reference": (payment_reference or "").strip(),
            },
        )
        return Response(
            {
                "detail": (
                    f"Tenant upgraded to {result.new_plan.name}."
                    if decision == "approve"
                    else "Upgrade request rejected."
                ),
                "request": TierUpgradeRequestSerializer(result.upgrade_request).data,
            },
            status=status.HTTP_200_OK,
        )
