"""R18 — Customer PII erasure / anonymization management command.

GDPR / right-to-erasure: anonymize a Customer in-place across all schemas.
The Customer ROW is NEVER deleted (CASCADE would destroy the financial ledger).
PII is blanked; financial rows (WalletTransaction, Order totals, etc.) are retained.

Usage
-----
    # Dry-run (default) — shows what would be erased, writes nothing:
    python manage.py erase_customer 42

    # Apply the erasure:
    python manage.py erase_customer 42 --force-erase

    # Bypass Phase 0 guards (open orders etc.):
    python manage.py erase_customer 42 --force-erase --force

    # Dry-run with guard-bypass:
    python manage.py erase_customer 42 --force

IMPORTANT: snapshot original_phone + original_email BEFORE scrubbing the Customer
row — they are needed to match NotificationLog.recipient / WaitlistEntry / Lead rows
that carry no Customer FK.
"""
from __future__ import annotations

import sys
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# Terminal Order statuses (orders in these states are not "open").
TERMINAL_ORDER_STATUSES = {"completed", "cancelled"}

# Epsilon for wallet balance zero-check (avoid floating-point false positives).
WALLET_EPSILON = Decimal("0.01")


class Command(BaseCommand):
    help = "Anonymize a customer's PII in-place across all schemas (GDPR right to erasure)."

    def add_arguments(self, parser):
        parser.add_argument(
            "customer_id",
            nargs="?",
            type=int,
            default=None,
            help="ID of the Customer to erase.",
        )
        parser.add_argument(
            "--customer-id",
            dest="customer_id_opt",
            type=int,
            default=None,
            help="Alternative: --customer-id=<id>",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report counts and what would be erased; write nothing, no audit log.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Skip Phase 0 guard-rail checks (open orders, pending charges, non-zero balance).",
        )
        parser.add_argument(
            "--force-erase",
            action="store_true",
            default=False,
            help=(
                "Actually perform the erasure. Without this flag the command runs in "
                "dry-run mode even if --dry-run is not passed (safety default)."
            ),
        )

    def handle(self, *args, **options):  # noqa: C901 — large but linear
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

        # ── Resolve customer_id ────────────────────────────────────────────────
        customer_id: int | None = options.get("customer_id") or options.get("customer_id_opt")
        if customer_id is None:
            raise CommandError(
                "Provide a customer ID as a positional argument or via --customer-id."
            )

        dry_run: bool = options["dry_run"] or not options["force_erase"]
        force: bool = options["force"]

        mode_label = "DRY-RUN" if dry_run else "ERASE"
        self.stdout.write(f"[{mode_label}] erase_customer id={customer_id}")

        # ── Fetch customer ─────────────────────────────────────────────────────
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise CommandError(f"Customer with id={customer_id} does not exist.")

        # Snapshot PII BEFORE any scrubbing (needed for cross-schema matching).
        original_phone: str | None = customer.phone
        original_email: str = customer.email

        # ── Phase 0 — Guard rails ──────────────────────────────────────────────
        if not force:
            errors = _check_guard_rails(customer, customer_id)
            if errors:
                for msg in errors:
                    self.stderr.write(self.style.ERROR(f"  GUARD: {msg}"))
                raise CommandError(
                    "Erasure refused due to guard-rail failures above. "
                    "Resolve them or pass --force to bypass."
                )
            self.stdout.write("  Phase 0 guards: OK")

        # ── Gather counts for dry-run / reporting ──────────────────────────────
        counts: dict[str, int] = {}

        # Public schema counts
        counts["wallet_transactions"] = WalletTransaction.objects.filter(customer_id=customer_id).count()
        counts["tenant_float_transactions"] = TenantFloatTransaction.objects.filter(customer_id=customer_id).count()
        counts["order_refs"] = CustomerOrderRef.objects.filter(customer_id=customer_id).count()
        counts["push_subscriptions"] = CustomerPushSubscription.objects.filter(customer_id=customer_id).count()
        counts["saved_addresses"] = SavedAddress.objects.filter(customer_id=customer_id).count()
        counts["winback_nudges"] = WinbackNudge.objects.filter(customer_id=customer_id).count()
        counts["customer_ratings"] = CustomerRating.objects.filter(customer_id=customer_id).count()
        counts["delivery_jobs_as_driver"] = DeliveryJob.objects.filter(driver_id=customer_id).count()
        counts["ride_requests"] = RideRequest.objects.filter(rider_id=customer_id).count()

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
            counts["notification_logs"] = NotificationLog.objects.filter(notif_q).count()
        else:
            counts["notification_logs"] = 0

        # Per-tenant counts
        tenants = list(Tenant.objects.all())
        counts["tenants"] = len(tenants)
        counts["orders_total"] = 0
        counts["ratings_total"] = 0
        counts["customer_notes_total"] = 0
        counts["waitlist_entries_total"] = 0

        tenant_order_numbers: dict[int, list[str]] = {}  # tenant.id -> [order_number]

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    from menu.models import CustomerNote, Order, Rating, WaitlistEntry

                    tenant_orders = list(
                        Order.objects.filter(customer_id=customer_id).values_list("order_number", flat=True)
                    )
                    tenant_order_numbers[tenant.id] = tenant_orders
                    counts["orders_total"] += len(tenant_orders)
                    counts["ratings_total"] += Rating.objects.filter(customer_id=customer_id).count()
                    counts["customer_notes_total"] += CustomerNote.objects.filter(customer_id=customer_id).count()

                    wl_q = _waitlist_q(original_phone, original_email)
                    if wl_q is not None:
                        counts["waitlist_entries_total"] += WaitlistEntry.objects.filter(wl_q).count()
            except Exception as exc:
                self.stdout.write(f"  [warn] tenant {tenant.slug}: {exc}")

        # Phase 3 — sales (public schema)
        from sales.models import Lead, ReservationReminder
        lead_q = _lead_q(original_phone, original_email)
        if lead_q is not None:
            matched_leads = list(Lead.objects.filter(lead_q).values_list("id", flat=True))
            counts["leads"] = len(matched_leads)
            counts["reservation_reminders"] = ReservationReminder.objects.filter(
                lead_id__in=matched_leads
            ).count()
        else:
            counts["leads"] = 0
            counts["reservation_reminders"] = 0
            matched_leads = []

        # Print summary
        self.stdout.write("  Counts:")
        for k, v in counts.items():
            self.stdout.write(f"    {k}: {v}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY-RUN] No changes written. Re-run with --force-erase to apply."
                )
            )
            return

        # ══════════════════════════════════════════════════════════════════════
        # WRITE PATH
        # ══════════════════════════════════════════════════════════════════════

        # ── Phase 1 — Public schema (one atomic transaction) ──────────────────
        with transaction.atomic():
            # 1a. Scrub Customer PII fields in-place.
            Customer.objects.filter(pk=customer_id).update(
                phone=None,
                email="",
                name="",
                google_sub=None,
                driver_lat=None,
                driver_lng=None,
                driver_vehicle="",
                driver_vehicle_type="",
                driver_licence_url="",
                driver_insurance_url="",
                phone_verified=False,
                email_verified=False,
            )

            # 1b. Scrub WalletTransaction.note (retain rows — ledger integrity).
            WalletTransaction.objects.filter(customer_id=customer_id).update(note="")

            # 1c. Scrub TenantFloatTransaction.note where customer FK matches.
            TenantFloatTransaction.objects.filter(customer_id=customer_id).update(note="")

            # 1d. Scrub CustomerOrderRef snapshot fields (retain row for ledger cross-ref).
            CustomerOrderRef.objects.filter(customer_id=customer_id).update(
                restaurant_name="",
                restaurant_slug="",
                items_snapshot=[],
            )

            # 1e. Scrub RideRequest PII (rider=this customer).
            RideRequest.objects.filter(rider_id=customer_id).update(
                pickup_address="",
                dropoff_address="",
                recipient_name="",
                recipient_phone="",
                package_note="",
                delivery_code="",
                pickup_lat=None,
                pickup_lng=None,
                dropoff_lat=None,
                dropoff_lng=None,
            )

            # Scrub the driver-side notes on jobs THIS customer drove. Do NOT touch
            # delivery_address/lat/lng here — on a driven job those belong to the
            # ORDER's customer (a third party); the erased customer's OWN delivery
            # address is handled in Phase 2 via their order numbers.
            DeliveryJob.objects.filter(driver_id=customer_id).update(
                failure_note="",
                driver_customer_note="",
            )

            # Scrub DriverPayout.note (driver=this customer); RETAIN rows (financial).
            DriverPayout.objects.filter(driver_id=customer_id).update(note="")

            # Unlink this customer as DRIVER on rides they drove (rider-side PII on
            # those rows belongs to OTHER riders — leave it; just drop the FK).
            RideRequest.objects.filter(driver_id=customer_id).update(driver=None)

            # Scrub WalletChargeRequest.note (RETAIN rows — financial).
            WalletChargeRequest.objects.filter(customer_id=customer_id).update(note="")

            # 1g. Blank NotificationLog.recipient where it matches original phone/email.
            if notification_q_parts:
                from django.db.models import Q as _Q
                notif_q2 = _Q()
                for val in notification_q_parts:
                    notif_q2 |= _Q(recipient=val)
                NotificationLog.objects.filter(notif_q2).update(recipient="")

            # 1h. DELETE: CustomerPushSubscription, SavedAddress, WinbackNudge,
            # CustomerRating, CustomerServiceProfile (per-service prefs).
            CustomerPushSubscription.objects.filter(customer_id=customer_id).delete()
            SavedAddress.objects.filter(customer_id=customer_id).delete()
            WinbackNudge.objects.filter(customer_id=customer_id).delete()
            CustomerRating.objects.filter(customer_id=customer_id).delete()
            CustomerServiceProfile.objects.filter(customer_id=customer_id).delete()

        self.stdout.write("  Phase 1 (public schema): done")

        # ── Phase 2 — Per-tenant schemas ──────────────────────────────────────
        scrubbed_tenants = 0
        total_orders_scrubbed = 0
        failed_tenants: list[str] = []

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    with transaction.atomic():
                        from menu.models import CustomerNote, Order, Rating, WaitlistEntry

                        order_nums = tenant_order_numbers.get(tenant.id, [])

                        # 2a. Scrub Order PII fields; retain all financial fields.
                        if order_nums:
                            Order.objects.filter(customer_id=customer_id).update(
                                customer=None,
                                customer_name="",
                                customer_phone="",
                                customer_note="",
                                delivery_address="",
                                delivery_location_url="",
                                delivery_lat=None,
                                delivery_lng=None,
                                delivery_code="",
                                delivery_proof_photo_url="",
                            )
                            total_orders_scrubbed += len(order_nums)

                        # 2b. Scrub Rating.comment; set customer FK to None.
                        Rating.objects.filter(customer_id=customer_id).update(
                            customer=None,
                            comment="",
                        )

                        # 2c. DELETE CustomerNote (private owner notes about this customer).
                        CustomerNote.objects.filter(customer_id=customer_id).delete()

                        # 2d. Scrub DeliveryJob delivery_address where order_number
                        #     belongs to this customer in this tenant.
                        if order_nums:
                            DeliveryJob.objects.filter(
                                tenant_id=tenant.id,
                                order_number__in=order_nums,
                            ).update(
                                delivery_address="",
                                delivery_lat=None,
                                delivery_lng=None,
                                customer_driver_note="",
                            )

                        # 2e. Scrub WaitlistEntry matched by original phone/email.
                        wl_q = _waitlist_q(original_phone, original_email)
                        if wl_q is not None:
                            WaitlistEntry.objects.filter(wl_q).update(
                                name="",
                                phone="",
                                email="",
                                notes="",
                            )

                        scrubbed_tenants += 1
            except Exception as exc:
                failed_tenants.append(tenant.slug)
                self.stderr.write(
                    self.style.ERROR(f"  [error] tenant {tenant.slug} phase 2 failed: {exc}")
                )

        self.stdout.write(f"  Phase 2 (per-tenant): {scrubbed_tenants}/{len(tenants)} tenants")

        # ── Phase 3 — Sales / reservations (matched by original phone/email) ──
        if lead_q is not None:
            from sales.models import Lead, ReservationReminder, ReservationTimelineEvent
            with transaction.atomic():
                matched_leads_qs = Lead.objects.filter(lead_q)
                matched_lead_ids = list(matched_leads_qs.values_list("id", flat=True))

                # Blank Lead PII.
                matched_leads_qs.update(
                    name="",
                    phone="",
                    email="",
                    notes="",
                    cancel_token=None,
                )
                if matched_lead_ids:
                    # Staff free-text timeline notes may name/contact the customer.
                    ReservationTimelineEvent.objects.filter(
                        lead_id__in=matched_lead_ids
                    ).update(note="")
                    # Delete reminders (phone/message/whatsapp_link).
                    ReservationReminder.objects.filter(lead_id__in=matched_lead_ids).delete()

        self.stdout.write("  Phase 3 (sales/leads): done")

        # If any tenant failed in Phase 2, do NOT claim success: skip the completion
        # audit (it would falsely assert full erasure) and exit non-zero. Public + all
        # reachable tenant PII was still scrubbed; re-run (idempotent) after fixing the
        # tenant so the erasure completes and the audit is written.
        if failed_tenants:
            raise CommandError(
                "Erasure INCOMPLETE — phase 2 failed for tenant(s): "
                + ", ".join(failed_tenants)
                + ". Re-run after resolving (the command is idempotent); no completion "
                "audit was written."
            )

        # ── Phase 4 — Audit log ────────────────────────────────────────────────
        from sales.audit import log_admin_action
        from sales.models import AdminAuditLog

        log_admin_action(
            action=AdminAuditLog.Actions.CUSTOMER_ERASED,
            target_repr=f"customer_id={customer_id}",
            metadata={
                "customer_id": customer_id,
                "tenants_scrubbed": scrubbed_tenants,
                "orders_scrubbed": total_orders_scrubbed,
                "actor": "management_command:erase_customer",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[DONE] Customer {customer_id} anonymized. "
                f"{scrubbed_tenants} tenant(s), {total_orders_scrubbed} order(s) scrubbed."
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_guard_rails(customer, customer_id: int) -> list[str]:
    """Return a list of violation messages (empty = all clear)."""
    from accounts.models import DriverCashoutRequest, WalletChargeRequest
    from django_tenants.utils import schema_context
    from tenancy.models import Tenant

    errors: list[str] = []

    # Guard 1: no open orders across ALL tenant schemas.
    open_orders: list[str] = []
    for tenant in Tenant.objects.all():
        try:
            with schema_context(tenant.schema_name):
                from menu.models import Order
                qs = Order.objects.filter(customer_id=customer_id).exclude(
                    status__in=TERMINAL_ORDER_STATUSES
                )
                for o in qs.values_list("order_number", "status"):
                    open_orders.append(f"{tenant.slug}/{o[0]} ({o[1]})")
        except Exception:
            pass  # skip broken schemas; don't block erasure for infrastructure issues

    if open_orders:
        errors.append(
            f"Customer has {len(open_orders)} non-terminal order(s): "
            + ", ".join(open_orders[:5])
            + (" …" if len(open_orders) > 5 else "")
        )

    # Guard 2: no PENDING WalletChargeRequest.
    pending_charges = WalletChargeRequest.objects.filter(
        customer_id=customer_id,
        status=WalletChargeRequest.Status.PENDING,
    ).count()
    if pending_charges:
        errors.append(f"Customer has {pending_charges} pending WalletChargeRequest(s).")

    # Guard 3: no PENDING DriverCashoutRequest.
    pending_cashouts = DriverCashoutRequest.objects.filter(
        driver_id=customer_id,
        status=DriverCashoutRequest.Status.PENDING,
    ).count()
    if pending_cashouts:
        errors.append(f"Customer has {pending_cashouts} pending DriverCashoutRequest(s).")

    # Guard 4: wallet balance must be (near-)zero.
    if abs(customer.wallet_balance) > WALLET_EPSILON:
        errors.append(
            f"Customer wallet_balance is {customer.wallet_balance} (must be 0 ± {WALLET_EPSILON})."
        )

    return errors


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
