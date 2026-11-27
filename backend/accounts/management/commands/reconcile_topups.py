"""Reconcile a Stripe Checkout top-up session that never credited the wallet.

Wave M M-07: if Stripe took the money but the webhook never landed (Stripe
outage, webhook secret rotation, a 4xx/5xx the operator missed), the customer
paid but has no credit and the status endpoint answers "unknown" forever.
This command closes that gap by hand, from Stripe's own record:

    python manage.py reconcile_topups <stripe_checkout_session_id>
    python manage.py reconcile_topups --list-uncredited
    python manage.py reconcile_topups --reconcile-all

Safety:
  * Credits ONLY when Stripe reports payment_status == "paid".
  * Credits ONLY when no TOPUP WalletTransaction with
    reference="stripe:<session_id>" exists yet — so a second run (or a late
    webhook) is a no-op, never a double credit. The credit itself also carries
    idempotency_key="reconciled:<session_id>" as a second guard.
  * Credits the SETTLED amount Stripe reports (amount_total, minor units) —
    never the client-echoed metadata amount (same rule as the webhook, MONEY-3).
  * Read-only by default for --list-uncredited (lists attempt rows with no
    TOPUP row); the credit path never runs without an explicit session id.
  * R6-19: --reconcile-all (hourly Beat, cron.reconcile_topups) closes the
    loop for good — a missed webhook (secret rotation, transient 5xx, expired
    retries) must not strand a paid top-up forever. It iterates the same
    uncredited CREATED attempts the list mode shows and credits the paid ones
    from Stripe's own record, one attempt at a time: a single bad session is
    logged on the payments channel and the batch continues. Each auto-credit
    is ALSO logged on the payments channel (money moved without a webhook —
    the operator should know the reconciler, not Stripe, credited it). The
    double-credit guards (TOPUP-row check + idempotency_key) are untouched,
    so a late webhook landing after the reconciler is still a no-op.

Requires the stripe SDK + PSP_STRIPE_SECRET_KEY. No live Stripe calls in tests
(mock the stripe module).
"""
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

payments_logger = logging.getLogger("payments")


class Command(BaseCommand):
    help = "Credit a paid Stripe Checkout top-up session that has no TOPUP ledger row yet (M-07)."

    def add_arguments(self, parser):
        parser.add_argument(
            "session_id", nargs="?",
            help="Stripe Checkout Session id (cs_...). Required unless --list-uncredited.",
        )
        parser.add_argument(
            "--list-uncredited", action="store_true",
            help="List top-up attempt rows with no TOPUP WalletTransaction yet (read-only).",
        )
        parser.add_argument(
            "--reconcile-all", action="store_true",
            help="Credit every uncredited CREATED attempt whose Stripe session is "
            "paid (hourly Beat mode, R6-19). One bad session is logged and "
            "skipped, never stops the batch.",
        )

    def handle(self, *args, **options):
        if options["list_uncredited"]:
            # _list_uncredited returns the count for direct callers; handle()
            # must return None — BaseCommand.execute writes a non-None return
            # value to stdout, and an int has no .endswith (Django raises).
            self._list_uncredited()
            return
        if options["reconcile_all"]:
            # R6-19: beat mode — every uncredited CREATED attempt, best-effort.
            self._reconcile_all()
            return

        session_id = options["session_id"]
        if not session_id:
            raise CommandError(
                "session_id is required (or pass --list-uncredited / --reconcile-all)."
            )

        status, amount, customer_id, payment_status = self._reconcile_session(session_id)
        if status == "already_credited":
            self.stdout.write(
                f"Session {session_id} already credited (TOPUP row exists) — nothing to do."
            )
        elif status == "not_paid":
            self.stdout.write(
                f"Session {session_id} payment_status={payment_status!r} — "
                "not paid, nothing credited."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Session {session_id} reconciled: credited {amount} to customer {customer_id}."
            ))
        return

    def _reconcile_session(self, session_id):
        """Credit one session if Stripe says paid and no TOPUP row exists yet.

        Returns (status, amount, customer_id, payment_status) with status in
        {"credited", "already_credited", "not_paid"}. The double-credit guards
        (TOPUP-row check + idempotency_key="reconciled:<session_id>") are
        unchanged from the M-07 single-session path — this is that path,
        factored out so --reconcile-all can call it per attempt. Lookup and
        metadata problems raise CommandError (the caller decides: abort for a
        single session, log-and-continue for the batch).
        """
        try:
            import stripe as _stripe
        except ImportError:
            raise CommandError("stripe SDK is not installed; cannot reconcile from Stripe.")
        if not getattr(settings, "PSP_STRIPE_SECRET_KEY", ""):
            raise CommandError("PSP_STRIPE_SECRET_KEY is not configured; cannot reconcile from Stripe.")
        _stripe.api_key = settings.PSP_STRIPE_SECRET_KEY

        try:
            session = _stripe.checkout.Session.retrieve(session_id)
        except Exception as exc:
            raise CommandError(f"Stripe lookup failed for {session_id}: {exc}")

        payment_status = session.get("payment_status")
        if payment_status != "paid":
            return ("not_paid", None, None, payment_status)

        from accounts.models import CustomerTopUpAttempt, WalletTransaction
        if WalletTransaction.objects.filter(
            reference=f"stripe:{session_id}",
            type=WalletTransaction.Type.TOPUP,
        ).exists():
            return ("already_credited", None, None, payment_status)

        meta = session.get("metadata") or {}
        customer_id = meta.get("customer_id")
        amount_total = session.get("amount_total")
        amount_value = None
        if amount_total is not None:
            try:
                amount_value = (Decimal(str(amount_total)) / Decimal("100")).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError, TypeError):
                amount_value = None
        if not customer_id or amount_value is None:
            raise CommandError(
                f"Session {session_id} is missing customer_id/amount_total metadata — "
                "cannot credit safely."
            )

        from accounts.wallet_service import credit_wallet
        credit_wallet(
            customer_id=customer_id,
            amount=amount_value,
            idempotency_key=f"reconciled:{session_id}",
            reference=f"stripe:{session_id}",
            note="PSP top-up reconciled from Stripe session",
            require_verified=False,
        )
        try:
            CustomerTopUpAttempt.objects.filter(session_id=session_id).update(
                status=CustomerTopUpAttempt.Status.CREDITED
            )
        except Exception:
            payments_logger.warning(
                "Top-up attempt row not marked credited session_id=%s", session_id
            )
        return ("credited", amount_value, customer_id, payment_status)

    def _reconcile_all(self):
        """Beat mode (R6-19, hourly): reconcile every uncredited CREATED attempt.

        One attempt's failure (Stripe lookup, bad metadata) is logged on the
        payments channel and the batch continues — a single bad session must
        not strand the rest. Each credit is also logged on the payments
        channel: money moved without a webhook, so the operator should know
        the reconciler (not Stripe's webhook) credited it. The per-session
        double-credit guards live in _reconcile_session and are unchanged.
        """
        from accounts.models import CustomerTopUpAttempt, WalletTransaction
        attempts = CustomerTopUpAttempt.objects.filter(
            status=CustomerTopUpAttempt.Status.CREATED,
        ).order_by("-created_at")[:100]
        credited = already = not_paid = failed = 0
        for attempt in attempts:
            session_id = attempt.session_id
            if WalletTransaction.objects.filter(
                reference=f"stripe:{session_id}",
                type=WalletTransaction.Type.TOPUP,
            ).exists():
                already += 1
                continue
            try:
                status, amount, customer_id, _ = self._reconcile_session(session_id)
            except CommandError as exc:
                failed += 1
                payments_logger.warning(
                    "reconcile_topups auto: session %s failed: %s", session_id, exc
                )
                continue
            if status == "credited":
                credited += 1
                payments_logger.warning(
                    "reconcile_topups auto: credited %s to customer %s for session %s "
                    "(webhook missed)",
                    amount, customer_id, session_id,
                )
            elif status == "already_credited":
                already += 1
            else:
                not_paid += 1
        self.stdout.write(
            f"reconcile_all: {credited} credited, {already} already credited, "
            f"{not_paid} not paid, {failed} failed."
        )
        return credited

    def _list_uncredited(self):
        from accounts.models import CustomerTopUpAttempt, WalletTransaction
        attempts = CustomerTopUpAttempt.objects.filter(
            status=CustomerTopUpAttempt.Status.CREATED,
        ).order_by("-created_at")[:100]
        found = 0
        for attempt in attempts:
            if WalletTransaction.objects.filter(
                reference=f"stripe:{attempt.session_id}",
                type=WalletTransaction.Type.TOPUP,
            ).exists():
                continue
            found += 1
            self.stdout.write(
                f"{attempt.session_id} customer={attempt.customer_id} "
                f"amount={attempt.amount} status={attempt.status}"
            )
        self.stdout.write(f"{found} uncredited attempt(s).")
        return found
