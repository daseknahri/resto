"""Run 8 G3a — admin rides list pagination (A-08).

A-08: GET /api/admin/rides/ returned a bare 50-row array — the 50-cap was silent
and older rides were unreachable. The response is now the envelope
{results, total, page, page_size} with ?page= (1-based, default 1) and
?page_size= (default 50, clamped to 1..200).

Unit-level (SimpleTestCase + mocks — no real DB), following test_flash_sales.py.
The real RideRequest.Status enum is kept (the view validates ?status= against it);
only RideRequest.objects is stubbed with a fake queryset.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status as http_status
from rest_framework.test import APIRequestFactory

from accounts.models import RideRequest, User
from accounts.ride_views import AdminRideListView


def _admin():
    u = MagicMock()
    u.__class__ = User
    u.is_authenticated = True
    u.is_platform_admin = True
    u.is_superuser = True
    u.is_staff = True
    return u


class _FakeQS:
    """Minimal queryset stand-in: filter/count/slice over an in-memory list."""

    def __init__(self, rides):
        self._rides = list(rides)

    def filter(self, **kw):
        return _FakeQS([r for r in self._rides if all(getattr(r, k) == v for k, v in kw.items())])

    def count(self):
        return len(self._rides)

    def __getitem__(self, key):
        return self._rides[key]


def _make_ride(ride_id, ride_status="searching"):
    r = MagicMock()
    r.id = ride_id
    r.kind = "ride"
    r.status = ride_status
    r.fare = Decimal("45.00")
    r.payment_method = "cash"
    r.paid_with_wallet = False
    r.distance_km = 3.5
    r.pickup_address = "A"
    r.dropoff_address = "B"
    r.created_at = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
    r.completed_at = None
    r.rider_id = 10
    r.rider = MagicMock()
    r.rider.id = 10
    r.rider.name = "Aicha"
    r.rider.phone = "0611223344"
    r.driver_id = None
    r.driver = None
    return r


class AdminRideListEnvelopeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminRideListView.as_view()
        # Newest first: the view's order_by("-created_at") is mocked away (the mock
        # chain returns this list as-is), so the fake must already be in the order
        # production returns — id descending here.
        self.rides = [_make_ride(i, "completed" if i % 3 == 0 else "searching") for i in range(60, 0, -1)]

    def _get(self, query=None):
        url = "/api/admin/rides/"
        if query:
            url += "?" + query
        req = self.factory.get(url)
        req.user = _admin()
        return req

    def _call(self, query=None):
        qs = _FakeQS(self.rides)
        manager = MagicMock()
        manager.select_related.return_value.order_by.return_value = qs
        with patch.object(RideRequest, "objects", manager), \
             patch("sales.audit.log_admin_action"):
            return self.view(self._get(query))

    def test_default_page_returns_envelope_with_first_50_of_60(self):
        resp = self._call()
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        # The response is an envelope now, not the old bare array.
        self.assertIsInstance(resp.data, dict)
        self.assertEqual(resp.data["total"], 60)
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["page_size"], 50)
        self.assertEqual(len(resp.data["results"]), 50)
        self.assertEqual(resp.data["results"][0]["id"], 60)  # newest first

    def test_page_2_with_page_size_10(self):
        resp = self._call("page=2&page_size=10")
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 60)
        self.assertEqual(resp.data["page"], 2)
        self.assertEqual(resp.data["page_size"], 10)
        self.assertEqual(len(resp.data["results"]), 10)
        self.assertEqual(resp.data["results"][0]["id"], 50)

    def test_page_size_clamped_to_200(self):
        resp = self._call("page_size=500")
        self.assertEqual(resp.data["page_size"], 200)
        self.assertEqual(len(resp.data["results"]), 60)

    def test_bad_page_falls_back_to_page_1(self):
        resp = self._call("page=abc")
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(len(resp.data["results"]), 50)

    def test_status_filter_applies_before_count(self):
        resp = self._call("status=completed")
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 20)  # every 3rd of 60
        self.assertTrue(all(r["status"] == "completed" for r in resp.data["results"]))

    def test_invalid_status_still_400(self):
        resp = self._call("status=bogus")
        self.assertEqual(resp.status_code, http_status.HTTP_400_BAD_REQUEST)


# Run 8 G3a A2-07 — delivery jobs list envelope (same fix class as the rides list).
from unittest.mock import MagicMock, patch

from accounts.views import AdminDeliveryJobListView


class AdminDeliveryJobListEnvelopeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDeliveryJobListView.as_view()

    def _get(self, query=""):
        req = self.factory.get("/api/admin/delivery-jobs/" + query)
        req.user = _admin()
        return self.view(req)

    @patch("accounts.views.log_admin_action")
    @patch("accounts.views._batch_restaurant_phones", return_value={})
    @patch("accounts.views._batch_business_types", return_value={})
    @patch("accounts.views._serialize_delivery_job")
    @patch("accounts.models.DeliveryJob.objects")
    def test_envelope_and_total(self, mock_objs, mock_ser, mock_biz, mock_phones, mock_log):
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.count.return_value = 250
        job = MagicMock()
        job.tenant_id = 7
        job.driver_id = None
        qs.__getitem__.return_value = [job]
        mock_objs.select_related.return_value.order_by.return_value = qs
        mock_ser.return_value = {"id": 1, "tenant_id": 7}
        with patch("tenancy.models.Tenant.objects") as mock_tenant_objs:
            mock_tenant_objs.filter.return_value.values_list.return_value = [(7, "Chez Test")]
            resp = self._get()
        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], 250)
        self.assertEqual(resp.data["page"], 1)
        self.assertEqual(resp.data["page_size"], 100)
        self.assertEqual(resp.data["results"][0]["tenant_name"], "Chez Test")

    @patch("accounts.views.log_admin_action")
    @patch("accounts.views._batch_restaurant_phones", return_value={})
    @patch("accounts.views._batch_business_types", return_value={})
    @patch("accounts.views._serialize_delivery_job", return_value={"id": 2})
    @patch("accounts.models.DeliveryJob.objects")
    def test_page_2_slices_the_queryset(self, mock_objs, mock_ser, mock_biz, mock_phones, mock_log):
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.count.return_value = 250
        job = MagicMock()
        job.tenant_id = 7
        job.driver_id = None
        qs.__getitem__.return_value = [job]
        mock_objs.select_related.return_value.order_by.return_value = qs
        with patch("tenancy.models.Tenant.objects") as mock_tenant_objs:
            mock_tenant_objs.filter.return_value.values_list.return_value = [(7, "Chez Test")]
            resp = self._get("?page=2&page_size=10")
        self.assertEqual(resp.data["page"], 2)
        self.assertEqual(resp.data["page_size"], 10)
        qs.__getitem__.assert_called_with(slice(10, 20))
