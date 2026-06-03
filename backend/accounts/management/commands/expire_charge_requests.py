"""Expire pending wallet charge requests that have passed their TTL.

Pending requests are lazily expired when a customer lists them or an owner polls a
specific one, but a request that is never looked at again would linger as 'pending'.
This sweeps them so the table reflects reality. Idempotent — safe to run on a schedule.

    python manage.py expire_charge_requests
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Mark pending wallet charge requests past their expiry as expired."

    def handle(self, *args, **options):
        from accounts.models import WalletChargeRequest

        now = timezone.now()
        expired = WalletChargeRequest.objects.filter(
            status=WalletChargeRequest.Status.PENDING,
            expires_at__lte=now,
        ).update(status=WalletChargeRequest.Status.EXPIRED, resolved_at=now)

        if expired:
            self.stdout.write(self.style.SUCCESS(f"Expired {expired} stale charge request(s)."))
        else:
            self.stdout.write("No pending charge requests to expire.")
