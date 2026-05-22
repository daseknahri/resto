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

from menu.models import CurrencyRate

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

        updated = []
        skipped = []

        for code, rate_from_mad in raw_rates.items():
            try:
                rate_float = float(rate_from_mad)
                if rate_float <= 0:
                    raise ValueError("non-positive rate")
                # Invert: 1 MAD = rate_from_mad EUR  →  1 EUR = 1/rate_from_mad MAD
                mad_per_unit = Decimal(str(round(1.0 / rate_float, 6)))
            except (TypeError, ValueError, InvalidOperation) as exc:
                self.stderr.write(f"  Skipping {code}: bad rate value {rate_from_mad!r} ({exc})")
                skipped.append(code)
                continue

            if dry_run:
                self.stdout.write(f"  [dry-run] {code}: mad_per_unit = {mad_per_unit}")
            else:
                rows_updated = CurrencyRate.objects.filter(code=code).update(mad_per_unit=mad_per_unit)
                if rows_updated:
                    updated.append(f"{code}={mad_per_unit}")
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  {code} not found in DB — skipping (add it via admin first).")
                    )
                    skipped.append(code)

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run complete. No changes saved."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Updated: {', '.join(updated) or 'none'}. "
                    f"Skipped: {', '.join(skipped) or 'none'}."
                )
            )
        logger.info("fetch_currency_rates: updated=%s skipped=%s dry_run=%s", updated, skipped, dry_run)
