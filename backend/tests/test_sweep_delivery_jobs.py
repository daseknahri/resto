"""Sweep rules added in Wave B (delivery gap hunt): pickup SLA (D G5), FAILED
re-alert (D G4), and missing-job backfill (D G3).

Mock-based (SimpleTestCase, no DB), following test_sweep_auto_refund.py: the DB
collaborators are mocked and the real Command methods are driven. The ORM filter
semantics (which rows the scan matches) are by construction; these tests prove the
decision logic under the lock / the throttle / the wiring.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from accounts.management.commands.sweep_delivery_jobs import Command

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


@contextmanager
def _noop_cm(*args, **kwargs):
    yield


def _job(*, job_id=1, tenant_id=1, order="ORD-1", status="assigned",
         driver_id=99, redispatch_count=0, assigned_at=None, failed_at=None,
         owner_alerted_at=None, failure_reason="customer_no_show", food_ready_at=None):
    j = MagicMock()
    j.id = job_id
    j.pk = job_id
    j.tenant_id = tenant_id
    j.order_number = order
    j.status = status
    j.driver_id = driver_id
    j.redispatch_count = redispatch_count
    j.assigned_at = assigned_at
    j.failed_at = failed_at
    j.food_ready_at = food_ready_at
    j.owner_alerted_at = owner_alerted_at
    j.failure_reason = failure_reason
    j.get_failure_reason_display.return_value = "Customer not reachable / no-show"
    return j


# ── D G5: pickup SLA ──────────────────────────────────────────────────────────

class ReleaseIdleAssignedJobsTests(SimpleTestCase):
    def _run(self, *, candidate, locked_job, sla_minutes=15):
        """Drive Command._release_idle_assigned_jobs with the DB mocked.

        candidate: the job the scan yields (or None). locked_job: what the under-lock
        re-check returns (None = advanced/picked up since the scan). Returns
        (released_count, alert_owner_mock, offer_mock, locked_job).
        """
        alert_owner = MagicMock()
        with patch("accounts.models.DeliveryJob") as DJ, \
                patch("accounts.dispatch.offer_to_next_driver") as offer, \
                patch("django.db.transaction.atomic", _noop_cm):
            for name, val in [
                ("SEARCHING", "searching"), ("ASSIGNED", "assigned"),
                ("AT_RESTAURANT", "at_restaurant"), ("PICKED_UP", "picked_up"),
            ]:
                setattr(DJ.Status, name, val)
            DJ.objects.filter.return_value.select_related.return_value = (
                [candidate] if candidate else []
            )
            (DJ.objects.select_for_update.return_value
                .filter.return_value.first.return_value) = locked_job
            with override_settings(DELIVERY_PICKUP_SLA_MINUTES=sla_minutes):
                count = Command()._release_idle_assigned_jobs(_NOW, alert_owner)
        return count, alert_owner, offer, locked_job

    def test_idle_assigned_driver_past_sla_is_released(self):
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=20))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 1)
        self.assertIsNone(locked.driver)
        self.assertEqual(locked.status, "searching")
        self.assertEqual(locked.redispatch_count, 1)
        self.assertIsNone(locked.assigned_at)
        locked.save.assert_called_once()
        offer.assert_called_once_with(job.id)
        alert_owner.assert_called_once()

    def test_idle_at_restaurant_driver_past_sla_is_released(self):
        """AT_RESTAURANT counts too: the SLA is measured from assigned_at (there is no
        at_restaurant_at timestamp), so a driver parked at the restaurant is idle."""
        job = _job(status="at_restaurant", assigned_at=_NOW - timedelta(minutes=20))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 1)
        self.assertEqual(locked.status, "searching")
        offer.assert_called_once_with(job.id)

    def test_driver_within_sla_is_left_alone(self):
        """Assigned 5 min ago (SLA 15): the under-lock re-check refuses the release."""
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=5))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 0)
        offer.assert_not_called()
        alert_owner.assert_not_called()

    def test_capped_job_escalates_instead_of_releasing(self):
        """Past MAX_AUTO_REDISPATCH (3) cycles: no more re-offers — alert the owner once
        and leave the job assigned for a manual reassign/refund."""
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=20),
                   redispatch_count=3, owner_alerted_at=None)
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 0)
        offer.assert_not_called()
        self.assertEqual(locked.status, "assigned")  # untouched
        self.assertIsNotNone(locked.owner_alerted_at)
        alert_owner.assert_called_once()

    def test_picked_up_between_scan_and_lock_is_skipped(self):
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=20))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=None)
        self.assertEqual(count, 0)
        offer.assert_not_called()
        alert_owner.assert_not_called()

    def test_sla_is_configurable_from_settings(self):
        """DELIVERY_PICKUP_SLA_MINUTES=30: a driver idle 20 min is still within SLA."""
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=20))
        count, alert_owner, offer, locked = self._run(
            candidate=job, locked_job=job, sla_minutes=30
        )
        self.assertEqual(count, 0)
        offer.assert_not_called()


# ── D G4: FAILED re-alert ─────────────────────────────────────────────────────

    # Wave L L-02: food-aware pickup SLA

    def test_food_not_ready_holds_driver_past_assigned_sla(self):
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=20),
                   food_ready_at=_NOW + timedelta(minutes=10))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 0)
        offer.assert_not_called()
        alert_owner.assert_not_called()
        self.assertEqual(locked.status, "assigned")

    def test_food_ready_within_sla_is_not_released(self):
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=40),
                   food_ready_at=_NOW - timedelta(minutes=5))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 0)
        offer.assert_not_called()

    def test_food_ready_past_sla_is_released(self):
        job = _job(status="assigned", assigned_at=_NOW - timedelta(minutes=40),
                   food_ready_at=_NOW - timedelta(minutes=20))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 1)
        self.assertEqual(locked.status, "searching")
        offer.assert_called_once_with(job.id)

    def test_at_restaurant_driver_waiting_on_food_is_not_released(self):
        job = _job(status="at_restaurant", assigned_at=_NOW - timedelta(minutes=20),
                   food_ready_at=_NOW + timedelta(minutes=10))
        count, alert_owner, offer, locked = self._run(candidate=job, locked_job=job)
        self.assertEqual(count, 0)
        offer.assert_not_called()
        self.assertEqual(locked.status, "at_restaurant")


class RealertFailedJobsTests(SimpleTestCase):
    def _run(self, *, candidate, claimed=1):
        """Drive Command._realert_failed_jobs.

        candidate: the FAILED job the scan yields (or None). claimed: what the atomic
        owner_alerted_at claim returns (1 = this caller won the throttle, 0 = already
        alerted within the hour). Returns (count, alert_owner_mock).
        """
        alert_owner = MagicMock()
        with patch("accounts.models.DeliveryJob") as DJ:
            DJ.Status.FAILED = "failed"
            DJ.Resolution.REFUNDED_CANCELLED = "refunded_cancelled"
            DJ.objects.filter.return_value.exclude.return_value = (
                [candidate] if candidate else []
            )
            (DJ.objects.filter.return_value.filter.return_value
                .update.return_value) = claimed
            count = Command()._realert_failed_jobs(_NOW, alert_owner)
        return count, alert_owner

    def test_failed_job_past_an_hour_realerts(self):
        job = _job(status="failed", failed_at=_NOW - timedelta(minutes=120),
                   owner_alerted_at=None)
        count, alert_owner = self._run(candidate=job, claimed=1)
        self.assertEqual(count, 1)
        alert_owner.assert_called_once()
        _args, _kwargs = alert_owner.call_args
        self.assertEqual(_args[1], "ORD-1")  # (tenant_id, order_number, title, body)
        self.assertIn("still needs a decision", _args[3])

    def test_alert_within_the_hour_is_throttled(self):
        """The claim lost (owner_alerted_at was set < 1h ago by a previous run): no
        second alert — the throttle is the atomic update, not a re-read."""
        job = _job(status="failed", failed_at=_NOW - timedelta(minutes=120),
                   owner_alerted_at=_NOW - timedelta(minutes=30))
        count, alert_owner = self._run(candidate=job, claimed=0)
        self.assertEqual(count, 0)
        alert_owner.assert_not_called()

    def test_no_failed_jobs_is_noop(self):
        count, alert_owner = self._run(candidate=None)
        self.assertEqual(count, 0)
        alert_owner.assert_not_called()


# ── D G3: missing-job backfill ────────────────────────────────────────────────

class BackfillMissingJobsTests(SimpleTestCase):
    def _run(self, *, tenant, orders, job_numbers=None, created=True):
        """Drive Command._backfill_missing_jobs with the DB mocked.

        tenant: the tenant mock (profile attached). orders: tenant-schema orders the
        scan yields. job_numbers: existing DeliveryJob order_numbers for the tenant.
        created: what get_or_create reports. Returns (count, dispatch_mock, dj_mock).
        """
        with patch("tenancy.models.Tenant") as TenantM, \
                patch("accounts.models.DeliveryJob") as DJ, \
                patch("menu.models.Order") as OrderM, \
                patch("tenancy.delivery_pricing.split_delivery_fee") as split_fee, \
                patch("accounts.dispatch.start_dispatch") as dispatch, \
                patch("django_tenants.utils.schema_context", _noop_cm):
            TenantM.LifecycleStatus.ACTIVE = "active"
            (TenantM.objects.filter.return_value.exclude.return_value
                .select_related.return_value) = [tenant]
            DJ.Status.SEARCHING = "searching"
            DJ.objects.filter.return_value.values_list.return_value = list(job_numbers or [])
            OrderM.FulfillmentType.DELIVERY = "delivery"
            for name, val in [
                ("SCHEDULED", "scheduled"), ("CANCELLED", "cancelled"),
                ("COMPLETED", "completed"),
            ]:
                setattr(OrderM.Status, name, val)
            (OrderM.objects.filter.return_value.exclude.return_value
                .exclude.return_value) = list(orders)
            split_fee.return_value = {
                "driver_payout": Decimal("10.00"),
                "platform_commission": Decimal("0.00"),
                "commission_pct": Decimal("0"),
            }
            new_job = MagicMock()
            DJ.objects.get_or_create.return_value = (new_job, created)
            count = Command()._backfill_missing_jobs(_NOW)
        return count, dispatch, DJ

    def _tenant(self, enabled=True):
        t = MagicMock()
        t.id = 7
        t.schema_name = "resto7"
        profile = MagicMock()
        profile.platform_delivery_enabled = enabled
        profile.address = "1 Rue Test"
        profile.lat = 35.7
        profile.lng = -5.8
        profile.business_type = "restaurant"
        t.profile = profile
        return t

    def _order(self, number="ORD-9"):
        o = MagicMock()
        o.order_number = number
        o.delivery_address = "2 Ave Client"
        o.delivery_lat = 35.71
        o.delivery_lng = -5.81
        o.delivery_fee = Decimal("15.00")
        return o

    def test_stranded_order_gets_a_job_and_dispatch(self):
        count, dispatch, DJ = self._run(
            tenant=self._tenant(enabled=True), orders=[self._order()], job_numbers=[]
        )
        self.assertEqual(count, 1)
        DJ.objects.get_or_create.assert_called_once()
        _args, kwargs = DJ.objects.get_or_create.call_args
        self.assertEqual(kwargs["tenant_id"], 7)
        self.assertEqual(kwargs["order_number"], "ORD-9")
        self.assertEqual(kwargs["defaults"]["status"], "searching")
        dispatch.assert_called_once()

    def test_platform_delivery_off_is_skipped(self):
        count, dispatch, DJ = self._run(
            tenant=self._tenant(enabled=False), orders=[self._order()], job_numbers=[]
        )
        self.assertEqual(count, 0)
        DJ.objects.get_or_create.assert_not_called()
        dispatch.assert_not_called()

    def test_racing_checkout_win_is_not_recounted(self):
        """get_or_create lost the race (created=False): the checkout's job stands, this
        run counts nothing and does not re-dispatch."""
        count, dispatch, DJ = self._run(
            tenant=self._tenant(enabled=True), orders=[self._order()],
            job_numbers=[], created=False,
        )
        self.assertEqual(count, 0)
        dispatch.assert_not_called()

    def test_no_stranded_orders_is_noop(self):
        count, dispatch, DJ = self._run(
            tenant=self._tenant(enabled=True), orders=[], job_numbers=[]
        )
        self.assertEqual(count, 0)
        DJ.objects.get_or_create.assert_not_called()
