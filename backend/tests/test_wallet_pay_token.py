"""Tests for the wallet pay-code token (no DB).

RISK IDENTITY-1: CustomerWalletPayTokenView now authenticates via
CustomerSessionAuthentication + IsCustomer; tests force-authenticate a real
(unsaved) Customer principal instead of hand-setting request.session.
"""
from django.core import signing
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerWalletPayTokenView, _WALLET_PAY_SALT


class CustomerWalletPayTokenTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletPayTokenView.as_view()

    def _get(self, customer=None):
        req = self.factory.get("/api/customer/wallet/pay-token/")
        req.session = {}
        if customer is not None:
            force_authenticate(req, user=customer)
        return self.view(req)

    def test_no_session_returns_401(self):
        self.assertEqual(self._get(customer=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_a_token_that_round_trips_to_the_customer(self):
        resp = self._get(customer=Customer(id=7))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        token = resp.data["token"]
        self.assertTrue(token)
        # The token must decode back to the same customer id under the same salt.
        decoded = signing.loads(token, salt=_WALLET_PAY_SALT)
        self.assertEqual(decoded["cid"], 7)
