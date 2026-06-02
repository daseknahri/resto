"""Tests for CustomerWalletTransferView (P2P wallet gifting).

The feature-flag gate runs before any DB access, so it's covered by a no-DB
SimpleTestCase. The money-movement itself is covered in test_wallet_service.py.
"""
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerWalletTransferView


class CustomerWalletTransferGateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerWalletTransferView.as_view()

    def _post(self, data=None, session=None):
        req = self.factory.post("/api/customer/wallet/transfer/", data or {}, format="json")
        req.session = session if session is not None else {}
        return self.view(req)

    @override_settings(WALLET_P2P_ENABLED=False)
    def test_disabled_returns_403_before_anything_else(self):
        # Even with a valid-looking session, the flag gate wins.
        resp = self._post({"recipient_phone": "+212600000000", "amount": "10.00"},
                          session={"customer_id": 1})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(WALLET_P2P_ENABLED=True)
    def test_enabled_but_unauthenticated_returns_401(self):
        resp = self._post({"recipient_phone": "+212600000000", "amount": "10.00"}, session={})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(WALLET_P2P_ENABLED=True, WALLET_DEFAULT_DIAL_CODE="")
    def test_unnormalizable_phone_returns_400_before_db(self):
        # Authenticated, but a local number with no default dial code can't be resolved
        # to E.164 → rejected before any DB lookup.
        resp = self._post({"recipient_phone": "0612345678", "amount": "10.00"},
                          session={"customer_id": 1})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_phone")
