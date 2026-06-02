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

    def handle(self, *args, **options):
        from accounts.models import Customer, WalletTransaction

        apply = options["apply"]
        note = (options["note"] or "")[:200]

        qs = Customer.objects.filter(phone_verified=False, wallet_balance__gt=0)
        count = qs.count()
        total = qs.aggregate(s=Sum("wallet_balance"))["s"] or Decimal("0")

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No unverified customers hold a wallet balance. Nothing to do."))
            return

        if not apply:
            self.stdout.write(
                f"[dry-run] {count} unverified customer(s) hold a total of {total} in wallet balance."
            )
            self.stdout.write("Re-run with --apply to zero these balances (an adjustment record is written for each).")
            return

        swept = 0
        swept_total = Decimal("0")
        for cust_id in list(qs.values_list("id", flat=True)):
            with transaction.atomic():
                cust = Customer.objects.select_for_update().get(pk=cust_id)
                # Re-check under lock: skip if it got verified or zeroed meanwhile.
                if cust.phone_verified or Decimal(str(cust.wallet_balance or "0")) <= 0:
                    continue
                amount = Decimal(str(cust.wallet_balance)).quantize(Decimal("0.01"))
                cust.wallet_balance = Decimal("0.00")
                cust.save(update_fields=["wallet_balance", "updated_at"])
                WalletTransaction.objects.create(
                    customer=cust,
                    type=WalletTransaction.Type.ADJUSTMENT,
                    amount=amount,
                    balance_after=Decimal("0.00"),
                    note=note,
                )
                swept += 1
                swept_total += amount

        self.stdout.write(self.style.SUCCESS(f"Swept {swept} wallet(s), removing {swept_total} in unverified balance."))
