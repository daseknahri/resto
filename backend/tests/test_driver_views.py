"""
Tests for driver-related views:
  - DriverRegisterView          POST /api/driver/register/
  - DriverStatusView            PATCH /api/driver/status/
  - DriverPositionUpdateView    POST /api/driver/position/
  - DriverJobListView           GET /api/driver/jobs/
  - DriverJobAcceptView         POST /api/driver/jobs/<job_id>/accept/
  - DriverJobStatusUpdateView   PATCH /api/driver/jobs/<job_id>/status/

RISK IDENTITY-1: the driver views now authenticate via CustomerSessionAuthentication
+ IsCustomer, so the signed-in driver (a Customer with is_driver=True) arrives as
request.user instead of being re-fetched from request.session["customer_id"]. Each
view keeps its OWN is_driver / approved+online gate, so those 404/403 contracts are
unchanged — the tests below now drive them with a real (unsaved) Customer principal
rather than by making Customer.objects.get raise DoesNotExist.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import (
    DriverRegisterView,
    DriverStatusView,
    DriverPositionUpdateView,
    DriverJobListView,
    DriverJobAcceptView,
    DriverJobStatusUpdateView,
    DriverDeliveriesView,
    DriverCashoutHistoryView,
    AdminDriverApprovalView,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_customer(pk=1, is_driver=True, is_driver_online=True, driver_approved=True):
    """A real (unsaved) Customer so it passes IsCustomer's principal check
    (is_authenticated + class name). No DB is touched — save is monkeypatched."""
    c = Customer(
        id=pk,
        is_driver=is_driver,
        driver_approved=driver_approved,
        is_driver_online=is_driver_online,
        driver_vehicle="",
    )
    c.save = MagicMock()
    return c


def _authed(req, customer):
    """Attach the driver principal the way production does (via the auth stack).

    `req.session` is always set because CustomerSessionAuthentication reads it on the
    unauthenticated path (force_authenticate bypasses the authenticator entirely).
    """
    req.session = {}
    if customer is not None:
        force_authenticate(req, user=customer)
    return req


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
    j.code_attempts = 0
    j.code_locked_until = None
    j.failure_reason = ""
    j.failure_note = ""
    return j


def _noop_atomic():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


# ── DriverRegisterView ────────────────────────────────────────────────────────

class DriverRegisterViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverRegisterView.as_view()

    def _post(self, customer=None):
        return _authed(self.factory.post("/api/driver/register/"), customer)

    def test_no_session_returns_401(self):
        resp = self.view(self._post(customer=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_session_returns_401(self):
        """RISK IDENTITY-1: a stale/forged customer_id now 401s at the auth layer
        (CustomerSessionAuthentication fails closed before the view runs) instead of
        the view's old 404 — the sanctioned 404-to-401 carve-out."""
        req = self.factory.post("/api/driver/register/")
        req.session = {"customer_id": 99}
        with patch("accounts.models.Customer.objects") as mock_objs:
            mock_objs.filter.return_value.first.return_value = None
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.views._notify_admins_new_driver")
    def test_register_activates_driver(self, _notify):
        customer = _make_customer(is_driver=False)
        resp = self.view(self._post(customer=customer))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_driver"])
        self.assertTrue(customer.is_driver)
        customer.save.assert_called_once_with(update_fields=["is_driver", "updated_at"])

    def test_already_driver_no_save_called(self):
        customer = _make_customer(is_driver=True)
        resp = self.view(self._post(customer=customer))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_driver"])
        customer.save.assert_not_called()


# ── DriverStatusView ──────────────────────────────────────────────────────────

class DriverStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverStatusView.as_view()

    def _patch(self, data, customer=None):
        req = self.factory.patch("/api/driver/status/", data, format="json")
        return _authed(req, customer)

    def test_no_session_returns_401(self):
        req = self._patch({"online": True}, customer=None)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        """The is_driver gate stays in the view (deliberately NOT a permission class),
        so a signed-in customer who never applied still gets the 404 contract."""
        customer = _make_customer(is_driver=False)
        req = self._patch({"online": True}, customer=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        customer.save.assert_not_called()

    def test_go_online_updates_status(self):
        customer = _make_customer(is_driver_online=False)
        req = self._patch({"online": True}, customer=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(customer.is_driver_online)
        customer.save.assert_called_once_with(update_fields=["is_driver_online", "updated_at"])

    def test_unapproved_driver_cannot_go_online(self):
        customer = _make_customer(is_driver_online=False, driver_approved=False)
        req = self._patch({"online": True}, customer=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "pending_approval")
        customer.save.assert_not_called()

    def test_go_offline_updates_status(self):
        customer = _make_customer(is_driver_online=True)
        req = self._patch({"online": False}, customer=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.is_driver_online)

    def test_response_contains_is_driver_online(self):
        customer = _make_customer(is_driver_online=True)
        req = self._patch({"online": True}, customer=customer)
        resp = self.view(req)
        self.assertIn("is_driver_online", resp.data)


# ── DriverPositionUpdateView ──────────────────────────────────────────────────

class DriverPositionUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverPositionUpdateView.as_view()

    def _post(self, data, customer=None):
        req = self.factory.post("/api/driver/position/", data, format="json")
        return _authed(req, customer)

    def test_no_session_returns_401(self):
        req = self._post({"lat": 48.85, "lng": 2.35}, customer=None)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        customer = _make_customer(is_driver=False)
        req = self._post({"lat": 48.85, "lng": 2.35}, customer=customer)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_lat_lng_returns_400(self):
        req = self._post({}, customer=_make_customer())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_lat_returns_400(self):
        req = self._post({"lat": "bad", "lng": 2.35}, customer=_make_customer())
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views._maybe_notify_restaurant_arrival")
    def test_valid_position_returns_200(self, _arrival):
        customer = _make_customer()
        req = self._post({"lat": 33.57, "lng": -7.58}, customer=customer)
        mock_now = MagicMock()
        mock_now.isoformat.return_value = "2026-05-01T12:00:00+00:00"
        with patch("django.utils.timezone.now", return_value=mock_now):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertAlmostEqual(resp.data["lat"], 33.57)
        self.assertAlmostEqual(resp.data["lng"], -7.58)
        self.assertIn("updated_at", resp.data)
        customer.save.assert_called_once()

    @patch("accounts.views._maybe_notify_restaurant_arrival")
    def test_position_stored_on_customer(self, _arrival):
        customer = _make_customer()
        req = self._post({"lat": 10.0, "lng": 20.0}, customer=customer)
        with patch("django.utils.timezone.now", return_value=MagicMock()):
            self.view(req)
        self.assertAlmostEqual(customer.driver_lat, 10.0)
        self.assertAlmostEqual(customer.driver_lng, 20.0)


# ── DriverJobListView ─────────────────────────────────────────────────────────

class DriverJobListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobListView.as_view()

    def _get(self, customer=None):
        return _authed(self.factory.get("/api/driver/jobs/"), customer)

    def test_no_session_returns_401(self):
        req = self._get(customer=None)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        req = self._get(customer=_make_customer(is_driver=False))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_active_and_pending_keys(self):
        customer = _make_customer()

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
                req = self._get(customer=customer)
                resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("active", resp.data)
        self.assertIn("pending", resp.data)


# ── DriverDeliveriesView ──────────────────────────────────────────────────────

class DriverDeliveriesViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverDeliveriesView.as_view()

    def _get(self, customer=None):
        return _authed(self.factory.get("/api/driver/deliveries/"), customer)

    def test_no_session_returns_401(self):
        resp = self.view(self._get(customer=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        resp = self.view(self._get(customer=_make_customer(is_driver=False)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_finished_jobs(self):
        job = _make_job(status_val="delivered", driver=_make_customer())

        with patch("accounts.models.DeliveryJob") as mock_dj:
            qs = MagicMock()
            qs.order_by.return_value.__getitem__.return_value = [job]
            mock_dj.objects.filter.return_value = qs
            mock_dj.Status.DELIVERED = "delivered"
            mock_dj.Status.FAILED = "failed"
            # DriverDeliveriesView now uses _tenant_slug_name (not _serialize_delivery_job).
            with patch("accounts.views._tenant_slug_name", return_value=("demo", "Demo")):
                resp = self.view(self._get(customer=_make_customer()))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        self.assertEqual(resp.data["results"][0]["order_number"], "ORD-001")
        # Only delivered/failed are queried.
        filter_kwargs = mock_dj.objects.filter.call_args[1]
        self.assertIn("delivered", filter_kwargs["status__in"])
        self.assertIn("failed", filter_kwargs["status__in"])


# ── DriverCashoutHistoryView ──────────────────────────────────────────────────

def _make_cashout_req(pk=1, status_val="paid", tenant_id=7, amount="150.00"):
    r = MagicMock()
    r.id = pk
    r.amount = amount
    r.status = status_val
    r.tenant_id = tenant_id
    r.created_at = MagicMock()
    r.created_at.isoformat.return_value = "2026-06-01T09:00:00+00:00"
    r.resolved_at = MagicMock()
    r.resolved_at.isoformat.return_value = "2026-06-01T09:05:00+00:00"
    return r


class DriverCashoutHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverCashoutHistoryView.as_view()

    def _get(self, customer=None):
        return _authed(self.factory.get("/api/driver/cashout/history/"), customer)

    def test_no_session_returns_401(self):
        resp = self.view(self._get(customer=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        resp = self.view(self._get(customer=_make_customer(is_driver=False)))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_resolved_rows_excludes_pending(self):
        req = _make_cashout_req(status_val="paid")

        with patch("accounts.models.DriverCashoutRequest") as mock_dcr:
            qs = MagicMock()
            qs.exclude.return_value.order_by.return_value.__getitem__.return_value = [req]
            mock_dcr.objects.filter.return_value = qs
            mock_dcr.Status.PENDING = "pending"
            with patch("accounts.views._tenant_slug_name", return_value=("demo", "Demo")):
                resp = self.view(self._get(customer=_make_customer()))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["results"]), 1)
        row = resp.data["results"][0]
        self.assertEqual(row["status"], "paid")
        self.assertEqual(row["amount"], "150.00")
        self.assertEqual(row["settled_by"], "Demo")
        self.assertIn("resolved_at", row)
        # Scoped to this driver only.
        filter_kwargs = mock_dcr.objects.filter.call_args[1]
        self.assertEqual(filter_kwargs["driver_id"], 1)
        # Pending is excluded, never included in history.
        exclude_kwargs = qs.exclude.call_args[1]
        self.assertEqual(exclude_kwargs["status"], "pending")

    def test_pagination_has_more_flag(self):
        # 21 rows returned for a page size of 20 → has_more True, only 20 kept.
        rows = [_make_cashout_req(pk=i) for i in range(21)]

        with patch("accounts.models.DriverCashoutRequest") as mock_dcr:
            qs = MagicMock()
            qs.exclude.return_value.order_by.return_value.__getitem__.return_value = rows
            mock_dcr.objects.filter.return_value = qs
            mock_dcr.Status.PENDING = "pending"
            with patch("accounts.views._tenant_slug_name", return_value=("demo", "Demo")):
                resp = self.view(self._get(customer=_make_customer()))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(len(resp.data["results"]), 20)


# ── AdminDriverApprovalView ───────────────────────────────────────────────────

class AdminDriverApprovalViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminDriverApprovalView.as_view()

    def _admin_req(self, path):
        from accounts.models import User
        admin = MagicMock(spec=User)
        admin.is_platform_admin = True
        admin.is_authenticated = True
        req = self.factory.post(path)
        force_authenticate(req, user=admin)
        return req

    @patch("accounts.models.Customer.objects")
    def test_approve_sets_driver_approved(self, mock_objs):
        customer = _make_customer(driver_approved=False)
        mock_objs.get.return_value = customer
        resp = self.view(self._admin_req("/api/admin/drivers/1/approve/"), driver_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(customer.driver_approved)
        self.assertTrue(resp.data["approved"])

    @patch("accounts.models.Customer.objects")
    def test_reject_revokes_application(self, mock_objs):
        customer = _make_customer(driver_approved=False)
        mock_objs.get.return_value = customer
        resp = self.view(self._admin_req("/api/admin/drivers/1/reject/"), driver_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.is_driver)
        self.assertFalse(resp.data["is_driver"])

    def test_non_admin_forbidden(self):
        req = self.factory.post("/api/admin/drivers/1/approve/")
        # A genuine non-admin: authenticated but none of the platform-admin flags set.
        non_admin = MagicMock(is_authenticated=True, is_superuser=False, is_staff=False,
                              is_platform_admin=False)
        force_authenticate(req, user=non_admin)
        resp = self.view(req, driver_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ── DriverJobAcceptView ───────────────────────────────────────────────────────

class DriverJobAcceptViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobAcceptView.as_view()

    def _post(self, job_id, customer=None):
        req = self.factory.post(f"/api/driver/jobs/{job_id}/accept/")
        return self.view(_authed(req, customer), job_id=job_id)

    def test_no_session_returns_401(self):
        resp = self._post(1, customer=None)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_driver_offline_returns_403(self):
        """The approved+online gate stays in the view, so an offline driver still
        gets the exact 403 contract (not DRF's generic permission denial)."""
        resp = self._post(1, customer=_make_customer(is_driver_online=False))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unapproved_driver_returns_403(self):
        resp = self._post(1, customer=_make_customer(driver_approved=False))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_driver_returns_403(self):
        resp = self._post(1, customer=_make_customer(is_driver=False))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("accounts.models.DeliveryJob")
    def test_already_has_active_job_returns_409(self, mock_dj):
        customer = _make_customer(is_driver_online=True)
        mock_dj.Status.ASSIGNED = "assigned"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.SEARCHING = "searching"
        mock_dj.objects.filter.return_value.exists.return_value = True
        resp = self._post(1, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_job_not_available_returns_404(self, mock_cust_objs, mock_dj):
        # Customer.objects stays patched: this test reaches INSIDE the atomic block,
        # where the view takes the driver-row mutex (select_for_update) that
        # serialises concurrent accepts — that's a real query, not an identity read.
        customer = _make_customer(is_driver_online=True)
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
            resp = self._post(1, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ── DriverJobStatusUpdateView ─────────────────────────────────────────────────

class DriverJobStatusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobStatusUpdateView.as_view()
        # The view mutates under transaction.atomic(); neutralise it (no DB in unit tests).
        self._atomic = patch("django.db.transaction.atomic", return_value=_noop_atomic())
        self._atomic.start()

    def tearDown(self):
        self._atomic.stop()

    def _patch(self, job_id, data, customer=None):
        req = self.factory.patch(f"/api/driver/jobs/{job_id}/status/", data, format="json")
        return self.view(_authed(req, customer), job_id=job_id)

    @staticmethod
    def _wire_status(mock_dj):
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.DELIVERED = "delivered"
        mock_dj.Status.FAILED = "failed"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"
        mock_dj.FailureReason.values = ["customer_no_show", "bad_address", "driver_unable", "other"]
        mock_dj.FailureReason.CUSTOMER_NO_SHOW = "customer_no_show"

    def test_no_session_returns_401(self):
        resp = self._patch(1, {"status": "at_restaurant"}, customer=None)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_driver_returns_404(self):
        resp = self._patch(1, {"status": "at_restaurant"},
                           customer=_make_customer(is_driver=False))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.DeliveryJob")
    def test_job_not_found_returns_404(self, mock_dj):
        customer = _make_customer()
        mock_dj.DoesNotExist = Exception
        mock_dj.objects.select_for_update.return_value.get.side_effect = mock_dj.DoesNotExist
        resp = self._patch(999, {"status": "at_restaurant"}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.DeliveryJob")
    def test_invalid_transition_returns_409(self, mock_dj):
        customer = _make_customer()
        job = _make_job(status_val="assigned", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        # "delivered" is not a valid transition from "assigned"
        resp = self._patch(1, {"status": "delivered"}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("allowed", resp.data)

    @patch("accounts.models.DeliveryJob")
    def test_valid_transition_returns_200(self, mock_dj):
        customer = _make_customer()
        job = _make_job(status_val="assigned", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)

        with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "at_restaurant"}):
            with patch("accounts.views._batch_business_types", return_value={}):
                with patch("django.utils.timezone.now", return_value=MagicMock()):
                    resp = self._patch(1, {"status": "at_restaurant"}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("accounts.views._complete_delivered_order")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_delivered_transition_updates_fields(self, mock_objs, mock_dj, mock_complete):
        # Customer.objects stays patched here: the DELIVERED branch re-reads
        # driver_approved from the DB (it must not trust the principal, which was
        # hydrated at auth time and could since have been revoked).
        customer = _make_customer()
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)

        with patch("accounts.views._order_delivery_code", return_value=""):
            with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "delivered"}):
                with patch("accounts.views._batch_business_types", return_value={}):
                    with patch("django.utils.timezone.now", return_value=MagicMock()):
                        resp = self._patch(1, {"status": "delivered"}, customer=customer)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.is_driver_online)  # driver freed after delivery
        mock_complete.assert_called_once()

    @patch("accounts.views._on_job_failed")
    @patch("accounts.models.DeliveryJob")
    def test_failed_requires_reason(self, mock_dj, mock_failed):
        customer = _make_customer()
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        # No failure_reason → 400
        resp = self._patch(1, {"status": "failed"}, customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "failure_reason_required")
        mock_failed.assert_not_called()

    @patch("accounts.views._on_job_failed")
    @patch("accounts.models.DeliveryJob")
    def test_failed_with_reason_ok(self, mock_dj, mock_failed):
        customer = _make_customer()
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "failed"}):
            with patch("accounts.views._batch_business_types", return_value={}):
                with patch("django.utils.timezone.now", return_value=MagicMock()):
                    resp = self._patch(1, {"status": "failed", "failure_reason": "customer_no_show"},
                                       customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_failed.assert_called_once()

    @patch("accounts.views._on_job_failed")
    @patch("accounts.models.DeliveryJob")
    def test_failed_transition_clears_driver_online(self, mock_dj, mock_failed):
        """D-1 bug fix: a FAILED delivery must free the driver (mirrors DELIVERED),
        so a failed run doesn't strand the driver stuck 'online' server-side."""
        customer = _make_customer(is_driver_online=True)
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "failed"}):
            with patch("accounts.views._batch_business_types", return_value={}):
                with patch("django.utils.timezone.now", return_value=MagicMock()):
                    resp = self._patch(1, {"status": "failed", "failure_reason": "customer_no_show"},
                                       customer=customer)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.is_driver_online)
        customer.save.assert_any_call(update_fields=["is_driver_online", "updated_at"])
        mock_failed.assert_called_once()


# ── Part A: business_type in delivery job payloads ────────────────────────────


class BusinessTypeInJobPayloadsTests(SimpleTestCase):
    """business_type must appear in driver job payloads via a batch Profile query (no N+1)."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_driver_job_list_includes_business_type(self):
        """DriverJobListView: active and pending job cards must include business_type."""
        customer = _make_customer()

        job_active = _make_job(pk=1, status_val="assigned", driver=customer, tenant_id=42)
        job_pending = _make_job(pk=2, status_val="searching", driver=None, tenant_id=99)

        with patch("accounts.models.DeliveryJob") as mock_dj, \
             patch("accounts.views._batch_business_types", return_value={42: "grocery", 99: "pharmacy"}) as mock_biz, \
             patch("accounts.views._serialize_delivery_job",
                   side_effect=lambda j, **kw: {"id": j.id, "business_type": kw.get("business_type", "restaurant")}):

            active_qs = MagicMock()
            active_qs.select_related.return_value = [job_active]
            pending_qs = MagicMock()
            pending_qs.filter.return_value.select_related.return_value.__getitem__ = (
                lambda s, sl: [job_pending]
            )

            def _filter(**kwargs):
                if not kwargs.get("driver__isnull"):
                    return active_qs
                return pending_qs

            mock_dj.objects.filter.side_effect = _filter
            mock_dj.Status.ASSIGNED = "assigned"
            mock_dj.Status.AT_RESTAURANT = "at_restaurant"
            mock_dj.Status.PICKED_UP = "picked_up"
            mock_dj.Status.SEARCHING = "searching"

            with patch("accounts.views._job_order_summaries", return_value={}):
                req = _authed(self.factory.get("/api/driver/jobs/"), customer)
                from accounts.views import DriverJobListView
                resp = DriverJobListView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        # _batch_business_types must be called exactly once (no N+1)
        mock_biz.assert_called_once()
        # The tenant_ids passed in must cover both active and pending jobs
        called_tenant_ids = mock_biz.call_args[0][0]
        self.assertIn(42, called_tenant_ids)
        self.assertIn(99, called_tenant_ids)

    def test_batch_business_types_single_db_query(self):
        """_batch_business_types must call Profile.objects.filter exactly once."""
        from accounts.views import _batch_business_types
        from unittest.mock import patch, MagicMock

        mock_qs = MagicMock()
        mock_qs.values_list.return_value = [(1, "grocery"), (2, "pharmacy")]

        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value = mock_qs
            result = _batch_business_types({1, 2, 3})

        # Exactly one filter call (no per-row queries)
        mock_profile.objects.filter.assert_called_once()
        filter_kwargs = mock_profile.objects.filter.call_args[1]
        self.assertIn("tenant_id__in", filter_kwargs)
        self.assertEqual(result, {1: "grocery", 2: "pharmacy"})

    def test_batch_business_types_empty_set(self):
        """_batch_business_types with empty set returns {} without hitting the DB."""
        from accounts.views import _batch_business_types
        from unittest.mock import patch

        with patch("tenancy.models.Profile") as mock_profile:
            result = _batch_business_types(set())

        mock_profile.objects.filter.assert_not_called()
        self.assertEqual(result, {})

    def test_batch_business_types_missing_profile_defaults_to_restaurant(self):
        """Tenants with no Profile row get default 'restaurant' from the caller."""
        from accounts.views import _batch_business_types
        from unittest.mock import patch, MagicMock

        mock_qs = MagicMock()
        # Only tenant 1 has a Profile row
        mock_qs.values_list.return_value = [(1, "grocery")]

        with patch("tenancy.models.Profile") as mock_profile:
            mock_profile.objects.filter.return_value = mock_qs
            result = _batch_business_types({1, 2})

        # tenant 2 missing → not in result; caller defaults to "restaurant"
        self.assertEqual(result.get(1), "grocery")
        self.assertNotIn(2, result)

    def test_serialize_delivery_job_includes_business_type_field(self):
        """_serialize_delivery_job must include business_type in its output."""
        from accounts.views import _serialize_delivery_job

        job = _make_job(pk=5, status_val="assigned", tenant_id=10)
        # Minimal mocking: slug/name lookup will call _tenant_slug_name
        with patch("accounts.views._tenant_slug_name", return_value=("demo", "Demo")):
            with patch("accounts.views._job_distance_km", return_value=None):
                data = _serialize_delivery_job(job, business_type="pharmacy")

        self.assertIn("business_type", data)
        self.assertEqual(data["business_type"], "pharmacy")

    def test_serialize_delivery_job_defaults_business_type_restaurant(self):
        """When business_type is not supplied, it defaults to 'restaurant'."""
        from accounts.views import _serialize_delivery_job

        job = _make_job(pk=6, status_val="assigned", tenant_id=11)
        with patch("accounts.views._tenant_slug_name", return_value=("cafe", "The Cafe")):
            with patch("accounts.views._job_distance_km", return_value=None):
                data = _serialize_delivery_job(job)

        self.assertEqual(data.get("business_type"), "restaurant")

    def test_serialize_delivery_job_distance_to_pickup_null_without_driver_gps(self):
        """No driver coords supplied → distance_to_pickup_km is None (field present)."""
        from accounts.views import _serialize_delivery_job

        job = _make_job(pk=7, status_val="searching", tenant_id=12)
        job.pickup_lat = 33.5
        job.pickup_lng = -7.6
        with patch("accounts.views._tenant_slug_name", return_value=("cafe", "The Cafe")):
            with patch("accounts.views._job_distance_km", return_value=None):
                data = _serialize_delivery_job(job)

        self.assertIn("distance_to_pickup_km", data)
        self.assertIsNone(data["distance_to_pickup_km"])

    def test_serialize_delivery_job_distance_to_pickup_computed_with_driver_gps(self):
        """Driver coords + job pickup coords → a rounded straight-line km is returned."""
        from accounts.views import _serialize_delivery_job

        job = _make_job(pk=8, status_val="searching", tenant_id=13)
        job.pickup_lat = 33.5731
        job.pickup_lng = -7.5898
        with patch("accounts.views._tenant_slug_name", return_value=("cafe", "The Cafe")):
            with patch("accounts.views._job_distance_km", return_value=None):
                data = _serialize_delivery_job(
                    job, driver_lat=33.5650, driver_lng=-7.6100,
                )

        self.assertIsNotNone(data["distance_to_pickup_km"])
        self.assertIsInstance(data["distance_to_pickup_km"], float)
        self.assertGreater(data["distance_to_pickup_km"], 0)

    def test_pickup_distance_km_none_when_pickup_coords_missing(self):
        """_pickup_distance_km returns None if the pickup has no coordinates."""
        from accounts.views import _pickup_distance_km

        job = _make_job(pk=9, status_val="searching")
        job.pickup_lat = None
        job.pickup_lng = None
        self.assertIsNone(_pickup_distance_km(33.5, -7.6, job))
