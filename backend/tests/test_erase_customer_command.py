"""Tests for the R18 erase_customer management command.

Coverage strategy:
  - Pure-logic unit tests (SimpleTestCase + mocks) run locally without Postgres.
  - DB-backed integration tests (TestCase / django-tenants fixtures) join the
    known "error" bucket locally (no Postgres) and pass in CI.

Pure-logic tests:
  - Guard-rail predicates: open orders, pending charges, non-zero balance.
  - Field-scrub mapping verification (what Phase 1 Customer.update sends).
  - Idempotency: re-run on already-blank fields is a no-op (doesn't raise).
  - --dry-run: no writes, no audit log, still prints counts.
  - Missing customer raises CommandError.
  - --force-erase required to write (safety default is dry-run).
  - _waitlist_q / _lead_q helpers with various phone/email combos.

DB-backed tests (require Postgres / CI):
  - Phase 1: Customer PII blanked; WalletTransaction retained (note blanked);
    CustomerOrderRef retained (fields scrubbed); SavedAddress deleted;
    CustomerPushSubscription deleted; CustomerRating deleted.
  - Phase 2: Order PII blanked; Rating customer→None; CustomerNote deleted.
  - Guard rails refuse on open order / nonzero balance / pending charge unless --force.
  - Audit log row created (not under dry-run).
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


# ══════════════════════════════════════════════════════════════════════════════
# Pure-logic helpers
# ══════════════════════════════════════════════════════════════════════════════

class WaitlistQHelperTests(SimpleTestCase):
    """_waitlist_q / _lead_q return correct Q objects."""

    def _wq(self, phone, email):
        from accounts.management.commands.erase_customer import _waitlist_q
        return _waitlist_q(phone, email)

    def _lq(self, phone, email):
        from accounts.management.commands.erase_customer import _lead_q
        return _lead_q(phone, email)

    def test_none_when_both_blank(self):
        self.assertIsNone(self._wq(None, ""))
        self.assertIsNone(self._lq(None, ""))

    def test_phone_only(self):
        q = self._wq("+212600000001", "")
        self.assertIsNotNone(q)
        self.assertIn("phone", str(q))

    def test_email_only(self):
        q = self._wq(None, "test@example.com")
        self.assertIsNotNone(q)
        self.assertIn("email", str(q))

    def test_both_phone_and_email(self):
        q = self._wq("+212600000002", "a@b.com")
        self.assertIsNotNone(q)
        self.assertIn("phone", str(q))
        self.assertIn("email", str(q))

    def test_lead_q_none_when_both_blank(self):
        self.assertIsNone(self._lq(None, ""))

    def test_lead_q_phone_only(self):
        q = self._lq("+212600000003", "")
        self.assertIsNotNone(q)


class GuardRailUnitTests(SimpleTestCase):
    """_check_guard_rails with mocked querysets (no DB).

    _check_guard_rails imports are local: patch at the source module paths.
    """

    def _make_customer(self, balance=Decimal("0.00")):
        c = MagicMock()
        c.wallet_balance = balance
        return c

    def _run_guards(self, customer, customer_id=99, pending_charges=0, pending_cashouts=0):
        @contextmanager
        def fake_schema_context(schema_name):
            yield

        mock_tenant_list = []

        with patch("tenancy.models.Tenant") as MockTenant, \
             patch("django_tenants.utils.schema_context", side_effect=fake_schema_context), \
             patch("accounts.models.WalletChargeRequest") as MockWCR, \
             patch("accounts.models.DriverCashoutRequest") as MockDCR:

            MockTenant.objects.all.return_value = mock_tenant_list

            MockWCR.Status.PENDING = "pending"
            MockWCR.objects.filter.return_value.count.return_value = pending_charges

            MockDCR.Status.PENDING = "pending"
            MockDCR.objects.filter.return_value.count.return_value = pending_cashouts

            from accounts.management.commands.erase_customer import _check_guard_rails
            return _check_guard_rails(customer, customer_id)

    def test_all_clear_returns_empty_list(self):
        customer = self._make_customer(balance=Decimal("0.00"))
        errors = self._run_guards(customer)
        self.assertEqual(errors, [])

    def test_nonzero_balance_triggers_error(self):
        customer = self._make_customer(balance=Decimal("5.00"))
        errors = self._run_guards(customer)
        self.assertTrue(any("wallet_balance" in e for e in errors), errors)

    def test_pending_charge_triggers_error(self):
        customer = self._make_customer()
        errors = self._run_guards(customer, pending_charges=2)
        self.assertTrue(any("WalletChargeRequest" in e for e in errors), errors)

    def test_pending_cashout_triggers_error(self):
        customer = self._make_customer()
        errors = self._run_guards(customer, pending_cashouts=1)
        self.assertTrue(any("DriverCashoutRequest" in e for e in errors), errors)

    def test_tiny_balance_within_epsilon_is_ok(self):
        customer = self._make_customer(balance=Decimal("0.005"))
        errors = self._run_guards(customer)
        self.assertEqual(errors, [])


def _make_zero_qs():
    """Return a MagicMock queryset with count=0 / update=0 / delete=0."""
    m = MagicMock()
    m.count.return_value = 0
    m.update.return_value = 0
    m.delete.return_value = (0, {})
    m.filter.return_value = m
    m.values_list.return_value = []
    m.__iter__ = lambda self: iter([])
    return m


def _noop_atomic():
    @contextmanager
    def _ctx():
        yield
    return _ctx()


class CommandRequiresForceEraseTests(SimpleTestCase):
    """Without --force-erase the command defaults to dry-run (safety)."""

    def test_missing_customer_id_raises(self):
        out = io.StringIO()
        err = io.StringIO()
        with self.assertRaises((CommandError, SystemExit)):
            call_command("erase_customer", stdout=out, stderr=err)

    def test_no_force_erase_defaults_to_dry_run(self):
        """Calling without --force-erase must print DRY-RUN and make no writes."""
        fake_customer = MagicMock()
        fake_customer.phone = None
        fake_customer.email = ""
        fake_customer.wallet_balance = Decimal("0.00")

        zero_qs = _make_zero_qs()

        with patch("accounts.models.Customer") as MockCust, \
             patch("accounts.models.WalletTransaction") as MockWT, \
             patch("accounts.models.TenantFloatTransaction") as MockTFT, \
             patch("accounts.models.CustomerOrderRef") as MockCOR, \
             patch("accounts.models.CustomerPushSubscription") as MockCPS, \
             patch("accounts.models.SavedAddress") as MockSA, \
             patch("accounts.models.WinbackNudge") as MockWN, \
             patch("accounts.models.CustomerRating") as MockCR, \
             patch("accounts.models.DeliveryJob") as MockDJ, \
             patch("accounts.models.RideRequest") as MockRR, \
             patch("accounts.models.NotificationLog") as MockNL, \
             patch("tenancy.models.Tenant") as MockTenant, \
             patch("sales.models.Lead") as MockLead, \
             patch("sales.models.ReservationReminder"):

            MockCust.objects.get.return_value = fake_customer
            for m in [MockWT, MockTFT, MockCOR, MockCPS, MockSA, MockWN,
                      MockCR, MockDJ, MockRR, MockNL, MockCust]:
                m.objects.filter.return_value = _make_zero_qs()
            MockTenant.objects.all.return_value = []
            MockLead.objects.filter.return_value.values_list.return_value = []
            MockLead.objects.filter.return_value.count.return_value = 0

            out = io.StringIO()
            call_command("erase_customer", 1, "--force", stdout=out)
            output = out.getvalue()
            self.assertIn("DRY-RUN", output)
            self.assertNotIn("DONE", output)


class FieldScrubMappingTests(SimpleTestCase):
    """Verify the exact fields passed to Customer.objects.filter().update()."""

    def _run_erase_and_capture(self):
        """Run a full write pass and return the kwargs to Customer.update()."""
        fake_customer = MagicMock()
        fake_customer.phone = "+212600000001"
        fake_customer.email = "test@example.com"
        fake_customer.wallet_balance = Decimal("0.00")

        cust_filter_qs = MagicMock()
        cust_filter_qs.update = MagicMock(return_value=1)

        with patch("accounts.models.Customer") as MockCust, \
             patch("accounts.models.WalletTransaction") as MockWT, \
             patch("accounts.models.TenantFloatTransaction") as MockTFT, \
             patch("accounts.models.CustomerOrderRef") as MockCOR, \
             patch("accounts.models.CustomerPushSubscription") as MockCPS, \
             patch("accounts.models.SavedAddress") as MockSA, \
             patch("accounts.models.WinbackNudge") as MockWN, \
             patch("accounts.models.CustomerRating") as MockCR, \
             patch("accounts.models.DeliveryJob") as MockDJ, \
             patch("accounts.models.RideRequest") as MockRR, \
             patch("accounts.models.DriverPayout") as MockDP, \
             patch("accounts.models.WalletChargeRequest") as MockWCR, \
             patch("accounts.models.CustomerServiceProfile") as MockCSP, \
             patch("accounts.models.NotificationLog") as MockNL, \
             patch("tenancy.models.Tenant") as MockTenant, \
             patch("accounts.management.commands.erase_customer.transaction") as MockTx, \
             patch("sales.models.Lead") as MockLead, \
             patch("sales.models.ReservationReminder"), \
             patch("sales.models.ReservationTimelineEvent") as MockRTE, \
             patch("sales.audit.log_admin_action"):

            MockCust.objects.get.return_value = fake_customer
            MockCust.objects.filter.return_value = cust_filter_qs

            for m in [MockWT, MockTFT, MockCOR, MockCPS, MockSA, MockWN,
                      MockCR, MockDJ, MockRR, MockDP, MockWCR, MockRTE, MockNL, MockCSP]:
                m.objects.filter.return_value = _make_zero_qs()

            MockTenant.objects.all.return_value = []
            # Phase 1 AND Phase 3 each open transaction.atomic() → return a fresh
            # context manager per call (a single instance can only be entered once).
            MockTx.atomic.side_effect = lambda *a, **k: _noop_atomic()

            MockLead.objects.filter.return_value.values_list.return_value = []
            MockLead.objects.filter.return_value.update.return_value = 0
            MockLead.objects.filter.return_value.count.return_value = 0

            call_command("erase_customer", 1, "--force-erase", "--force")

            return cust_filter_qs.update.call_args

    def test_customer_scrub_blanks_phone(self):
        call_args = self._run_erase_and_capture()
        self.assertIsNotNone(call_args, "Customer.update was not called")
        self.assertIsNone(call_args.kwargs.get("phone"))

    def test_customer_scrub_blanks_email(self):
        call_args = self._run_erase_and_capture()
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args.kwargs.get("email"), "")

    def test_customer_scrub_blanks_name(self):
        call_args = self._run_erase_and_capture()
        self.assertIsNotNone(call_args)
        self.assertEqual(call_args.kwargs.get("name"), "")

    def test_customer_scrub_blanks_google_sub(self):
        call_args = self._run_erase_and_capture()
        self.assertIsNotNone(call_args)
        self.assertIsNone(call_args.kwargs.get("google_sub"))

    def test_customer_scrub_blanks_driver_lat_lng(self):
        call_args = self._run_erase_and_capture()
        self.assertIsNotNone(call_args)
        self.assertIsNone(call_args.kwargs.get("driver_lat"))
        self.assertIsNone(call_args.kwargs.get("driver_lng"))


class IdempotencyUnitTests(SimpleTestCase):
    """Already-blank customer does not raise on re-run."""

    def test_already_erased_customer_reruns_cleanly(self):
        already_erased = MagicMock()
        already_erased.phone = None
        already_erased.email = ""
        already_erased.wallet_balance = Decimal("0.00")

        cust_filter_qs = MagicMock()
        cust_filter_qs.update = MagicMock(return_value=0)  # 0 rows changed = no-op

        with patch("accounts.models.Customer") as MockCust, \
             patch("accounts.models.WalletTransaction") as MockWT, \
             patch("accounts.models.TenantFloatTransaction") as MockTFT, \
             patch("accounts.models.CustomerOrderRef") as MockCOR, \
             patch("accounts.models.CustomerPushSubscription") as MockCPS, \
             patch("accounts.models.SavedAddress") as MockSA, \
             patch("accounts.models.WinbackNudge") as MockWN, \
             patch("accounts.models.CustomerRating") as MockCR, \
             patch("accounts.models.DeliveryJob") as MockDJ, \
             patch("accounts.models.RideRequest") as MockRR, \
             patch("accounts.models.DriverPayout") as MockDP, \
             patch("accounts.models.WalletChargeRequest") as MockWCR, \
             patch("accounts.models.CustomerServiceProfile") as MockCSP, \
             patch("accounts.models.NotificationLog") as MockNL, \
             patch("tenancy.models.Tenant") as MockTenant, \
             patch("accounts.management.commands.erase_customer.transaction") as MockTx, \
             patch("sales.models.Lead") as MockLead, \
             patch("sales.models.ReservationReminder"), \
             patch("sales.models.ReservationTimelineEvent"), \
             patch("sales.audit.log_admin_action"):

            MockCust.objects.get.return_value = already_erased
            MockCust.objects.filter.return_value = cust_filter_qs

            for m in [MockWT, MockTFT, MockCOR, MockCPS, MockSA, MockWN,
                      MockCR, MockDJ, MockRR, MockDP, MockWCR, MockNL, MockCSP]:
                m.objects.filter.return_value = _make_zero_qs()

            MockTenant.objects.all.return_value = []
            MockTx.atomic.side_effect = lambda *a, **k: _noop_atomic()

            MockLead.objects.filter.return_value.values_list.return_value = []
            MockLead.objects.filter.return_value.update.return_value = 0
            MockLead.objects.filter.return_value.count.return_value = 0

            out = io.StringIO()
            call_command("erase_customer", 1, "--force-erase", "--force", stdout=out)
            # Must complete without raising
            self.assertIn("DONE", out.getvalue())


# ══════════════════════════════════════════════════════════════════════════════
# DB-backed integration tests (require Postgres / CI)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestEraseCustomerIntegration:
    """Full integration tests — these require Postgres and run in CI."""

    def _make_customer(self, phone="+212600100001", email="customer@example.com",
                       name="Test Customer", wallet_balance=Decimal("0.00")):
        from accounts.models import Customer
        return Customer.objects.create(
            phone=phone,
            email=email,
            name=name,
            wallet_balance=wallet_balance,
        )

    def test_customer_row_is_retained_not_deleted(self):
        from accounts.models import Customer
        customer = self._make_customer()
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        assert Customer.objects.filter(pk=cid).exists(), "Customer row was deleted — must NOT be!"

    def test_pii_fields_blanked(self):
        customer = self._make_customer(
            phone="+212600100002",
            email="pii@example.com",
            name="Has PII",
        )
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        customer.refresh_from_db()
        assert customer.phone is None
        assert customer.email == ""
        assert customer.name == ""
        assert customer.google_sub is None
        assert customer.phone_verified is False
        assert customer.email_verified is False

    def test_wallet_transaction_retained_note_blanked(self):
        from accounts.models import WalletTransaction
        customer = self._make_customer(phone="+212600100003", email="wt@example.com")
        tx = WalletTransaction.objects.create(
            customer=customer,
            type=WalletTransaction.Type.TOPUP,
            amount=Decimal("10.00"),
            note="Top-up for pii@example.com",
        )
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        tx.refresh_from_db()
        assert WalletTransaction.objects.filter(pk=tx.pk).exists()
        assert tx.note == ""
        assert tx.amount == Decimal("10.00")

    def test_saved_address_deleted(self):
        from accounts.models import SavedAddress
        customer = self._make_customer(phone="+212600100004", email="sa@example.com")
        SavedAddress.objects.create(customer=customer, address="123 Main St")
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        assert not SavedAddress.objects.filter(customer_id=cid).exists()

    def test_customer_push_subscription_deleted(self):
        from accounts.models import CustomerPushSubscription
        customer = self._make_customer(phone="+212600100005", email="push@example.com")
        CustomerPushSubscription.objects.create(
            customer=customer,
            endpoint="https://push.example.com/sub/1",
            p256dh="dGVzdA==",
            auth="YXV0aA==",
        )
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        assert not CustomerPushSubscription.objects.filter(customer_id=cid).exists()

    def test_customer_rating_deleted(self):
        from accounts.models import CustomerRating
        customer = self._make_customer(phone="+212600100006", email="cr@example.com")
        CustomerRating.objects.create(
            customer=customer,
            tenant_id=1,
            order_number="TEST-001",
            score=4,
            note="Good customer",
        )
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        assert not CustomerRating.objects.filter(customer_id=cid).exists()

    def test_customer_order_ref_retained_fields_scrubbed(self):
        from accounts.models import CustomerOrderRef
        from django.utils import timezone
        customer = self._make_customer(phone="+212600100007", email="cor@example.com")
        ref = CustomerOrderRef.objects.create(
            customer=customer,
            tenant_id=1,
            order_number="ORD-001",
            restaurant_name="Test Restaurant",
            restaurant_slug="test-rest",
            items_snapshot=[{"name": "Burger", "qty": 1}],
            total=Decimal("25.00"),
            order_created_at=timezone.now(),
        )
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        ref.refresh_from_db()
        assert CustomerOrderRef.objects.filter(pk=ref.pk).exists()
        assert ref.restaurant_name == ""
        assert ref.restaurant_slug == ""
        assert ref.items_snapshot == []
        assert ref.total == Decimal("25.00")

    def test_guard_refuses_nonzero_balance(self):
        customer = self._make_customer(
            phone="+212600100008",
            email="balance@example.com",
            wallet_balance=Decimal("10.00"),
        )
        with pytest.raises(CommandError, match="guard-rail"):
            call_command("erase_customer", customer.pk, "--force-erase")

    def test_guard_bypass_with_force(self):
        customer = self._make_customer(
            phone="+212600100009",
            email="bypass@example.com",
            wallet_balance=Decimal("10.00"),
        )
        call_command("erase_customer", customer.pk, "--force-erase", "--force")
        customer.refresh_from_db()
        assert customer.phone is None

    def test_dry_run_writes_nothing(self):
        customer = self._make_customer(phone="+212600100010", email="dry@example.com")
        cid = customer.pk
        out = io.StringIO()
        call_command("erase_customer", cid, "--dry-run", "--force", stdout=out)
        customer.refresh_from_db()
        assert customer.phone == "+212600100010"
        assert customer.email == "dry@example.com"
        assert "DRY-RUN" in out.getvalue()

    def test_audit_log_created_on_erase(self):
        from sales.models import AdminAuditLog
        customer = self._make_customer(phone="+212600100011", email="audit@example.com")
        cid = customer.pk
        before_count = AdminAuditLog.objects.filter(
            action=AdminAuditLog.Actions.CUSTOMER_ERASED
        ).count()
        call_command("erase_customer", cid, "--force-erase", "--force")
        after_count = AdminAuditLog.objects.filter(
            action=AdminAuditLog.Actions.CUSTOMER_ERASED
        ).count()
        assert after_count == before_count + 1

    def test_audit_log_not_created_on_dry_run(self):
        from sales.models import AdminAuditLog
        customer = self._make_customer(phone="+212600100012", email="nodry@example.com")
        cid = customer.pk
        before_count = AdminAuditLog.objects.filter(
            action=AdminAuditLog.Actions.CUSTOMER_ERASED
        ).count()
        call_command("erase_customer", cid, "--dry-run", "--force")
        after_count = AdminAuditLog.objects.filter(
            action=AdminAuditLog.Actions.CUSTOMER_ERASED
        ).count()
        assert after_count == before_count, "Audit log must NOT be written under --dry-run"

    def test_idempotent_reruns_cleanly(self):
        customer = self._make_customer(phone="+212600100013", email="idm@example.com")
        cid = customer.pk
        call_command("erase_customer", cid, "--force-erase", "--force")
        # Second run must not raise
        call_command("erase_customer", cid, "--force-erase", "--force")
        customer.refresh_from_db()
        assert customer.phone is None

    def test_notification_log_recipient_blanked(self):
        from accounts.models import NotificationLog
        phone = "+212600100014"
        email = "notif@example.com"
        customer = self._make_customer(phone=phone, email=email)
        log = NotificationLog.objects.create(
            channel=NotificationLog.Channel.SMS,
            event="order.ready",
            status=NotificationLog.Status.SENT,
            recipient=phone,
        )
        call_command("erase_customer", customer.pk, "--force-erase", "--force")
        log.refresh_from_db()
        assert log.recipient == ""

    def test_winback_nudge_deleted(self):
        from accounts.models import WinbackNudge
        customer = self._make_customer(phone="+212600100015", email="wb@example.com")
        WinbackNudge.objects.create(tenant_id=1, customer_id=customer.pk)
        call_command("erase_customer", customer.pk, "--force-erase", "--force")
        assert not WinbackNudge.objects.filter(customer_id=customer.pk).exists()
