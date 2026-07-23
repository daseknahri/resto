"""
Tests for the "driver arriving" web-push to the restaurant:
  - DriverPositionUpdateView    POST /api/driver/position/

When a driver assigned to a delivery job (pre-pickup: ASSIGNED / AT_RESTAURANT)
posts a position update within ARRIVAL_PROXIMITY_KM of the job's pickup point,
the restaurant gets a one-time web-push ("Driver arriving") and the job's
``pickup_arrival_notified`` flag is set so it never fires twice for the same job.

All tests are unit-level (SimpleTestCase + mocks — no real DB), mirroring the
style in test_driver_views.py. These DB-adjacent lookups (DeliveryJob.objects,
Tenant.objects) are all mocked at the class level, so no Postgres connection is
required to run this file.

RISK IDENTITY-1: DriverPositionUpdateView now authenticates via
CustomerSessionAuthentication + IsCustomer, so the driver arrives as request.user
(force-authenticated below) instead of being re-fetched from the session.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import (
    DriverPositionUpdateView,
    ARRIVAL_PROXIMITY_KM,
    _pickup_distance_km,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(pk=1, is_driver=True):
    """A real (unsaved) Customer so it passes IsCustomer's principal check."""
    c = Customer(id=pk, is_driver=is_driver)
    c.save = MagicMock()
    return c


def _make_job(pk=1, status_val="assigned", tenant_id=1, order_number="ORD-001",
              pickup_lat=33.5731, pickup_lng=-7.5898, pickup_arrival_notified=False):
    j = MagicMock()
    j.pk = pk
    j.id = pk
    j.status = status_val
    j.tenant_id = tenant_id
    j.order_number = order_number
    j.pickup_lat = pickup_lat
    j.pickup_lng = pickup_lng
    j.pickup_arrival_notified = pickup_arrival_notified
    return j


def _make_tenant(schema_name="tenant_demo"):
    t = MagicMock()
    t.schema_name = schema_name
    return t


class _DJPatch:
    """Context manager that patches accounts.models.DeliveryJob so the local
    ``from .models import DeliveryJob`` import inside the view picks up the mock,
    and wires .objects.filter(...).first() to return a fixed job (or None)."""

    def __init__(self, job):
        self.job = job
        self._patcher = patch("accounts.models.DeliveryJob")

    def __enter__(self):
        mock_dj = self._patcher.__enter__()
        mock_dj.Status.ASSIGNED = "assigned"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"
        qs = MagicMock()
        qs.first.return_value = self.job
        mock_dj.objects.filter.return_value = qs
        self.mock_dj = mock_dj
        return mock_dj

    def __exit__(self, *exc):
        return self._patcher.__exit__(*exc)


class DriverArrivalPushTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverPositionUpdateView.as_view()

    def _post(self, data, customer=None):
        req = self.factory.post("/api/driver/position/", data, format="json")
        req.session = {}
        force_authenticate(req, user=customer if customer is not None else _make_customer())
        return req

    # (a) Close position -> exactly one push enqueued + flag set on the job.
    @patch("accounts.tasks.enqueue")
    @patch("tenancy.models.Tenant")
    def test_close_position_sends_one_push_and_sets_flag(self, mock_tenant, mock_enqueue):
        customer = _make_customer()
        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898)
        mock_tenant.objects.filter.return_value.first.return_value = _make_tenant("tenant_demo")

        # Same coords as pickup => distance 0km, well within threshold.
        req = self._post({"lat": 33.5731, "lng": -7.5898}, customer=customer)
        with _DJPatch(job):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_enqueue.call_count, 1)
        args = mock_enqueue.call_args[0]
        self.assertEqual(args[2], "Driver arriving")
        self.assertIn("ORD-001", args[3])
        self.assertEqual(args[4], "/owner/orders")
        self.assertTrue(job.pickup_arrival_notified)
        job.save.assert_called_once_with(update_fields=["pickup_arrival_notified"])

    # (b) A second update (still close / flag already set) must NOT push again.
    @patch("accounts.tasks.enqueue")
    @patch("tenancy.models.Tenant")
    def test_second_close_update_does_not_repush(self, mock_tenant, mock_enqueue):
        customer = _make_customer()
        mock_tenant.objects.filter.return_value.first.return_value = _make_tenant("tenant_demo")

        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898, pickup_arrival_notified=False)

        # First call: job not yet notified -> found by the filter, push fires, flag set.
        req1 = self._post({"lat": 33.5731, "lng": -7.5898}, customer=customer)
        with _DJPatch(job):
            resp1 = self.view(req1)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_enqueue.call_count, 1)

        # Second call: the real query filters on pickup_arrival_notified=False, so once
        # notified the job would no longer be returned by DeliveryJob.objects.filter(...).
        # Simulate that by having the (patched) queryset return None this time.
        req2 = self._post({"lat": 33.5731, "lng": -7.5898}, customer=customer)
        with _DJPatch(None):
            resp2 = self.view(req2)

        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_enqueue.call_count, 1)  # unchanged — no second push

    # (c) Far-away position -> nothing enqueued, flag untouched.
    @patch("accounts.tasks.enqueue")
    @patch("tenancy.models.Tenant")
    def test_far_position_sends_no_push(self, mock_tenant, mock_enqueue):
        customer = _make_customer()
        mock_tenant.objects.filter.return_value.first.return_value = _make_tenant("tenant_demo")

        # Pickup in Casablanca; driver position several km away in Rabat.
        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898, pickup_arrival_notified=False)
        req = self._post({"lat": 34.0209, "lng": -6.8416}, customer=customer)
        with _DJPatch(job):
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_enqueue.assert_not_called()
        self.assertFalse(job.pickup_arrival_notified)
        job.save.assert_not_called()

    # (d) Any failure in the arrival-check block must be swallowed — position update
    #     endpoint still returns 200 with its normal body.
    @patch("accounts.tasks.enqueue")
    def test_push_failure_does_not_break_position_endpoint(self, mock_enqueue):
        customer = _make_customer()
        mock_enqueue.side_effect = RuntimeError("push backend unavailable")

        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898)
        req = self._post({"lat": 33.5731, "lng": -7.5898}, customer=customer)
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.filter.return_value.first.return_value = _make_tenant("tenant_demo")
            with _DJPatch(job):
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("lat", resp.data)
        self.assertIn("lng", resp.data)
        self.assertIn("updated_at", resp.data)
        customer.save.assert_called_once()  # the position save still happened


# ── DB-independent bonus tests (pure function + constant, no mocking needed) ──

class ArrivalProximityUnitTests(SimpleTestCase):
    def test_threshold_constant_value(self):
        self.assertEqual(ARRIVAL_PROXIMITY_KM, 0.5)

    def test_distance_within_threshold_for_identical_coords(self):
        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898)
        dist = _pickup_distance_km(33.5731, -7.5898, job)
        self.assertIsNotNone(dist)
        self.assertLessEqual(dist, ARRIVAL_PROXIMITY_KM)

    def test_distance_beyond_threshold_for_far_coords(self):
        # Casablanca pickup vs. Rabat driver position — tens of km apart.
        job = _make_job(pickup_lat=33.5731, pickup_lng=-7.5898)
        dist = _pickup_distance_km(34.0209, -6.8416, job)
        self.assertIsNotNone(dist)
        self.assertGreater(dist, ARRIVAL_PROXIMITY_KM)

    def test_distance_none_when_pickup_coords_missing(self):
        job = _make_job(pickup_lat=None, pickup_lng=None)
        dist = _pickup_distance_km(33.5731, -7.5898, job)
        self.assertIsNone(dist)
