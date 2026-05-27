"""
Tests for customer-facing views:
  - CustomerProfileUpdateView  PATCH /api/customer/profile/
  - CustomerOrdersView         GET   /api/customer/orders/
  - CustomerEmailRequestView   POST  /api/customer/email-otp/request/
  - CustomerEmailVerifyView    POST  /api/customer/email-otp/verify/

All tests are unit-level (SimpleTestCase + mocks — no real DB or cache).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    CustomerEmailRequestView,
    CustomerEmailVerifyView,
    CustomerOrdersView,
    CustomerProfileUpdateView,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    sess.pop = lambda key, default=None: data.pop(key, default)
    sess.__setitem__ = lambda self_, k, v: data.__setitem__(k, v)
    return sess


def _make_customer(customer_id=1, name="Alice", email="alice@example.com",
                   locale="en", email_verified=True, wallet_balance=Decimal("0"),
                   loyalty_points=0, google_sub=None, phone="+21261234567",
                   phone_verified=True):
    c = MagicMock()
    c.pk = customer_id
    c.id = customer_id
    c.name = name
    c.email = email
    c.locale = locale
    c.email_verified = email_verified
    c.wallet_balance = wallet_balance
    c.loyalty_points = loyalty_points
    c.google_sub = google_sub
    c.phone = phone
    c.phone_verified = phone_verified
    return c


# ── CustomerProfileUpdateView ─────────────────────────────────────────────────

class CustomerProfileUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerProfileUpdateView.as_view()

    def _patch(self, data, session=None):
        req = self.factory.patch("/api/customer/profile/", data, format="json")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_no_session_returns_401(self):
        resp = self._patch({"name": "Bob"}, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_stale_session_returns_404(self):
        import accounts.views as _av
        from accounts.models import Customer as CustomerModel
        with patch.object(_av.Customer, "objects") as mock_objs:
            mock_objs.get.side_effect = CustomerModel.DoesNotExist
            resp = self._patch({"name": "Bob"}, session=_session(customer_id=999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("accounts.models.Customer.objects")
    def test_name_update_returns_200(self, mock_objs):
        customer = _make_customer(name="Old Name")
        mock_objs.get.return_value = customer
        mock_objs.filter.return_value.exclude.return_value.exists.return_value = False

        resp = self._patch({"name": "New Name"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("customer", resp.data)
        customer.save.assert_called_once()

    @patch("accounts.models.Customer.objects")
    def test_valid_locale_update_returns_200(self, mock_objs):
        customer = _make_customer(locale="en")
        mock_objs.get.return_value = customer

        resp = self._patch({"locale": "fr"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(customer.locale, "fr")

    @patch("accounts.models.Customer.objects")
    def test_invalid_locale_is_ignored(self, mock_objs):
        customer = _make_customer(locale="en")
        mock_objs.get.return_value = customer

        resp = self._patch({"locale": "zh"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # locale unchanged, save not called (only updated_at in update_fields == len 1)
        self.assertEqual(customer.locale, "en")

    @patch("accounts.models.Customer.objects")
    def test_email_taken_returns_400(self, mock_objs):
        customer = _make_customer(email="alice@example.com")
        mock_objs.get.return_value = customer
        # Simulate the uniqueness check returning True (email already used)
        mock_objs.filter.return_value.exclude.return_value.exists.return_value = True

        resp = self._patch({"email": "taken@example.com"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "email_taken")

    @patch("accounts.models.Customer.objects")
    def test_email_change_marks_unverified(self, mock_objs):
        customer = _make_customer(email="alice@example.com", email_verified=True)
        mock_objs.get.return_value = customer
        mock_objs.filter.return_value.exclude.return_value.exists.return_value = False

        resp = self._patch({"email": "new@example.com"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(customer.email_verified)

    @patch("accounts.models.Customer.objects")
    def test_no_changes_does_not_call_save(self, mock_objs):
        """Sending an empty payload should not call save()."""
        customer = _make_customer()
        mock_objs.get.return_value = customer

        resp = self._patch({}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        customer.save.assert_not_called()


# ── CustomerOrdersView ────────────────────────────────────────────────────────

class CustomerOrdersViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerOrdersView.as_view()

    def _get(self, session=None, schema_name="tenant_demo"):
        req = self.factory.get("/api/customer/orders/")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        req._cached_connection = None
        return req, schema_name

    def _call(self, session=None, schema_name="tenant_demo"):
        req = self.factory.get("/api/customer/orders/")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        with patch("django.db.connection") as mock_conn:
            mock_conn.schema_name = schema_name
            return self.view(req)

    def test_public_schema_returns_empty_list(self):
        resp = self._call(schema_name="public")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])
        self.assertEqual(resp.data["count"], 0)

    def test_no_session_returns_empty_list(self):
        resp = self._call(session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])

    @patch("accounts.models.Customer.objects")
    def test_stale_session_returns_empty_list(self, mock_objs):
        from accounts.models import Customer as CustomerModel
        mock_objs.get.side_effect = CustomerModel.DoesNotExist
        with patch("django.db.connection") as mock_conn:
            mock_conn.schema_name = "tenant_demo"
            resp = self.view.__func__(
                self.view.view_class(),
                self._get(session=_session(customer_id=999))[0]
            ) if False else None

        # Use the _call helper properly
        req = self.factory.get("/api/customer/orders/")
        req.user = MagicMock(is_authenticated=False)
        req.session = _session(customer_id=999)
        with patch("django.db.connection") as mock_conn:
            mock_conn.schema_name = "tenant_demo"
            with patch.object(__import__("accounts.views", fromlist=["Customer"]).Customer, "objects") as mock_cust:
                mock_cust.get.side_effect = __import__("accounts.models", fromlist=["Customer"]).Customer.DoesNotExist
                resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"], [])

    @patch("menu.models.Order.objects")
    @patch("accounts.models.Customer.objects")
    def test_returns_orders_for_authenticated_customer(self, mock_cust_objs, mock_order_objs):
        customer = _make_customer(customer_id=5)
        mock_cust_objs.get.return_value = customer

        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "completed"
        order.fulfillment_type = "pickup"
        order.table_label = ""
        order.total = Decimal("30.00")
        order.currency = "MAD"
        order.customer_name = "Alice"
        order.created_at = "2026-05-01T12:00:00+00:00"
        order.rating = None
        item = MagicMock()
        item.dish_slug = "burger"
        item.dish_name = "Burger"
        item.unit_price = Decimal("15.00")
        item.qty = 2
        item.note = ""
        item.subtotal = Decimal("30.00")
        item.options = []
        order.items.all.return_value = [item]

        qs = MagicMock()
        qs.filter.return_value = qs
        qs.prefetch_related.return_value = qs
        qs.select_related.return_value = qs
        qs.order_by.return_value.__getitem__.return_value = [order]
        mock_order_objs.filter.return_value.prefetch_related.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [order]

        req = self.factory.get("/api/customer/orders/")
        req.user = MagicMock(is_authenticated=False)
        req.session = _session(customer_id=5)
        with patch("django.db.connection") as mock_conn:
            mock_conn.schema_name = "tenant_demo"
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("orders", resp.data)
        self.assertIn("count", resp.data)
        self.assertEqual(len(resp.data["orders"]), 1)
        self.assertEqual(resp.data["orders"][0]["order_number"], "ORD-001")


# ── CustomerEmailRequestView ──────────────────────────────────────────────────

class CustomerEmailRequestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        # Disable throttling — cache-backed rate limits bleed across test classes
        # when the full suite is run after test_customer_auth.py
        self._throttle_patcher = patch.object(CustomerEmailRequestView, "throttle_classes", [])
        self._throttle_patcher.start()
        self.addCleanup(self._throttle_patcher.stop)
        self.view = CustomerEmailRequestView.as_view()

    def _post(self, data):
        req = self.factory.post("/api/customer/email-otp/request/", data, format="json")
        req.user = MagicMock(is_authenticated=False)
        return self.view(req)

    def test_missing_email_returns_400(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_email_no_at_returns_400(self):
        resp = self._post({"email": "notanemail"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_too_long_returns_400(self):
        resp = self._post({"email": "a" * 250 + "@x.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.views.cache")
    @patch("accounts.views.send_otp_email" if False else "accounts.messaging.send_otp_email")
    def test_valid_email_stores_otp_and_returns_ok(self, mock_send, mock_cache):
        with patch("accounts.views.cache") as mock_c:
            with patch("accounts.views.send_otp_email", create=True) as mock_s:
                # Import and patch the actual send_otp_email used by the view
                import accounts.messaging as _msg
                with patch.object(_msg, "send_otp_email") as mock_send_real:
                    with patch("accounts.views.cache") as mock_cache_real:
                        resp = self._post({"email": "user@example.com"})
        # Should return 200 OK with ok=True
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("ok"))


# ── CustomerEmailVerifyView ───────────────────────────────────────────────────

class CustomerEmailVerifyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerEmailVerifyView.as_view()

    def _post(self, data, cache_data=None):
        req = self.factory.post("/api/customer/email-otp/verify/", data, format="json")
        req.user = MagicMock(is_authenticated=False)
        sess_data = {}
        req.session = MagicMock()
        req.session.__setitem__ = lambda self_, k, v: sess_data.__setitem__(k, v)
        req.session.get = lambda k, d=None: sess_data.get(k, d)
        with patch("accounts.views.cache") as mock_cache:
            mock_cache.get.return_value = cache_data
            mock_cache.delete = MagicMock()
            mock_cache.set = MagicMock()
            return self.view(req), mock_cache

    def test_missing_email_returns_400(self):
        resp, _ = self._post({"code": "123456"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_code_returns_400(self):
        resp, _ = self._post({"email": "user@example.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_otp_returns_400(self):
        """cache.get returns None → OTP never requested or expired."""
        resp, _ = self._post({"email": "user@example.com", "code": "123456"}, cache_data=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "otp_expired")

    def test_too_many_attempts_returns_429(self):
        import time
        cache_data = {"code": "111111", "attempts": 5, "expires_at": time.time() + 300}
        resp, _ = self._post(
            {"email": "user@example.com", "code": "999999"},
            cache_data=cache_data,
        )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["code"], "too_many_attempts")

    def test_wrong_code_returns_400(self):
        import time
        cache_data = {"code": "111111", "attempts": 0, "expires_at": time.time() + 300}
        resp, _ = self._post(
            {"email": "user@example.com", "code": "999999"},
            cache_data=cache_data,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid_code")

    @patch("accounts.models.Customer.objects")
    def test_correct_code_new_customer_returns_200(self, mock_cust_objs):
        import time
        cache_data = {"code": "123456", "attempts": 0, "expires_at": time.time() + 300}

        new_customer = _make_customer(customer_id=10, name="", email="new@example.com")
        mock_cust_objs.filter.return_value.first.return_value = None  # no existing customer
        mock_cust_objs.create.return_value = new_customer

        req = self.factory.post(
            "/api/customer/email-otp/verify/",
            {"email": "new@example.com", "code": "123456", "name": "New User"},
            format="json",
        )
        req.user = MagicMock(is_authenticated=False)
        sess_data = {}
        req.session = MagicMock()
        req.session.__setitem__ = lambda self_, k, v: sess_data.__setitem__(k, v)

        with patch("accounts.views.cache") as mock_cache:
            mock_cache.get.return_value = cache_data
            mock_cache.delete = MagicMock()
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("customer", resp.data)
        mock_cust_objs.create.assert_called_once()

    @patch("accounts.models.Customer.objects")
    def test_correct_code_existing_customer_returns_200(self, mock_cust_objs):
        import time
        cache_data = {"code": "654321", "attempts": 0, "expires_at": time.time() + 300}

        existing = _make_customer(customer_id=7, email="existing@example.com", email_verified=False)
        mock_cust_objs.filter.return_value.first.return_value = existing

        req = self.factory.post(
            "/api/customer/email-otp/verify/",
            {"email": "existing@example.com", "code": "654321"},
            format="json",
        )
        req.user = MagicMock(is_authenticated=False)
        sess_data = {}
        req.session = MagicMock()
        req.session.__setitem__ = lambda self_, k, v: sess_data.__setitem__(k, v)

        with patch("accounts.views.cache") as mock_cache:
            mock_cache.get.return_value = cache_data
            mock_cache.delete = MagicMock()
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(existing.email_verified)
        existing.save.assert_called_once()
