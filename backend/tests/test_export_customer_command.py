"""Tests for the R18b export_customer management command.

Read-only GDPR export counterpart to erase_customer. Coverage:
  - Missing customer raises CommandError.
  - Export contains the customer's own rows (WalletTransaction, SavedAddress).
  - Export performs NO mutation: all fields/rows are unchanged after running,
    and no other customer's data leaks into the export.
  - --output writes the same JSON to a file.
"""
from __future__ import annotations

import io
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


class TestExportCustomerMissingId:
    """Pure-logic: missing/unknown customer id."""

    def test_missing_customer_id_raises(self):
        out = io.StringIO()
        err = io.StringIO()
        with pytest.raises((CommandError, SystemExit)):
            call_command("export_customer", stdout=out, stderr=err)

    @pytest.mark.django_db
    def test_unknown_customer_id_raises(self):
        with pytest.raises(CommandError, match="does not exist"):
            call_command("export_customer", 999999999)


@pytest.mark.django_db
class TestExportCustomerIntegration:
    """Full integration tests — require Postgres, run in CI."""

    def _make_customer(self, phone="+212600200001", email="export@example.com",
                        name="Export Customer"):
        from accounts.models import Customer
        return Customer.objects.create(phone=phone, email=email, name=name)

    def test_export_contains_customer_row(self):
        customer = self._make_customer()
        out = io.StringIO()
        call_command("export_customer", customer.pk, stdout=out)
        output = out.getvalue()
        # The JSON payload is embedded in stdout between the banner lines.
        payload = json.loads(output.split("\n", 1)[1].rsplit("\n\n", 1)[0])
        assert payload["customer_id"] == customer.pk
        assert payload["customer"]["email"] == "export@example.com"
        assert payload["customer"]["name"] == "Export Customer"
        assert payload["customer"]["phone"] == "+212600200001"

    def test_export_contains_wallet_transaction(self):
        from decimal import Decimal
        from accounts.models import WalletTransaction
        customer = self._make_customer(phone="+212600200002", email="wt@example.com")
        WalletTransaction.objects.create(
            customer=customer,
            type=WalletTransaction.Type.TOPUP,
            amount=Decimal("15.00"),
            note="export test topup",
        )
        out = io.StringIO()
        call_command("export_customer", customer.pk, stdout=out)
        payload = json.loads(out.getvalue().split("\n", 1)[1].rsplit("\n\n", 1)[0])
        assert len(payload["wallet_transactions"]) == 1
        assert payload["wallet_transactions"][0]["amount"] == "15.00"
        assert payload["wallet_transactions"][0]["note"] == "export test topup"

    def test_export_contains_saved_address(self):
        from accounts.models import SavedAddress
        customer = self._make_customer(phone="+212600200003", email="sa@example.com")
        SavedAddress.objects.create(customer=customer, address="123 Export St")
        out = io.StringIO()
        call_command("export_customer", customer.pk, stdout=out)
        payload = json.loads(out.getvalue().split("\n", 1)[1].rsplit("\n\n", 1)[0])
        assert len(payload["saved_addresses"]) == 1
        assert payload["saved_addresses"][0]["address"] == "123 Export St"

    def test_export_does_not_leak_other_customers_data(self):
        from accounts.models import SavedAddress
        customer = self._make_customer(phone="+212600200004", email="mine@example.com")
        other = self._make_customer(phone="+212600200005", email="other@example.com")
        SavedAddress.objects.create(customer=customer, address="Mine")
        SavedAddress.objects.create(customer=other, address="Not mine")
        out = io.StringIO()
        call_command("export_customer", customer.pk, stdout=out)
        payload = json.loads(out.getvalue().split("\n", 1)[1].rsplit("\n\n", 1)[0])
        addresses = [a["address"] for a in payload["saved_addresses"]]
        assert addresses == ["Mine"]

    def test_export_is_read_only_no_mutation(self):
        from decimal import Decimal
        from accounts.models import Customer, SavedAddress, WalletTransaction

        customer = self._make_customer(phone="+212600200006", email="readonly@example.com")
        SavedAddress.objects.create(customer=customer, address="Untouched Ave")
        tx = WalletTransaction.objects.create(
            customer=customer,
            type=WalletTransaction.Type.TOPUP,
            amount=Decimal("20.00"),
            note="must stay",
        )

        before_customer_count = Customer.objects.count()
        before_address_count = SavedAddress.objects.filter(customer_id=customer.pk).count()

        out = io.StringIO()
        call_command("export_customer", customer.pk, stdout=out)

        # Nothing deleted, nothing scrubbed.
        assert Customer.objects.count() == before_customer_count
        assert SavedAddress.objects.filter(customer_id=customer.pk).count() == before_address_count

        customer.refresh_from_db()
        assert customer.phone == "+212600200006"
        assert customer.email == "readonly@example.com"
        assert customer.name == "Export Customer"

        tx.refresh_from_db()
        assert tx.note == "must stay"
        assert tx.amount == Decimal("20.00")

        address = SavedAddress.objects.get(customer_id=customer.pk)
        assert address.address == "Untouched Ave"

    def test_output_file_written(self, tmp_path):
        customer = self._make_customer(phone="+212600200007", email="file@example.com")
        out_file = tmp_path / "export.json"
        out = io.StringIO()
        call_command("export_customer", customer.pk, "--output", str(out_file), stdout=out)
        assert out_file.exists()
        payload = json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["customer_id"] == customer.pk
        assert payload["customer"]["email"] == "file@example.com"
        assert "DONE" in out.getvalue()
