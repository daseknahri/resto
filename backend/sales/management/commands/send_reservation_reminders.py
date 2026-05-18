"""
Management command: send_reservation_reminders

Designed to run on a cron schedule (every hour is sufficient).
Finds all confirmed (WON) reservations with `booked_for` in the
1.5 – 2.5 hour window from now whose reminder has not been sent yet,
then sends each customer an email (and an SMS when Twilio is configured)
and stamps `Lead.reminder_sent_at`.

Usage:
    python manage.py send_reservation_reminders
    python manage.py send_reservation_reminders --dry-run
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from sales.models import Lead
from sales.sla import RESERVATION_SOURCES
from tenancy.models import Profile, Tenant

logger = logging.getLogger(__name__)

# Send the reminder when the reservation is this many hours away.
REMINDER_WINDOW_CENTER_HOURS = 2.0
REMINDER_WINDOW_HALF_HOURS = 0.5  # → window = [1.5 h, 2.5 h]


def _reminder_window() -> tuple:
    now = timezone.now()
    center = timedelta(hours=REMINDER_WINDOW_CENTER_HOURS)
    half = timedelta(hours=REMINDER_WINDOW_HALF_HOURS)
    return now + center - half, now + center + half


def _profile_reminders_enabled(tenant: Tenant) -> bool:
    """Return True when the tenant's Profile has reservation_reminders_enabled set."""
    try:
        with schema_context(tenant.schema_name):
            profile = Profile.objects.filter(tenant=tenant).first()
            return bool(profile and getattr(profile, "reservation_reminders_enabled", False))
    except Exception:
        logger.exception("Error reading profile for tenant %s", tenant.slug)
        return False


def _tenant_name(tenant: Tenant) -> str:
    return tenant.name or tenant.slug


def _send_reminder_email(lead: Lead, tenant_name: str) -> bool:
    """Send a reminder email to the customer. Returns True on success."""
    if not (lead.email or "").strip():
        return False

    booked_at_str = ""
    if lead.booked_for:
        booked_at_str = lead.booked_for.strftime("%A, %B %-d at %-I:%M %p")

    subject = f"Reminder: your reservation at {tenant_name}"
    body_lines = [
        f"Hi {lead.name},",
        "",
        f"This is a friendly reminder that you have a reservation at {tenant_name}",
    ]
    if booked_at_str:
        body_lines.append(f"scheduled for {booked_at_str}.")
    if lead.party_size:
        body_lines.append(f"Party size: {lead.party_size} guest(s).")
    body_lines += [
        "",
        "We look forward to seeing you!",
        "",
        f"— {tenant_name}",
    ]

    try:
        sent = send_mail(
            subject,
            "\n".join(body_lines),
            None,
            [lead.email.strip()],
            fail_silently=getattr(settings, "EMAIL_FAIL_SILENTLY", True),
        )
        if sent >= 1:
            logger.info("Reminder email sent to %s (lead %s)", lead.email, lead.pk)
            return True
        logger.warning("Reminder email not sent for lead %s (send_mail returned 0)", lead.pk)
        return False
    except Exception:
        logger.exception("Error sending reminder email for lead %s", lead.pk)
        return False


def _send_reminder_sms(lead: Lead, tenant_name: str) -> bool:
    """Send a reminder SMS to the customer. Returns True on success."""
    if not (lead.phone or "").strip():
        return False

    booked_at_str = ""
    if lead.booked_for:
        booked_at_str = lead.booked_for.strftime("%b %-d at %-I:%M %p")

    body = f"Hi {lead.name}! Reminder: you have a reservation at {tenant_name}"
    if booked_at_str:
        body += f" on {booked_at_str}"
    body += ". We look forward to seeing you!"

    try:
        # Reuse the sms helper from menu.sms — it normalises the phone and
        # handles Twilio credentials gracefully.
        from menu.sms import _credentials, _normalize_phone  # noqa: PLC0415

        import requests as _requests  # noqa: PLC0415

        creds = _credentials()
        if creds is None:
            logger.debug("Reminder SMS skipped for lead %s: Twilio not configured.", lead.pk)
            return False

        to_phone = _normalize_phone(lead.phone)
        if not to_phone:
            logger.warning("Reminder SMS skipped for lead %s: invalid phone %r", lead.pk, lead.phone)
            return False

        sid, token, from_num = creds
        resp = _requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"To": to_phone, "From": from_num, "Body": body},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("Reminder SMS sent to %s (lead %s) via Twilio", to_phone, lead.pk)
            return True
        logger.warning(
            "Reminder SMS failed for lead %s: Twilio %s — %s",
            lead.pk,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception:
        logger.exception("Error sending reminder SMS for lead %s", lead.pk)
        return False


class Command(BaseCommand):
    help = (
        "Send pre-reservation reminder emails/SMS to customers whose confirmed "
        "reservation is approximately 2 hours away and have not yet been reminded."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without actually sending or updating the DB.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        window_start, window_end = _reminder_window()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Reservation reminders — window: "
                f"{window_start.strftime('%H:%M')} – {window_end.strftime('%H:%M')} UTC"
                + (" [DRY RUN]" if dry_run else "")
            )
        )

        active_tenants = Tenant.objects.filter(
            is_active=True,
            lifecycle_status=Tenant.LifecycleStatus.ACTIVE,
        ).exclude(schema_name="public")

        total_sent = 0
        total_skipped = 0

        for tenant in active_tenants:
            if not _profile_reminders_enabled(tenant):
                continue

            eligible_leads = Lead.objects.filter(
                tenant_id=tenant.pk,
                source__in=RESERVATION_SOURCES,
                status=Lead.Status.WON,
                booked_for__gte=window_start,
                booked_for__lte=window_end,
                reminder_sent_at__isnull=True,
            )

            for lead in eligible_leads:
                tenant_name = _tenant_name(tenant)
                self.stdout.write(
                    f"  → {tenant.slug} | lead #{lead.pk} "
                    f"({lead.name}, {lead.booked_for})"
                )

                if dry_run:
                    self.stdout.write(self.style.WARNING("    [DRY RUN] skipped"))
                    total_skipped += 1
                    continue

                email_ok = _send_reminder_email(lead, tenant_name)
                sms_ok = _send_reminder_sms(lead, tenant_name)

                if email_ok or sms_ok:
                    lead.reminder_sent_at = timezone.now()
                    lead.save(update_fields=["reminder_sent_at", "updated_at"])
                    total_sent += 1
                    channels = ", ".join(
                        ch for ch, ok in [("email", email_ok), ("SMS", sms_ok)] if ok
                    )
                    self.stdout.write(self.style.SUCCESS(f"    sent via {channels}"))
                else:
                    # No contact details or all channels failed — still stamp
                    # so we don't retry on the next run for a lead with no contact info.
                    lead.reminder_sent_at = timezone.now()
                    lead.save(update_fields=["reminder_sent_at", "updated_at"])
                    total_skipped += 1
                    self.stdout.write(self.style.WARNING("    no channel sent (no contact info or all failed)"))

        label = "dry-run skipped" if dry_run else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_sent} reminder(s) {label}, {total_skipped} skipped."
            )
        )
