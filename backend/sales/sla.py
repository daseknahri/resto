from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


RESERVATION_SOURCES = ("table_reservation", "reservation", "reserve_table")
RESERVATION_STATUS_NEW = "new"

SLA_STATE_NOT_APPLICABLE = "not_applicable"
SLA_STATE_RESOLVED = "resolved"
SLA_STATE_ON_TRACK = "on_track"
SLA_STATE_DUE_SOON = "due_soon"
SLA_STATE_OVERDUE = "overdue"


def reservation_sla_minutes() -> int:
    raw = getattr(settings, "RESERVATION_SLA_NEW_MINUTES", 30)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 30
    return max(1, value)


def reservation_due_soon_minutes() -> int:
    raw = getattr(settings, "RESERVATION_SLA_DUE_SOON_MINUTES", 10)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 10
    return max(1, value)


def is_reservation_source(source: str) -> bool:
    return (source or "").strip().lower() in RESERVATION_SOURCES


def reservation_follow_up_due_at(created_at):
    if created_at is None:
        return None
    return created_at + timedelta(minutes=reservation_sla_minutes())


def reservation_overdue_cutoff(now=None):
    current_time = now or timezone.now()
    return current_time - timedelta(minutes=reservation_sla_minutes())


def reservation_due_soon_cutoff(now=None):
    current_time = now or timezone.now()
    due_soon_start_minutes = max(0, reservation_sla_minutes() - reservation_due_soon_minutes())
    return current_time - timedelta(minutes=due_soon_start_minutes)


def reservation_sla_snapshot(*, source: str, status: str, created_at, now=None) -> dict:
    due_at = reservation_follow_up_due_at(created_at)
    if not is_reservation_source(source) or due_at is None:
        return {
            "follow_up_due_at": None,
            "sla_state": SLA_STATE_NOT_APPLICABLE,
            "sla_minutes_overdue": 0,
            "sla_seconds_remaining": 0,
        }

    if (status or "").strip().lower() != RESERVATION_STATUS_NEW:
        return {
            "follow_up_due_at": due_at,
            "sla_state": SLA_STATE_RESOLVED,
            "sla_minutes_overdue": 0,
            "sla_seconds_remaining": 0,
        }

    current_time = now or timezone.now()
    delta_seconds = int((due_at - current_time).total_seconds())
    if delta_seconds <= 0:
        overdue_seconds = abs(delta_seconds)
        return {
            "follow_up_due_at": due_at,
            "sla_state": SLA_STATE_OVERDUE,
            "sla_minutes_overdue": max(1, overdue_seconds // 60) if overdue_seconds else 0,
            "sla_seconds_remaining": 0,
        }

    due_soon_seconds = reservation_due_soon_minutes() * 60
    return {
        "follow_up_due_at": due_at,
        "sla_state": SLA_STATE_DUE_SOON if delta_seconds <= due_soon_seconds else SLA_STATE_ON_TRACK,
        "sla_minutes_overdue": 0,
        "sla_seconds_remaining": delta_seconds,
    }
