"""Tests for customer Web Push subscribe / VAPID-key endpoints (no DB).

RISK IDENTITY-1: CustomerPushSubscribeView now authenticates via
CustomerSessionAuthentication + IsCustomer; tests force-authenticate a real
(unsaved) Customer principal instead of hand-setting request.session.
"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerPushSubscribeView, CustomerPushVapidKeyView


class CustomerPushVapidKeyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerPushVapidKeyView.as_view()

    @override_settings(VAPID_PUBLIC_KEY="abc123")
    def test_enabled_when_key_present(self):
        resp = self.view(self.factory.get("/api/customer/push-vapid-key/"))
        self.assertTrue(resp.data["enabled"])
        self.assertEqual(resp.data["public_key"], "abc123")

    @override_settings(VAPID_PUBLIC_KEY="")
    def test_disabled_when_no_key(self):
        resp = self.view(self.factory.get("/api/customer/push-vapid-key/"))
        self.assertFalse(resp.data["enabled"])
        self.assertIsNone(resp.data["public_key"])


class CustomerPushSubscribeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerPushSubscribeView.as_view()

    def _post(self, data, customer=5):
        req = self.factory.post("/api/customer/push-subscribe/", data, format="json")
        req.session = {}
        if customer is not None:
            force_authenticate(req, user=Customer(id=customer) if isinstance(customer, int) else customer)
        return self.view(req)

    def test_unauthenticated_401(self):
        self.assertEqual(self._post({}, customer=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_incomplete_subscription_400(self):
        self.assertEqual(self._post({"endpoint": "x"}).status_code, status.HTTP_400_BAD_REQUEST)

    @patch("accounts.models.CustomerPushSubscription.objects")
    def test_valid_creates_subscription_for_session_customer(self, mock_objs):
        resp = self._post({"endpoint": "https://push/x", "p256dh": "key", "auth": "secret"})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_objs.update_or_create.assert_called_once()
        _, kwargs = mock_objs.update_or_create.call_args
        self.assertEqual(kwargs["endpoint"], "https://push/x")
        self.assertEqual(kwargs["defaults"]["customer_id"], 5)

    @patch("accounts.models.CustomerPushSubscription.objects")
    def test_delete_removes_by_endpoint_and_customer(self, mock_objs):
        req = self.factory.delete("/api/customer/push-subscribe/", {"endpoint": "https://push/x"}, format="json")
        req.session = {}
        force_authenticate(req, user=Customer(id=5))
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_objs.filter.return_value.delete.assert_called_once()
