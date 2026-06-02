"""Internal staff chat — one shared channel per restaurant (owner + staff).

Messages are persisted for history and broadcast in real time (`chat.message`) to
the tenant's owner/staff WebSocket group. Owner/staff only — same authorization as
the rest of the owner API.
"""
from django.db import connection
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from realtime.broadcast import broadcast

from .models import StaffMessage
from .permissions import IsTenantEditorOrReadOnly

_HISTORY_LIMIT = 50


def _schema():
    try:
        return connection.tenant.schema_name
    except Exception:
        return ""


def _serialize(msg):
    return {
        "id": msg.id,
        "author_name": msg.author_name,
        "body": msg.body,
        "created_at": msg.created_at.isoformat(),
    }


class StaffChatView(APIView):
    """GET recent messages (chronological) / POST a new message."""

    permission_classes = [IsAuthenticated, IsTenantEditorOrReadOnly]

    def get(self, request):
        # Newest 50, returned oldest-first for natural chat order.
        msgs = list(StaffMessage.objects.all()[:_HISTORY_LIMIT])
        msgs.reverse()
        return Response({"results": [_serialize(m) for m in msgs]})

    def post(self, request):
        body = str(request.data.get("body") or "").strip()[:1000]
        if not body:
            return Response({"detail": "Message is empty.", "code": "empty"}, status=400)
        user = request.user
        author_name = (
            (getattr(user, "get_full_name", lambda: "")() or "").strip()
            or getattr(user, "first_name", "")
            or (getattr(user, "email", "") or "").split("@")[0]
            or "Staff"
        )
        msg = StaffMessage.objects.create(author=user, author_name=author_name[:80], body=body)
        broadcast(_schema(), "owner", "chat.message", _serialize(msg))
        return Response(_serialize(msg), status=201)
