"""
Tests for driver-related views:
  - DriverRegisterView          POST /api/driver/register/
  - DriverStatusView            PATCH /api/driver/status/
  - DriverPositionUpdateView    POST /api/driver/position/
  - DriverJobListView           GET /api/driver/jobs/
  - DriverJobAcceptView         POST /api/driver/jobs/<job_id>/accept/
  - DriverJobStatusUpdateView   PATCH /api/driver/jobs/<job_id>/status/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    DriverRegisterView,
    DriverStatusView,
    DriverPositionUpdateView,
    DriverJobListView,
    DriverJobAcceptView,
    DriverJobStatusUpdateView,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    return sess


def _make_customer(pk=1, is_driver=True, is_driver_online=True):
    c = MagicMock()
    c.pk = pk
    c.id = pk
    c.is_driver = is_driver
    c.is_driver_online = is_driver_online
    c.driver_lat = None
    c.driver_lng = None
    return c


def _make_job(pk=1, status_val="assigned", driver=None, tenant_id=1, order_number="ORD-001"):
    j = MagicMock()
    j.pk = pk
    j.id = pk
    j.status = status_val
    j.driver = driver
    j.tenant_id = tenant_id
    j.order_number = order_number
    j.delivery_address = "123 St"
    j.delivery_lat = None
    j.delivery_lng = None
    j.delivery_fee = "5.00"
    j.driver_payout = "3.00"
    j.assigned_at = None
    j.picked_up_at = None
    j.delivered_at = None
    j.failed_at = None
    j.created_at = MagicMock()
    j.created_at.isoformat.return_value = "2026-05-01T10:00:00+00:00"
    return j


# ── DriverRegisterView ────────────────────────────────────────────────────────

class DriverRegisterViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRegisterView.as_view()

    def _post(self, session=None):
        req = self.factory.post("/api/driver/register/")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._post(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_customer_not_found_returns_404(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        req = self._post(session=_session(customer_id=99))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_register_activates_driver(self, mock_objs):
        customer = _make_customer(is_driver=False)
        mock_objs.get.return_value = customer
        req = self._post(session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_driver"])
        self.assertTrue(customer.is_driver)
        customer.save.assert_called_once_with(update_fields=["is_driver", "updated_at"])

    @patch("accounts.models.Customer.objects")
    def test_already_driver_no_save_called(self, mock_objs):
        customer = _make_customer(is_driver=True)
        mock_objs.get.return_value = customer
        req = self._post(session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_driver"])
        customer.save.assert_not_called()


# ── DriverStatusView ──────────────────────────────────────────────────────────

class DriverStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverStatusView.as_view()

    def _patch(self, data, session=None):
        req = self.factory.patch("/api/driver/status/", data, format="json")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._patch({"online": True}, session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_driver_not_found_returns_404(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        req = self._patch({"online": True}, session=_session(customer_id=99))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_go_online_updates_status(self, mock_objs):
        customer = _make_customer(is_driver_online=False)
        mock_objs.get.return_value = customer
        req = self._patch({"online": True}, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(customer.is_driver_online)
        customer.save.assert_called_once_with(update_fields=["is_driver_online", "updated_at"])

    @patch("accounts.models.Customer.objects")
    def test_go_offline_updates_status(self, mock_objs):
        customer = _make_customer(is_driver_online=True)
        mock_objs.get.return_value = customer
        req = self._patch({"online": False}, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.is_driver_online)

    @patch("accounts.models.Customer.objects")
    def test_response_contains_is_driver_online(self, mock_objs):
        customer = _make_customer(is_driver_online=True)
        mock_objs.get.return_value = customer
        req = self._patch({"online": True}, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertIn("is_driver_online", resp.data)


# ── DriverPositionUpdateView ──────────────────────────────────────────────────

class DriverPositionUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverPositionUpdateView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/driver/position/", data, format="json")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._post({"lat": 48.85, "lng": 2.35}, session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_driver_not_found_returns_404(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        req = self._post({"lat": 48.85, "lng": 2.35}, session=_session(customer_id=99))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_missing_lat_lng_returns_400(self, mock_objs):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        req = self._post({}, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.Customer.objects")
    def test_invalid_lat_returns_400(self, mock_objs):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        req = self._post({"lat": "bad", "lng": 2.35}, session=_session(customer_id=1))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.Customer.objects")
    def test_valid_position_returns_200(self, mock_objs):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        req = self._post({"lat": 33.57, "lng": -7.58}, session=_session(customer_id=1))
        mock_now = MagicMock()
        mock_now.isoformat.return_value = "2026-05-01T12:00:00+00:00"
        with patch("django.utils.timezone.now", return_value=mock_now):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["lat"], 33.57)
        self.assertAlmostEqual(resp.data["lng"], -7.58)
        self.assertIn("updated_at", resp.data)
        customer.save.assert_called_once()

    @patch("accounts.models.Customer.objects")
    def test_position_stored_on_customer(self, mock_objs):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        req = self._post({"lat": 10.0, "lng": 20.0}, session=_session(customer_id=1))
        with patch("django.utils.timezone.now", return_value=MagicMock()):
            self.view(req)
        self.assertAlmostEqual(customer.driver_lat, 10.0)
        self.assertAlmostEqual(customer.driver_lng, 20.0)


# ── DriverJobListView ─────────────────────────────────────────────────────────

class DriverJobListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobListView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/driver/jobs/")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return req

    def test_no_session_returns_401(self):
        req = self._get(session=_session(customer_id=None))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_driver_not_found_returns_404(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        req = self._get(session=_session(customer_id=99))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_returns_active_and_pending_keys(self, mock_objs):
        customer = _make_customer()
        mock_objs.get.return_value = customer

        job_active = _make_job(status_val="assigned", driver=customer)
        job_pending = _make_job(pk=2, status_val="searching", driver=None)

        with patch("accounts.models.DeliveryJob") as mock_dj:
            # active jobs query
            active_qs = MagicMock()
            active_qs.select_related.return_value = [job_active]
            # pending jobs query
            pending_qs = MagicMock()
            pending_qs.select_related.return_value.__getitem__.return_value = [job_pending]

            def _filter(**kwargs):
                if kwargs.get("driver__isnull"):
                    return pending_qs
                return active_qs

            mock_dj.objects.filter.side_effect = _filter
            mock_dj.Status.ASSIGNED = "assigned"
            mock_dj.Status.AT_RESTAURANT = "at_restaurant"
            mock_dj.Status.PICKED_UP = "picked_up"
            mock_dj.Status.SEARCHING = "searching"

            with patch("accounts.views._serialize_delivery_job", side_effect=lambda j, **kw: {"id": j.id}):
                req = self._get(session=_session(customer_id=1))
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("active", resp.data)
        self.assertIn("pending", resp.data)


# ── DriverJobAcceptView ───────────────────────────────────────────────────────

class DriverJobAcceptViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobAcceptView.as_view()

    def _post(self, job_id, session=None):
        req = self.factory.post(f"/api/driver/jobs/{job_id}/accept/")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return self.view(req, job_id=job_id)

    def test_no_session_returns_401(self):
        resp = self._post(1, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_driver_offline_returns_403(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        resp = self._post(1, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_already_has_active_job_returns_409(self, mock_objs, mock_dj):
        customer = _make_customer(is_driver_online=True)
        mock_objs.get.return_value = customer
        mock_dj.Status.ASSIGNED = "assigned"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.SEARCHING = "searching"
        mock_dj.objects.filter.return_value.exists.return_value = True
        resp = self._post(1, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_job_not_available_returns_404(self, mock_objs, mock_dj):
        customer = _make_customer(is_driver_online=True)
        mock_objs.get.return_value = customer
        mock_dj.Status.ASSIGNED = "assigned"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.SEARCHING = "searching"
        mock_dj.DoesNotExist = Exception
        # No active job
        mock_dj.objects.filter.return_value.exists.return_value = False
        # But job select_for_update fails
        mock_dj.objects.select_for_update.return_value.get.side_effect = mock_dj.DoesNotExist
        with patch("django.db.transaction.atomic") as mock_atomic:
            mock_atomic.return_value.__enter__ = lambda s: None
            mock_atomic.return_value.__exit__ = lambda s, *a: None
            resp = self._post(1, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ── DriverJobStatusUpdateView ─────────────────────────────────────────────────

class DriverJobStatusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobStatusUpdateView.as_view()

    def _patch(self, job_id, data, session=None):
        req = self.factory.patch(f"/api/driver/jobs/{job_id}/status/", data, format="json")
        req.session = session or _session()
        req.user = MagicMock(is_authenticated=False)
        return self.view(req, job_id=job_id)

    def test_no_session_returns_401(self):
        resp = self._patch(1, {"status": "at_restaurant"}, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_driver_not_found_returns_404(self, mock_objs):
        from accounts.models import Customer
        mock_objs.get.side_effect = Customer.DoesNotExist
        resp = self._patch(1, {"status": "at_restaurant"}, session=_session(customer_id=99))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_job_not_found_returns_404(self, mock_objs, mock_dj):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        mock_dj.DoesNotExist = Exception
        mock_dj.objects.select_related.return_value.get.side_effect = mock_dj.DoesNotExist
        resp = self._patch(999, {"status": "at_restaurant"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_invalid_transition_returns_400(self, mock_objs, mock_dj):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        job = _make_job(status_val="assigned", driver=customer)
        mock_dj.objects.select_related.return_value.get.return_value = job
        # "delivered" is not a valid transition from "assigned"
        resp = self._patch(1, {"status": "delivered"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allowed", resp.data)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_valid_transition_returns_200(self, mock_objs, mock_dj):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        job = _make_job(status_val="assigned", driver=customer)
        mock_dj.objects.select_related.return_value.get.return_value = job
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.DELIVERED = "delivered"
        mock_dj.Status.FAILED = "failed"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"

        with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "at_restaurant"}):
            with patch("django.utils.timezone.now", return_value=MagicMock()):
                resp = self._patch(1, {"status": "at_restaurant"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_delivered_transition_updates_fields(self, mock_objs, mock_dj):
        customer = _make_customer()
        mock_objs.get.return_value = customer
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_related.return_value.get.return_value = job
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.DELIVERED = "delivered"
        mock_dj.Status.FAILED = "failed"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"

        with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "delivered"}):
            with patch("django.utils.timezone.now", return_value=MagicMock()):
                resp = self._patch(1, {"status": "delivered"}, session=_session(customer_id=1))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Driver should be set offline after delivery
        self.assertFalse(customer.is_driver_online)
