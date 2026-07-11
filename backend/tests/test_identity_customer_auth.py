"""RISK IDENTITY-1: customer-principal auth keystone.

CustomerSessionAuthentication hydrates the signed-in Customer (session["customer_id"]) onto
request.user; IsCustomer / IsOrderOwner replace the hand-rolled session-PK + int==int checks
that customer endpoints each re-implemented (the order-status IDOR class).

Mock-based (SimpleTestCase, no DB): Customer/User are instantiated in memory (never saved),
the auth class's Customer lookup is patched, and requests are lightweight namespaces — so the
identity + ownership decision logic runs without a database.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from accounts.authentication import CustomerSessionAuthentication
from accounts.models import Customer, User
from accounts.permissions import IsCustomer, IsOrderOwner


def _req(session=None, user=None):
    return SimpleNamespace(session=session if session is not None else {}, user=user)


class CustomerPrincipalTests(SimpleTestCase):
    """The Customer model is usable AS request.user (mirrors User.is_authenticated)."""

    def test_customer_is_authenticated_principal(self):
        c = Customer(id=7)
        self.assertTrue(c.is_authenticated)
        self.assertFalse(c.is_anonymous)


class CustomerSessionAuthenticationTests(SimpleTestCase):
    def test_valid_session_returns_customer_principal(self):
        sentinel = Customer(id=7)
        with patch("accounts.models.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = sentinel
            result = CustomerSessionAuthentication().authenticate(_req(session={"customer_id": 7}))
        self.assertEqual(result, (sentinel, None))

    def test_no_customer_id_returns_none(self):
        # Anonymous (no customer session) → None, so DRF leaves AnonymousUser and gates fail closed.
        self.assertIsNone(CustomerSessionAuthentication().authenticate(_req(session={})))

    def test_stale_customer_id_returns_none(self):
        # Session PK whose Customer row was erased → unauthenticated (not a 500), side-effect-free.
        with patch("accounts.models.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = None
            result = CustomerSessionAuthentication().authenticate(_req(session={"customer_id": 999}))
        self.assertIsNone(result)

    def test_authenticate_header_present_so_denials_are_401(self):
        # Non-None header → DRF renders permission denials as 401 (matching the old
        # hand-rolled "Not authenticated" responses) rather than 403.
        self.assertIsNotNone(CustomerSessionAuthentication().authenticate_header(_req()))


class IsCustomerTests(SimpleTestCase):
    def test_customer_principal_allowed(self):
        self.assertTrue(IsCustomer().has_permission(_req(user=Customer(id=7)), None))

    def test_anonymous_rejected(self):
        self.assertFalse(IsCustomer().has_permission(_req(user=AnonymousUser()), None))

    def test_staff_user_rejected(self):
        # A staff User is authenticated but NOT a Customer — a staff cookie must not reach a
        # customer-only endpoint (the two identity systems stay disjoint).
        staff = User(id=1, is_staff=True)
        self.assertTrue(staff.is_authenticated)  # sanity: it IS an authenticated principal
        self.assertFalse(IsCustomer().has_permission(_req(user=staff), None))


class IsOrderOwnerTests(SimpleTestCase):
    def _order(self, customer_id):
        return SimpleNamespace(customer_id=customer_id)

    def test_owner_allowed(self):
        req = _req(user=Customer(id=7))
        self.assertTrue(IsOrderOwner().has_object_permission(req, None, self._order(7)))

    def test_non_owner_rejected(self):
        req = _req(user=Customer(id=7))
        self.assertFalse(IsOrderOwner().has_object_permission(req, None, self._order(8)))

    def test_string_ids_compared_numerically(self):
        # customer_id can arrive as a str (session/JSON) — compare as ints, not identity.
        req = _req(user=Customer(id=7))
        self.assertTrue(IsOrderOwner().has_object_permission(req, None, self._order("7")))

    def test_anonymous_rejected(self):
        req = _req(user=AnonymousUser())
        self.assertFalse(IsOrderOwner().has_object_permission(req, None, self._order(7)))

    def test_staff_user_rejected(self):
        # A staff principal owns no customer order — fails closed.
        req = _req(user=User(id=7, is_staff=True))
        self.assertFalse(IsOrderOwner().has_object_permission(req, None, self._order(7)))

    def test_order_without_customer_rejected(self):
        req = _req(user=Customer(id=7))
        self.assertFalse(IsOrderOwner().has_object_permission(req, None, self._order(None)))

    def test_unparseable_id_rejected(self):
        req = _req(user=Customer(id=7))
        self.assertFalse(IsOrderOwner().has_object_permission(req, None, self._order("not-a-number")))

    def test_has_permission_gates_on_customer_principal(self):
        self.assertTrue(IsOrderOwner().has_permission(_req(user=Customer(id=7)), None))
        self.assertFalse(IsOrderOwner().has_permission(_req(user=AnonymousUser()), None))
