"""Tests for CustomerWalletTransferView (P2P wallet gifting).

The money-movement itself is covered in test_wallet_service.py.

RISK IDENTITY-1: the view reads the principal via customer_or_none(request) instead of
request.session["customer_id"], but deliberately stays AllowAny so the WALLET_P2P_ENABLED
gate still answers 403 BEFORE auth ("this feature doesn't exist" outranks "who are you")
— pinned by test_disabled_returns_403_before_anything_else below.

Note: mounting CustomerSessionAuthentication means DRF hydrates the Customer principal in
initial(), i.e. one DB lookup now happens even on the flag-disabled path (this file's
tests force-authenticate, which bypasses the authenticator, so they stay no-DB). That is
the uniform cost of the IDENTITY-1 keystone; the RESPONSE ordering is unchanged because
AllowAny lets the request reach post(), where the flag is checked first.
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import CustomerWalletTransferView


class CustomerWalletTransferGateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletTransferView.as_view()

    def _post(self, data=None, customer_id=None):
        req = self.factory.post("/api/customer/wallet/transfer/", data or {}, format="json")
        # Mirror production: the session still carries customer_id (WalletTransferThrottle
        # keys on it) AND the auth stack hydrates the principal onto request.user.
        req.session = {"customer_id": customer_id} if customer_id is not None else {}
        if customer_id is not None:
            c = Customer(id=customer_id)
            c.save = MagicMock()
            force_authenticate(req, user=c)
        return self.view(req)

    @override_settings(WALLET_P2P_ENABLED=False)
    def test_disabled_returns_403_before_anything_else(self):
        # Even with a fully signed-in customer, the flag gate wins.
        resp = self._post({"recipient_phone": "+212600000000", "amount": "10.00"},
                          customer_id=1)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(WALLET_P2P_ENABLED=True)
    def test_enabled_but_unauthenticated_returns_401(self):
        resp = self._post({"recipient_phone": "+212600000000", "amount": "10.00"}, customer_id=None)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(WALLET_P2P_ENABLED=True)
    def test_rate_limited_after_burst(self):
        """Per-customer transfer throttle (20/hour) returns 429 once exceeded."""
        from django.core.cache import cache
        cache.clear()  # isolate from other tests' throttle counters
        last = None
        for _ in range(21):  # 20 allowed, 21st over the limit
            last = self._post({"recipient_phone": ""}, customer_id=999)
        self.assertEqual(last.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        cache.clear()

    @override_settings(WALLET_P2P_ENABLED=True, WALLET_DEFAULT_DIAL_CODE="")
    def test_unnormalizable_phone_returns_400_before_db(self):
        # Authenticated, but a local number with no default dial code can't be resolved
        # to E.164 → rejected before any DB lookup.
        resp = self._post({"recipient_phone": "0612345678", "amount": "10.00"},
                          customer_id=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_phone")
