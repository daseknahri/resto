"""Zero wallet balances held by customers without a verified phone.

Enforces the platform rule "no verified phone → no wallet" on EXISTING data. New
credits are already blocked at the service layer; this is a one-off cleanup for any
balances that accumulated before the rule existed.

Safe by default: prints a report and changes nothing. Pass --apply to actually zero
the balances, writing an auditable ADJUSTMENT WalletTransaction for each.

    python manage.py sweep_unverified_wallets            # dry-run report
    python manage.py sweep_unverified_wallets --apply     # perform the sweep
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum


class Command(BaseCommand):
    help = "Zero wallet balances held by customers without a verified phone (no verified phone -> no wallet)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually zero the balances. Without this flag the command only reports (dry-run).",
        )
        parser.add_argument(
            "--note",
            default="Reversed: phone not verified",
            help="Note recorded on each adjustment transaction.",
        )
        parser.add_argument(
            "--include-card-paid",
            action="store_true",
            help="Also sweep customers who topped up by card (a TOPUP WalletTransaction "
                 "on file). By default those are skipped: their money arrived via a "
                 "verified payment instrument, so zeroing it is a support decision, "
                 "not a cleanup.",
        )

    def handle(self, *args, **options):
        from accounts.models import Customer, WalletTransaction

        apply = options["apply"]
        note = (options["note"] or "")[:200]

        qs = Customer.objects.filter(phone_verified=False, wallet_balance__gt=0)
        # Wave M M-08: a customer who paid by card has a TOPUP row on the
        # ledger — their balance is real card money, not a pre-rule artefact.
        # Skip them unless the operator explicitly opts in.
        skipped_card_paid = 0
        if not options["include_card_paid"]:
            before = qs.count()
            qs = qs.exclude(
                id__in=WalletTransaction.objects.filter(
                    type=WalletTransaction.Type.TOPUP
                ).values("customer_id")
            )
            skipped_card_paid = before - qs.count()
        count = qs.count()
        total = qs.aggregate(s=Sum("wallet_balance"))["s"] or Decimal("0")

        if count == 0:
            msg = "No unverified customers hold a wallet balance. Nothing to do."
            if skipped_card_paid:
                msg += (
                    f" ({skipped_card_paid} card-paid customer(s) skipped — "
                    "pass --include-card-paid to include them.)"
                )
            self.stdout.write(self.style.SUCCESS(msg))
            return

        if not apply:
            self.stdout.write(
                f"[dry-run] {count} unverified customer(s) hold a total of {total} in wallet balance."
            )
            if skipped_card_paid:
                self.stdout.write(
                    f"Skipped {skipped_card_paid} customer(s) who topped up by card "
                    "(TOPUP on file) — pass --include-card-paid to include them."
                )
            self.stdout.write("Re-run with --apply to zero these balances (an adjustment record is written for each).")
            return

        from accounts.wallet_service import debit_wallet, InsufficientFunds

        swept = 0
        swept_total = Decimal("0")
        for cust_id in list(qs.values_list("id", flat=True)):
            with transaction.atomic():
                # Re-check under lock (debit_wallet does its own select_for_update):
                # read a fresh snapshot first to know the amount; if it changed to 0
                # or the customer got verified, skip.
                # Lock the row for the re-check so a concurrent phone-verification
                # cannot slip between the check and the debit. debit_wallet re-locks
                # the same row in this same transaction — a no-op in PostgreSQL.
                cust = Customer.objects.select_for_update().get(pk=cust_id)
                if cust.phone_verified or Decimal(str(cust.wallet_balance or "0")) <= 0:
                    continue
                amount = Decimal(str(cust.wallet_balance)).quantize(Decimal("0.01"))
                try:
                    tx = debit_wallet(
                        cust.id,
                        amount,
                        tx_type=WalletTransaction.Type.ADJUSTMENT,
                        reference="sweep_unverified",
                        note=note,
                    )
                except InsufficientFunds:
                    # Balance may have dropped to zero between the snapshot above and
                    # the debit_wallet lock — skip cleanly rather than fail the sweep.
                    continue
                swept += 1
                swept_total += tx.amount if tx is not None else amount

        self.stdout.write(self.style.SUCCESS(f"Swept {swept} wallet(s), removing {swept_total} in unverified balance."))
        if skipped_card_paid:
            self.stdout.write(
                f"Skipped {skipped_card_paid} card-paid customer(s) (TOPUP on file)."
            )
