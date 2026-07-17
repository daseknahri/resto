"""
Tests for order tracking and delivery rating views:
  - OrderTrackingView     GET /api/marketplace/track/<order_number>/
  - DeliveryRatingView    POST /api/marketplace/track/<order_number>/rate/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import OrderTrackingView, DeliveryRatingView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    return sess


def _make_tenant(tenant_id=1, slug="myrestaurant"):
    t = MagicMock()
    t.id = tenant_id
    t.slug = slug
    return t


def _make_job(pk=1, status_val="assigned", order_number="ORD-001", tenant_id=1):
    j = MagicMock()
    j.pk = pk
    j.id = pk
    j.status = status_val
    j.driver = None
    j.tenant_id = tenant_id
    j.order_number = order_number
    j.delivery_address = "123 St"
    j.pickup_address = "456 Ave"
    j.delivery_lat = None
    j.delivery_lng = None
    j.pickup_lat = None
    j.pickup_lng = None
    j.delivery_fee = "5.00"
    j.driver_payout = "3.00"
    j.assigned_at = None
    j.picked_up_at = None
    j.delivered_at = None
    j.failed_at = None
    j.is_terminal = False
    j.customer_driver_rating = None
    j.customer_driver_note = ""
    j.driver_customer_rating = None
    j.driver_customer_note = ""
    j.restaurant_driver_rating = None
    j.restaurant_driver_note = ""
    j.created_at = MagicMock()
    j.created_at.isoformat.return_value = "2026-05-01T10:00:00+00:00"
    return j


# ── _tracking_request_owns_order helper ───────────────────────────────────────

class TrackingOwnsOrderHelperTests(SimpleTestCase):
    """RISK IDENTITY-1: the helper now reads the customer off request.user
    (customer_or_none) instead of request.session["customer_id"]. It only touches
    request.user, so a plain namespace carrying the principal is enough to drive it."""

    def _run(self, *, principal, order_customer_id):
        from contextlib import contextmanager
        import menu.models as mm
        from django.contrib.auth.models import AnonymousUser
        from accounts.views import _tracking_request_owns_order

        @contextmanager
        def _noop_sc(*a, **k):
            yield

        request = SimpleNamespace(user=principal if principal is not None else AnonymousUser())
        tenant = SimpleNamespace(schema_name="bistro")
        vl = MagicMock()
        vl.values_list.return_value.first.return_value = order_customer_id
        with patch("django_tenants.utils.schema_context", _noop_sc), \
             patch.object(mm.Order, "objects") as mock_objs:
            mock_objs.filter.return_value = vl
            return _tracking_request_owns_order(request, tenant, "ORD-1")

    def test_no_principal_is_not_owner(self):
        self.assertFalse(self._run(principal=None, order_customer_id=5))

    def test_matching_customer_is_owner(self):
        self.assertTrue(self._run(principal=Customer(id=5), order_customer_id=5))

    def test_non_matching_customer_is_not_owner(self):
        self.assertFalse(self._run(principal=Customer(id=9), order_customer_id=5))


# ── OrderTrackingView ─────────────────────────────────────────────────────────

class OrderTrackingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OrderTrackingView.as_view()

    def _get(self, order_number="ORD-001", params=None, session=None):
        url = f"/api/marketplace/track/{order_number}/"
        req = self.factory.get(url, params or {})
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req, order_number=order_number)

    def test_missing_restaurant_param_returns_400(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_restaurant_not_found_returns_404(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = Exception
            mock_tenant.objects.get.side_effect = mock_tenant.DoesNotExist
            resp = self._get(params={"restaurant": "unknown-slug"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_job_not_found_returns_404(self):
        tenant = _make_tenant()
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.DoesNotExist = Exception
                mock_dj.objects.select_related.return_value.get.side_effect = mock_dj.DoesNotExist
                resp = self._get(params={"restaurant": "myrestaurant"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "no_job")

    def test_valid_request_returns_200(self):
        tenant = _make_tenant()
        job = _make_job()

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.select_related.return_value.get.return_value = job
                with patch("accounts.views._tracking_request_owns_order", return_value=True):
                    with patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "assigned"}):
                        resp = self._get(params={"restaurant": "myrestaurant"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("id", resp.data)

    def test_non_owner_forbidden(self):
        """Driver phone + live position must not leak to a non-owner who guesses an order #."""
        tenant = _make_tenant()
        job = _make_job()
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.select_related.return_value.get.return_value = job
                with patch("accounts.views._tracking_request_owns_order", return_value=False):
                    resp = self._get(params={"restaurant": "myrestaurant"})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_data_includes_driver_position(self):
        tenant = _make_tenant()
        driver = MagicMock()
        driver.id = 5
        driver.name = "Driver"
        driver.phone = "0600000000"
        driver.driver_lat = 33.5
        driver.driver_lng = -7.6
        driver.is_driver_online = True
        driver.driver_position_updated_at = None
        job = _make_job()
        job.driver = driver

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.select_related.return_value.get.return_value = job
                with patch("accounts.views._tracking_request_owns_order", return_value=True):
                    resp = self._get(params={"restaurant": "myrestaurant"})

        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ── DeliveryRatingView ────────────────────────────────────────────────────────

class DeliveryRatingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DeliveryRatingView.as_view()

    def _post(self, order_number, data, params=None, session=None, user=None, tenant=None):
        url = f"/api/marketplace/track/{order_number}/rate/"
        req = self.factory.post(url, data, format="json")
        if params:
            req.GET = req.GET.copy()
            for k, v in params.items():
                req.GET[k] = v
        req.user = user or MagicMock(is_authenticated=False)
        req.session = session or _session()
        if tenant:
            req.tenant = tenant
        return self.view(req, order_number=order_number)

    def test_missing_restaurant_returns_400(self):
        resp = self._post("ORD-001", {"role": "customer", "score": 5})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_restaurant_not_found_returns_404(self):
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = Exception
            mock_tenant.objects.get.side_effect = mock_tenant.DoesNotExist

            req = self.factory.post("/api/marketplace/track/ORD-001/rate/",
                                    {"role": "customer", "score": 5},
                                    format="json")
            req.user = MagicMock(is_authenticated=False)
            req.session = _session()
            req.GET = req.GET.copy()
            req.GET["restaurant"] = "unknown"
            resp = self.view(req, order_number="ORD-001")

        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def _post_with_restaurant(self, order_number, data, session=None, user=None, tenant=None):
        """Helper that always includes a restaurant slug."""
        url = f"/api/marketplace/track/{order_number}/rate/?restaurant=myrestaurant"
        req = self.factory.post(url, data, format="json")
        if user is not None:
            # authentication_classes=[] means DRF's Request.user re-derives from
            # perform_authentication() rather than trusting a plain req.user
            # assignment — force_authenticate is the supported way to simulate
            # an authenticated caller here.
            force_authenticate(req, user=user)
        else:
            req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        if tenant:
            req.tenant = tenant
        return self.view(req, order_number=order_number)

    def test_job_not_found_returns_404(self):
        tenant = _make_tenant()
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.DoesNotExist = Exception
                mock_dj.objects.get.side_effect = mock_dj.DoesNotExist
                resp = self._post_with_restaurant("ORD-001", {"role": "customer", "score": 5})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_score_returns_400(self):
        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant("ORD-001", {"role": "customer", "score": 0})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_score_six_returns_400(self):
        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant("ORD-001", {"role": "customer", "score": 6})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_role_returns_400(self):
        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant("ORD-001", {"role": "manager", "score": 4})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_role_no_session_returns_401(self):
        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "customer", "score": 5},
                    session=_session(customer_id=None),
                )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_role_valid_saves_rating(self):
        # OPS-5f: the customer branch now requires the session customer to OWN the
        # order — the order (tenant schema) must report a matching customer_id.
        import menu.models as mm
        from contextlib import contextmanager

        @contextmanager
        def _noop_sc(*a, **k):
            yield

        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        order = SimpleNamespace(customer_id=42)
        order_qs = MagicMock()
        order_qs.only.return_value.first.return_value = order
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj, \
                 patch("django_tenants.utils.schema_context", _noop_sc), \
                 patch.object(mm.Order, "objects") as mock_order_objs:
                mock_dj.objects.get.return_value = job
                mock_order_objs.filter.return_value = order_qs
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "customer", "score": 5, "note": "Fast!"},
                    user=Customer(id=42),
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["score"], 5)
        job.save.assert_called_once()

    def test_customer_role_already_rated_returns_400(self):
        """B14: a second customer-role POST for an already-rated leg 400s with
        code=already_rated instead of overwriting the first rating."""
        import menu.models as mm
        from contextlib import contextmanager

        @contextmanager
        def _noop_sc(*a, **k):
            yield

        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        job.customer_driver_rating = 5  # already rated
        order = SimpleNamespace(customer_id=42)
        order_qs = MagicMock()
        order_qs.only.return_value.first.return_value = order
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj, \
                 patch("django_tenants.utils.schema_context", _noop_sc), \
                 patch.object(mm.Order, "objects") as mock_order_objs:
                mock_dj.objects.get.return_value = job
                mock_order_objs.filter.return_value = order_qs
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "customer", "score": 1, "note": "trying to overwrite"},
                    user=Customer(id=42),
                )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "already_rated")
        job.save.assert_not_called()
        self.assertEqual(job.customer_driver_rating, 5)

    def test_customer_role_non_owner_returns_403(self):
        """OPS-5f: a session customer who doesn't own the order cannot rate the driver."""
        import menu.models as mm
        from contextlib import contextmanager

        @contextmanager
        def _noop_sc(*a, **k):
            yield

        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        order = SimpleNamespace(customer_id=999)  # owned by someone else
        order_qs = MagicMock()
        order_qs.only.return_value.first.return_value = order
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj, \
                 patch("django_tenants.utils.schema_context", _noop_sc), \
                 patch.object(mm.Order, "objects") as mock_order_objs:
                mock_dj.objects.get.return_value = job
                mock_order_objs.filter.return_value = order_qs
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "customer", "score": 5, "note": "Fast!"},
                    user=Customer(id=42),
                )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "not_order_owner")
        job.save.assert_not_called()

    def test_driver_role_wrong_session_returns_403(self):
        tenant = _make_tenant()
        driver = MagicMock()
        driver.id = 7
        job = _make_job(status_val="delivered")
        job.driver = driver
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                # customer_id=42 doesn't match driver.id=7
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "driver", "score": 4},
                    user=Customer(id=42),
                )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_role_valid_saves_rating(self):
        tenant = _make_tenant()
        driver = MagicMock()
        driver.id = 7
        job = _make_job(status_val="delivered")
        job.driver = driver
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "driver", "score": 4},
                    user=Customer(id=7),  # driver id = 7
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["score"], 4)

    def test_driver_role_already_rated_returns_400(self):
        """B14: a second driver-role POST for an already-rated leg must not
        silently overwrite the first rating."""
        tenant = _make_tenant()
        driver = MagicMock()
        driver.id = 7
        job = _make_job(status_val="delivered")
        job.driver = driver
        job.driver_customer_rating = 4  # already rated
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "driver", "score": 5},
                    user=Customer(id=7),
                )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "already_rated")
        job.save.assert_not_called()
        # The original rating must be untouched.
        self.assertEqual(job.driver_customer_rating, 4)

    def test_restaurant_role_unauthenticated_returns_401(self):
        tenant = _make_tenant()
        job = _make_job(status_val="delivered")
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "restaurant", "score": 5},
                )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_restaurant_role_no_tenant_context_returns_401(self):
        """Without session auth, request.user is AnonymousUser → 401 before tenant check."""
        tenant = _make_tenant(tenant_id=1)
        job = _make_job(status_val="delivered", tenant_id=1)
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                # No req.tenant set, no authenticated user
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "restaurant", "score": 5},
                )
        # authentication_classes=[] → request.user is AnonymousUser → 401
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_restaurant_role_valid_saves_rating(self):
        tenant = _make_tenant(tenant_id=1)
        job = _make_job(status_val="delivered", tenant_id=1)
        owner_user = MagicMock(is_authenticated=True)
        owner_tenant_ctx = SimpleNamespace(id=1)
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "restaurant", "score": 5, "note": "On time"},
                    user=owner_user,
                    tenant=owner_tenant_ctx,
                )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["score"], 5)
        job.save.assert_called_once()

    def test_restaurant_role_rejects_customer_principal(self):
        """RISK IDENTITY-1 landmine: a Customer principal is authenticated too now
        (Customer.is_authenticated is True), so the role=restaurant STAFF gate must reject
        it — a customer must not write the owner→driver rating even with a matching tenant
        context. This is the exact 'assumes the principal is a staff User' hazard."""
        tenant = _make_tenant(tenant_id=1)
        job = _make_job(status_val="delivered", tenant_id=1)
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "restaurant", "score": 5},
                    user=Customer(id=42),           # a customer principal, NOT a staff owner
                    tenant=SimpleNamespace(id=1),   # even with a matching tenant context
                )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        job.save.assert_not_called()

    def test_restaurant_role_already_rated_returns_400(self):
        """B14: a second restaurant-role POST for an already-rated leg must not
        silently overwrite the first rating."""
        tenant = _make_tenant(tenant_id=1)
        job = _make_job(status_val="delivered", tenant_id=1)
        job.restaurant_driver_rating = 3  # already rated
        owner_user = MagicMock(is_authenticated=True)
        owner_tenant_ctx = SimpleNamespace(id=1)
        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("accounts.models.DeliveryJob") as mock_dj:
                mock_dj.objects.get.return_value = job
                resp = self._post_with_restaurant(
                    "ORD-001",
                    {"role": "restaurant", "score": 1},
                    user=owner_user,
                    tenant=owner_tenant_ctx,
                )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "already_rated")
        job.save.assert_not_called()
        self.assertEqual(job.restaurant_driver_rating, 3)
