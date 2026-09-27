"""
Management command: fetch_currency_rates
========================================
Fetches current MAD-based exchange rates from the Frankfurter API
(https://frankfurter.app — free, no API key required) and updates
the CurrencyRate table.

Usage:
    python manage.py fetch_currency_rates

Typical cron (daily at 06:00):
    0 6 * * * /path/to/venv/bin/python /app/manage.py fetch_currency_rates

Frankfurter endpoint used:
    GET https://api.frankfurter.app/latest?base=MAD&symbols=EUR,SAR,AED
    Response: { "base": "MAD", "rates": { "EUR": 0.0917, "SAR": 0.3831, "AED": 0.3745 } }

Since the response gives  "1 MAD = X <code>", we invert to get mad_per_unit:
    mad_per_unit = 1 / rate
"""

import logging
import urllib.request
import json
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from menu.models import CurrencyRate
from tenancy.models import Tenant

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest?base=MAD&symbols=EUR,SAR,AED"
TIMEOUT_SECONDS = 10


class Command(BaseCommand):
    help = "Fetch latest MAD exchange rates from Frankfurter and update CurrencyRate table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the fetched rates without saving to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        self.stdout.write("Fetching exchange rates from Frankfurter…")

        try:
            with urllib.request.urlopen(FRANKFURTER_URL, timeout=TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode())
        except Exception as exc:
            raise CommandError(f"Failed to fetch rates: {exc}") from exc

        raw_rates = payload.get("rates", {})
        if not raw_rates:
            raise CommandError("Empty rates payload received from Frankfurter.")

        # Parse + invert once (1 MAD = X <code>  →  1 <code> = 1/X MAD).
        parsed = {}
        bad = []
        for code, rate_from_mad in raw_rates.items():
            try:
                rate_float = float(rate_from_mad)
                if rate_float <= 0:
                    raise ValueError("non-positive rate")
                parsed[code] = Decimal(str(round(1.0 / rate_float, 6)))
            except (TypeError, ValueError, InvalidOperation) as exc:
                self.stderr.write(f"  Skipping {code}: bad rate value {rate_from_mad!r} ({exc})")
                bad.append(code)

        if dry_run:
            for code, mad_per_unit in parsed.items():
                self.stdout.write(f"  [dry-run] {code}: mad_per_unit = {mad_per_unit}")
            self.stdout.write(self.style.SUCCESS("Dry-run complete. No changes saved."))
            return

        # CurrencyRate is a TENANT-app model — menu_currencyrate exists ONLY inside each
        # tenant schema, never in public. This command runs on the PUBLIC schema (the Celery
        # cron), so the update MUST loop tenant schemas; the previous public-schema update
        # raised ProgrammingError ("relation does not exist") on every run, so rates never
        # refreshed after the manual seed. Mirrors release_scheduled_orders / auto_reset_availability.
        tenants = (
            Tenant.objects.filter(is_active=True, lifecycle_status=Tenant.LifecycleStatus.ACTIVE)
            .exclude(schema_name="public")
        )
        tenant_count = 0
        row_updates = 0
        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    for code, mad_per_unit in parsed.items():
                        row_updates += CurrencyRate.objects.filter(code=code).update(mad_per_unit=mad_per_unit)
                tenant_count += 1
            except Exception as exc:  # noqa: BLE001 — one bad schema must not abort the rest
                self.stderr.write(f"  {tenant.schema_name}: update failed ({exc})")
                logger.warning("fetch_currency_rates: schema %s failed", tenant.schema_name, exc_info=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Rates {', '.join(f'{c}={v}' for c, v in parsed.items()) or 'none'} applied "
                f"across {tenant_count} tenant schema(s) ({row_updates} row updates). "
                f"Bad codes skipped: {', '.join(bad) or 'none'}."
            )
        )
        logger.info(
            "fetch_currency_rates: tenants=%s row_updates=%s bad=%s dry_run=%s",
            tenant_count, row_updates, bad, dry_run,
        )
