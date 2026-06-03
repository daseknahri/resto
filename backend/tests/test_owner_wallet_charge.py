"""Tests for OwnerWalletChargeView (wallet charge by pay-code). No DB."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.core import signing
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.models import User
from accounts.views import _WALLET_PAY_SALT
from menu.views import OwnerWalletChargeView


def _owner(tenant_id=1):
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.tenant_id = tenant_id
    u.role = User.Roles.TENANT_OWNER
    u.Roles = User.Roles
    return u


def _outsider():
    u = _owner(tenant_id=99)  # different tenant than the request tenant (id=1)
    return u


class OwnerWalletChargeViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWalletChargeView.as_view()

    def _post(self, data, user=None, tenant=None):
        req = self.factory.post("/api/owner/wallet/charge/", data, format="json")
        req.user = user or _owner()
        req.tenant = tenant or SimpleNamespace(id=1)
        return self.view(req)

    def test_non_owner_403(self):
        self.assertEqual(self._post({"token": "x", "amount": "10"}, user=_outsider()).status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_token_400(self):
        resp = self._post({"amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_token")

    def test_bad_token_400(self):
        resp = self._post({"token": "not-a-valid-token", "amount": "10"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "invalid")

    def test_valid_token_but_bad_amount_400(self):
        token = signing.dumps({"cid": 5}, salt=_WALLET_PAY_SALT)
        resp = self._post({"token": token, "amount": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
