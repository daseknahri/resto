"""R18b — Customer PII export (GDPR right-to-access / export-before-erase).

Read-only counterpart to ``erase_customer``: collects all personal data held
about ONE customer — across the public schema and every tenant schema — and
writes it out as a single JSON document. Performs NO writes, deletes, or
schema mutations of any kind; safe to run against production at any time.

Mirrors erase_customer's identifier resolution, tenant iteration, and
phone/email cross-schema matching EXACTLY so the export always reflects the
same footprint the erase command would touch (mint an export just before
erasing, or on its own for a data subject access request).

Usage
-----
    # Print JSON to stdout:
    python manage.py export_customer 42

    # Write JSON to a file:
    python manage.py export_customer 42 --output customer_42_export.json

    # Alternative id form:
    python manage.py export_customer --customer-id=42
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder


class Command(BaseCommand):
    help = "Export a customer's personal data as JSON (GDPR right-to-access / export-before-erase). Read-only."

    def add_arguments(self, parser):
        parser.add_argument(
            "customer_id",
            nargs="?",
            type=int,
            default=None,
            help="ID of the Customer to export.",
        )
        parser.add_argument(
            "--customer-id",
            dest="customer_id_opt",
            type=int,
            default=None,
            help="Alternative: --customer-id=<id>",
        )
        parser.add_argument(
            "--output",
            dest="output",
            type=str,
            default=None,
            help="Path to write the JSON export to. Defaults to stdout.",
        )

    def handle(self, *args, **options):  # noqa: C901 — large but linear, mirrors erase_customer
        from accounts.models import (
            Customer,
            CustomerOrderRef,
            CustomerPushSubscription,
            CustomerRating,
            CustomerServiceProfile,
            DeliveryJob,
            DriverCashoutRequest,
            DriverPayout,
            NotificationLog,
            RideRequest,
            SavedAddress,
            TenantFloatTransaction,
            WalletChargeRequest,
            WalletTransaction,
            WinbackNudge,
        )
        from django_tenants.utils import schema_context
        from tenancy.models import Tenant

        # ── Resolve customer_id (identical to erase_customer) ──────────────────
        customer_id: int | None = options.get("customer_id") or options.get("customer_id_opt")
        if customer_id is None:
            raise CommandError(
                "Provide a customer ID as a positional argument or via --customer-id."
            )

        self.stdout.write(f"[EXPORT] export_customer id={customer_id}")

        # ── Fetch customer (read-only) ──────────────────────────────────────────
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise CommandError(f"Customer with id={customer_id} does not exist.")

        # Snapshot phone/email for cross-schema matching (same fields erase_customer
        # snapshots — NotificationLog.recipient / WaitlistEntry / Lead carry no FK).
        original_phone: str | None = customer.phone
        original_email: str = customer.email

        export: dict = {"customer_id": customer_id}

        # ── Public-schema data ──────────────────────────────────────────────────
        export["customer"] = _model_to_dict(customer)
        export["wallet_transactions"] = _rows(WalletTransaction.objects.filter(customer_id=customer_id))
        export["tenant_float_transactions"] = _rows(
            TenantFloatTransaction.objects.filter(customer_id=customer_id)
        )
        export["order_refs"] = _rows(CustomerOrderRef.objects.filter(customer_id=customer_id))
        export["push_subscriptions"] = _rows(
            CustomerPushSubscription.objects.filter(customer_id=customer_id)
        )
        export["saved_addresses"] = _rows(SavedAddress.objects.filter(customer_id=customer_id))
        export["winback_nudges"] = _rows(WinbackNudge.objects.filter(customer_id=customer_id))
        export["customer_ratings"] = _rows(CustomerRating.objects.filter(customer_id=customer_id))
        export["service_profiles"] = _rows(CustomerServiceProfile.objects.filter(customer_id=customer_id))
        export["driver_payouts"] = _rows(DriverPayout.objects.filter(driver_id=customer_id))
        export["driver_cashout_requests"] = _rows(
            DriverCashoutRequest.objects.filter(driver_id=customer_id)
        )
        export["wallet_charge_requests"] = _rows(
            WalletChargeRequest.objects.filter(customer_id=customer_id)
        )
        export["delivery_jobs_as_driver"] = _rows(DeliveryJob.objects.filter(driver_id=customer_id))
        export["ride_requests_as_rider"] = _rows(RideRequest.objects.filter(rider_id=customer_id))
        export["ride_requests_as_driver"] = _rows(RideRequest.objects.filter(driver_id=customer_id))

        notification_q_parts = []
        if original_phone:
            notification_q_parts.append(original_phone)
        if original_email:
            notification_q_parts.append(original_email)

        if notification_q_parts:
            from django.db.models import Q
            notif_q = Q()
            for val in notification_q_parts:
                notif_q |= Q(recipient=val)
            export["notification_logs"] = _rows(NotificationLog.objects.filter(notif_q))
        else:
            export["notification_logs"] = []

        # ── Per-tenant data ──────────────────────────────────────────────────────
        tenants = list(Tenant.objects.all())
        export["tenants"] = {}

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    from menu.models import CustomerNote, Order, Rating, WaitlistEntry

                    tenant_export = {
                        "orders": _rows(Order.objects.filter(customer_id=customer_id)),
                        "ratings": _rows(Rating.objects.filter(customer_id=customer_id)),
                        "customer_notes": _rows(CustomerNote.objects.filter(customer_id=customer_id)),
                    }

                    wl_q = _waitlist_q(original_phone, original_email)
                    if wl_q is not None:
                        tenant_export["waitlist_entries"] = _rows(WaitlistEntry.objects.filter(wl_q))
                    else:
                        tenant_export["waitlist_entries"] = []

                    # Only include the tenant section if it actually holds data for
                    # this customer, keeping the export focused on the one customer.
                    if any(tenant_export.values()):
                        export["tenants"][tenant.slug] = tenant_export
            except Exception as exc:
                self.stdout.write(f"  [warn] tenant {tenant.slug}: {exc}")

        # ── Sales / reservations (matched by original phone/email) ─────────────
        from sales.models import Lead, ReservationReminder, ReservationTimelineEvent
        lead_q = _lead_q(original_phone, original_email)
        if lead_q is not None:
            matched_leads = list(Lead.objects.filter(lead_q))
            matched_lead_ids = [lead.pk for lead in matched_leads]
            export["leads"] = _rows(matched_leads)
            export["reservation_reminders"] = _rows(
                ReservationReminder.objects.filter(lead_id__in=matched_lead_ids)
            )
            export["reservation_timeline_events"] = _rows(
                ReservationTimelineEvent.objects.filter(lead_id__in=matched_lead_ids)
            )
        else:
            export["leads"] = []
            export["reservation_reminders"] = []
            export["reservation_timeline_events"] = []

        # ── Emit ─────────────────────────────────────────────────────────────────
        payload = json.dumps(export, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)

        output_path = options.get("output")
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(payload)
            self.stdout.write(
                self.style.SUCCESS(f"\n[DONE] Export for customer {customer_id} written to {output_path}")
            )
        else:
            self.stdout.write(payload)
            self.stdout.write(
                self.style.SUCCESS(f"\n[DONE] Export for customer {customer_id} complete.")
            )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _model_to_dict(instance) -> dict:
    """Serialize a single model instance's concrete fields to a plain dict."""
    return {
        field.name: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
    }


def _rows(queryset_or_list) -> list[dict]:
    """Serialize an iterable of model instances to a list of plain dicts."""
    return [_model_to_dict(obj) for obj in queryset_or_list]


def _waitlist_q(phone: str | None, email: str):
    """Build a Q for WaitlistEntry matching original phone or email."""
    from django.db.models import Q
    if not phone and not email:
        return None
    q = Q()
    if phone:
        q |= Q(phone=phone)
    if email:
        q |= Q(email=email)
    return q


def _lead_q(phone: str | None, email: str):
    """Build a Q for Lead matching original phone or email."""
    from django.db.models import Q
    if not phone and not email:
        return None
    q = Q()
    if phone:
        q |= Q(phone=phone)
    if email:
        q |= Q(email=email)
    return q
