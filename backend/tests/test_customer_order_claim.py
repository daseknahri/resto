"""Tests for CustomerClaimOrderView — POST /api/customer/orders/claim/.

The QR/guest soft-capture keystone: retroactively link a just-placed anonymous order to the
signed-in customer, guarded by a phone-digits match. Unit-level (SimpleTestCase + mocks — no
real DB or schema switch): tenant_context / transaction.atomic are patched to no-ops and the
Tenant + Order lookups are mocked, so the security logic is exercised without Postgres.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.authentication import CustomerSessionAuthentication
from accounts.permissions import IsCustomer
from accounts.throttles import CustomerOrderClaimThrottle
from accounts.models import Customer
from menu.models import Order
from tenancy.models import Tenant
from accounts.views import CustomerClaimOrderView


@contextmanager
def _noop_cm(*args, **kwargs):
    yield


def _customer(pk=1, phone_verified=True, phone="+212600001234", phone_digits="600001234"):
    # Real (unsaved) Customer so it passes IsCustomer's principal check; phone_digits is
    # normally set in save(), so we set it explicitly on the unsaved instance.
    return Customer(id=pk, phone_verified=phone_verified, phone=phone, phone_digits=phone_digits)


def _order(customer_id=None, phone_digits="600001234", order_number="ORD-1"):
    o = MagicMock()
    o.customer_id = customer_id
    o.customer_phone_digits = phone_digits
    o.order_number = order_number
    o.save = MagicMock()
    return o


class CustomerClaimOrderViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # isolate the per-customer customer_order_claim throttle counter
        self.factory = APIRequestFactory()
        self.view = CustomerClaimOrderView.as_view()

    def _run(self, body, principal, *, tenant_exists=True, order="__found__"):
        """Drive the view with tenant_context/atomic patched to no-ops and Tenant/Order mocked.

        order=None → the order lookup raises DoesNotExist; a mock order → found.
        """
        mock_tenant_cls = MagicMock()
        mock_tenant_cls.DoesNotExist = Tenant.DoesNotExist
        if tenant_exists:
            mock_tenant_cls.objects.get.return_value = MagicMock(
                schema_name="t_demo", slug="demo", name="Demo", id=7
            )
        else:
            mock_tenant_cls.objects.get.side_effect = Tenant.DoesNotExist

        mock_order_cls = MagicMock()
        mock_order_cls.DoesNotExist = Order.DoesNotExist
        getter = mock_order_cls.objects.select_for_update.return_value.get
        if order is None:
            getter.side_effect = Order.DoesNotExist
        elif order != "__found__":
            getter.return_value = order

        req = self.factory.post("/api/customer/orders/claim/", body, format="json")
        if principal is not None:
            force_authenticate(req, user=principal)

        with patch("tenancy.models.Tenant", mock_tenant_cls), \
                patch("menu.models.Order", mock_order_cls), \
                patch("django_tenants.utils.tenant_context", _noop_cm), \
                patch("django.db.transaction.atomic", _noop_cm):
            return self.view(req)

    # ── Auth / preconditions ──────────────────────────────────────────────────

    def test_anonymous_returns_401(self):
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"}, principal=None)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_phone_unverified_returns_403(self):
        c = _customer(phone_verified=False, phone_digits="")
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"}, principal=c)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "phone_unverified")

    def test_missing_order_number_returns_400(self):
        resp = self._run({"restaurant": "demo"}, principal=_customer())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "missing_fields")

    def test_tenant_not_found_returns_404(self):
        resp = self._run({"restaurant": "nope", "order_number": "ORD-1"},
                         principal=_customer(), tenant_exists=False)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_not_found_returns_404(self):
        resp = self._run({"restaurant": "demo", "order_number": "ORD-X"},
                         principal=_customer(), order=None)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── The security core ─────────────────────────────────────────────────────

    def test_phone_mismatch_is_refused(self):
        # An order placed with a DIFFERENT phone cannot be claimed, even if unlinked.
        o = _order(customer_id=None, phone_digits="999999999")
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"},
                         principal=_customer(phone_digits="600001234"), order=o)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "phone_mismatch")
        o.save.assert_not_called()

    def test_order_with_blank_phone_cannot_be_claimed(self):
        # A guest order that captured no phone has nothing to match → never claimable.
        o = _order(customer_id=None, phone_digits="")
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"},
                         principal=_customer(phone_digits="600001234"), order=o)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data.get("code"), "phone_mismatch")
        o.save.assert_not_called()

    def test_already_claimed_by_other_returns_409(self):
        o = _order(customer_id=2, phone_digits="600001234")  # linked to a different customer
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"},
                         principal=_customer(pk=1, phone_digits="600001234"), order=o)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "already_claimed")
        o.save.assert_not_called()

    def test_already_mine_is_idempotent(self):
        o = _order(customer_id=1, phone_digits="600001234")  # already linked to caller
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"},
                         principal=_customer(pk=1, phone_digits="600001234"), order=o)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("already"))
        o.save.assert_not_called()  # nothing to write

    def test_claims_unlinked_matching_order(self):
        c = _customer(pk=1, phone_digits="600001234")
        o = _order(customer_id=None, phone_digits="600001234")
        resp = self._run({"restaurant": "demo", "order_number": "ORD-1"}, principal=c, order=o)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("claimed"))
        # The order was linked to the caller and persisted (which fires the mirror signal).
        self.assertIs(o.customer, c)
        o.save.assert_called_once_with(update_fields=["customer", "updated_at"])

    def test_accepts_tenant_slug_alias(self):
        # The body may use `tenant_slug` instead of `restaurant`.
        c = _customer(pk=1, phone_digits="600001234")
        o = _order(customer_id=None, phone_digits="600001234")
        resp = self._run({"tenant_slug": "demo", "order_number": "ORD-1"}, principal=c, order=o)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get("claimed"))

    # ── Contract guard ────────────────────────────────────────────────────────

    def test_auth_and_throttle_contract(self):
        self.assertIn(CustomerSessionAuthentication, CustomerClaimOrderView.authentication_classes)
        self.assertIn(IsCustomer, CustomerClaimOrderView.permission_classes)
        self.assertIn(CustomerOrderClaimThrottle, CustomerClaimOrderView.throttle_classes)
