"""Waiter-call endpoints.

Flow: a dine-in customer raises a call from their table QR (public, throttled) →
we record it and broadcast `waiter.call` to the tenant's owner/staff sockets →
staff acknowledge it, which broadcasts `waiter.call.ack` so every device clears.
"""
from datetime import timedelta

from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from realtime.broadcast import broadcast

from .models import SectionServer, TableLink, WaiterCall
from .permissions import IsTenantEditorOrReadOnly
from .throttles import WaiterCallThrottle

# Collapse repeat presses from the same table within this window into the existing
# pending call, so staff aren't flooded.
_DEDUPE_WINDOW = timedelta(seconds=90)


def _schema():
    try:
        return connection.tenant.schema_name
    except Exception:
        return ""


def _serialize(call):
    return {
        "id": call.id,
        "table_label": call.table_label,
        "table_slug": call.table_slug,
        "note": call.note,
        "status": call.status,
        "created_at": call.created_at.isoformat(),
    }


class WaiterCallCreateView(APIView):
    """POST /api/waiter-call/ — raise a call from a table QR. Public + throttled."""

    permission_classes = [AllowAny]
    throttle_classes = [WaiterCallThrottle]

    def post(self, request):
        table_slug = str(request.data.get("table") or request.data.get("table_slug") or "").strip()
        note = str(request.data.get("note") or "").strip()[:200]
        if not table_slug:
            return Response({"detail": "A table is required.", "code": "table_required"}, status=400)

        # Must be a real, active table — prevents arbitrary spam to staff.
        table = TableLink.objects.filter(slug=table_slug, is_active=True).first()
        if table is None:
            return Response({"detail": "Unknown table.", "code": "unknown_table"}, status=400)

        # Dedupe: reuse a recent still-pending call for this table.
        since = timezone.now() - _DEDUPE_WINDOW
        existing = (
            WaiterCall.objects.filter(
                table_slug=table.slug, status=WaiterCall.Status.PENDING, created_at__gte=since
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            return Response(_serialize(existing), status=status.HTTP_200_OK)

        call = WaiterCall.objects.create(
            table_label=table.label, table_slug=table.slug, note=note
        )
        broadcast(_schema(), "owner", "waiter.call", {
            "id": call.id,
            "table_label": call.table_label,
            "note": call.note,
        })
        return Response(_serialize(call), status=status.HTTP_201_CREATED)


def _section_slugs_for(user):
    """(my_slugs, claimed_slugs) for hard section routing. claimed_slugs empty
    means the floor isn't divided yet → no filtering (everyone sees all)."""
    uid = getattr(user, "id", None)
    my_section_ids = list(
        SectionServer.objects.filter(user_id=uid).values_list("section_id", flat=True)
    )
    my_slugs = set(
        TableLink.objects.filter(section_id__in=my_section_ids).values_list("slug", flat=True)
    ) if my_section_ids else set()
    claimed_section_ids = set(SectionServer.objects.values_list("section_id", flat=True))
    claimed_slugs = set(
        TableLink.objects.filter(section_id__in=claimed_section_ids).values_list("slug", flat=True)
    ) if claimed_section_ids else set()
    return my_slugs, claimed_slugs


class OwnerWaiterCallListView(APIView):
    """GET /api/owner/waiter-calls/ — pending calls for this tenant.

    Hard section routing: a waiter sees only calls for tables in their sections
    (plus orphan tables with no assigned server). Owners/managers see all.
    """

    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def get(self, request):
        from tenancy.capabilities import tenant_capability_enabled
        if not tenant_capability_enabled(getattr(request, "tenant", None), "waiter"):
            return Response(
                {"detail": "Waiter features are not available for this business.",
                 "code": "waiter_unavailable"},
                status=403,
            )
        calls = list(WaiterCall.objects.filter(status=WaiterCall.Status.PENDING).order_by("created_at"))

        from .views import _is_tenant_owner  # lazy import avoids a heavy module load cycle
        if not _is_tenant_owner(request):
            my_slugs, claimed_slugs = _section_slugs_for(request.user)
            if claimed_slugs:
                calls = [
                    c for c in calls
                    if (not c.table_slug) or c.table_slug in my_slugs or c.table_slug not in claimed_slugs
                ]
        return Response({"results": [_serialize(c) for c in calls]})


class OwnerWaiterCallAcknowledgeView(APIView):
    """POST /api/owner/waiter-calls/<id>/acknowledge/ — clear a call for all staff."""

    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def post(self, request, call_id):
        from tenancy.capabilities import tenant_capability_enabled
        if not tenant_capability_enabled(getattr(request, "tenant", None), "waiter"):
            return Response(
                {"detail": "Waiter features are not available for this business.",
                 "code": "waiter_unavailable"},
                status=403,
            )
        call = WaiterCall.objects.filter(pk=call_id).first()
        if call is None:
            return Response({"detail": "Not found.", "code": "not_found"}, status=404)
        if call.status != WaiterCall.Status.ACKNOWLEDGED:
            call.status = WaiterCall.Status.ACKNOWLEDGED
            call.acknowledged_at = timezone.now()
            call.acknowledged_by = request.user if getattr(request.user, "is_authenticated", False) else None
            call.save(update_fields=["status", "acknowledged_at", "acknowledged_by"])
            broadcast(_schema(), "owner", "waiter.call.ack", {"id": call.id})
        return Response(_serialize(call))
