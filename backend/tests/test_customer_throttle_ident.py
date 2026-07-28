"""RISK IDENTITY-1: the per-customer throttles key on the Customer PRINCIPAL.

`_CustomerThrottle` (and `WalletTransferThrottle`) used to derive their rate-limit
bucket from a raw `request.session["customer_id"]` read — a latent inconsistency once
IDENTITY-1 moved the customer onto `request.user`. They now go through
`_customer_throttle_ident`, which prefers the Customer principal and only falls back to
the raw session (for the un-converted ride views) then the client IP.

Behaviour is preserved byte-for-byte: `CustomerSessionAuthentication` hydrates the
Customer from `session["customer_id"]`, so the principal's pk IS that id — `c{pk}` and
the old `c{cid}` are the same bucket.

Mock-based (SimpleTestCase, no DB): the Customer principal is instantiated in memory
(never saved) and requests are lightweight namespaces.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from accounts.models import Customer
from accounts.throttles import (
    DeliveryTrackingThrottle,
    WalletTransferThrottle,
    _customer_throttle_ident,
)


def _req(user=None, session=None, ip="203.0.113.7"):
    return SimpleNamespace(
        user=user,
        session=session if session is not None else {},
        META={"REMOTE_ADDR": ip},
    )


class CustomerThrottleIdentTests(SimpleTestCase):
    """The ident helper: principal-first, session fallback, then None (→ IP)."""

    def test_prefers_the_customer_principal(self):
        # A signed-in Customer principal (converted view) → keyed on its pk; no session read.
        self.assertEqual(_customer_throttle_ident(_req(user=Customer(id=42))), "c42")

    def test_principal_and_old_session_key_the_same_bucket(self):
        # Behaviour preservation: the principal path and the old session path produce the
        # SAME bucket for the same customer (pk == session customer_id).
        principal = _customer_throttle_ident(_req(user=Customer(id=42)))
        session_only = _customer_throttle_ident(
            _req(user=AnonymousUser(), session={"customer_id": 42})
        )
        self.assertEqual(principal, session_only)
        self.assertEqual(principal, "c42")

    def test_falls_back_to_session_for_unconverted_ride_views(self):
        # Ride views don't mount CustomerSessionAuthentication → request.user is anonymous;
        # the raw session read still keys the driver/customer bucket (unchanged behaviour).
        self.assertEqual(
            _customer_throttle_ident(_req(user=AnonymousUser(), session={"customer_id": 99})),
            "c99",
        )

    def test_none_when_neither_principal_nor_session(self):
        self.assertIsNone(_customer_throttle_ident(_req(user=AnonymousUser(), session={})))

    def test_never_keys_on_a_staff_user(self):
        # A staff User is not a Customer principal → no c-bucket (falls through to session/IP),
        # so a staff cookie can never share or hijack a customer's throttle bucket.
        staff = SimpleNamespace(is_authenticated=True)  # __class__.__name__ != "Customer"
        self.assertIsNone(_customer_throttle_ident(_req(user=staff, session={})))

    def test_tolerates_a_request_without_a_session(self):
        no_session = SimpleNamespace(user=AnonymousUser())  # no `.session` attribute at all
        self.assertIsNone(_customer_throttle_ident(no_session))


class CustomerThrottleCacheKeyTests(SimpleTestCase):
    """The concrete throttles build `throttle_<scope>_<ident>` from that helper."""

    def test_customer_throttle_uses_the_principal_bucket(self):
        key = DeliveryTrackingThrottle().get_cache_key(_req(user=Customer(id=42)), view=None)
        self.assertEqual(key, "throttle_delivery_tracking_c42")

    def test_customer_throttle_falls_back_to_ip(self):
        t = DeliveryTrackingThrottle()
        t.get_ident = MagicMock(return_value="203.0.113.7")
        key = t.get_cache_key(_req(user=AnonymousUser(), session={}), view=None)
        self.assertEqual(key, "throttle_delivery_tracking_203.0.113.7")

    def test_wallet_transfer_throttle_uses_the_principal_bucket(self):
        key = WalletTransferThrottle().get_cache_key(_req(user=Customer(id=8)), view=None)
        self.assertEqual(key, "throttle_wallet_transfer_c8")
