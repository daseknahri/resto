"""HSWEEP: ride/package dispatch + rider push helpers must write a NotificationLog.

Bug: ``notify_car_drivers_new_ride_sync`` and ``notify_rider_sync`` (accounts/push.py)
sent web pushes but — unlike every sibling helper in the file — recorded NO
NotificationLog row, so a failed send was fully silent (no delivery observability).

Fix: each helper now calls ``record_notification`` at the end (wrapped in try/except so
a logging failure never breaks the push). These tests assert the event + recipient.

Unit-level (SimpleTestCase + mocks — no DB): we mock the public-schema managers and the
low-level ``_send_one`` delivery, then assert the logging call.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from accounts.push import notify_car_drivers_new_ride_sync, notify_rider_sync


def _noop_ctx():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _sub(customer_id=1, sub_id=10):
    s = MagicMock()
    s.id = sub_id
    s.customer_id = customer_id
    s.endpoint = "https://push.example/endpoint"
    s.p256dh = "p256dh-key"
    s.auth = "auth-key"
    return s


class NotifyCarDriversNewRideLoggingTests(SimpleTestCase):
    """A trip offer to drivers must record one push NotificationLog (ride vs package)."""

    def _run(self, *, is_package):
        with (
            patch("django_tenants.utils.schema_context", return_value=_noop_ctx()),
            patch("tenancy.delivery_pricing.valid_coord", return_value=False),
            patch("menu.push._send_one", return_value="ok"),
            patch("accounts.models.RideRequest") as ride_m,
            patch("accounts.models.Customer") as cust_m,
            patch("accounts.models.CustomerPushSubscription") as sub_m,
            patch("accounts.notifications.record_notification") as rec_m,
        ):
            ride = MagicMock()
            ride.status = ride_m.Status.SEARCHING
            ride.kind = ride_m.Kind.PACKAGE if is_package else "ride"
            ride.pickup_lat = None
            ride.pickup_lng = None
            ride_m.objects.get.return_value = ride

            candidate = MagicMock()
            candidate.id = 1
            # First filter → candidate list; second filter → (id, locale) values_list.
            cust_m.objects.filter.side_effect = [
                [candidate],
                MagicMock(**{"values_list.return_value": [(1, "en")]}),
            ]
            sub_m.objects.filter.return_value = [_sub(customer_id=1)]

            sent = notify_car_drivers_new_ride_sync(42)

        self.assertEqual(sent, 1)
        rec_m.assert_called_once()
        return rec_m.call_args.kwargs

    def test_ride_offer_is_logged(self):
        kw = self._run(is_package=False)
        self.assertEqual(kw["channel"], "push")
        self.assertEqual(kw["event"], "ride.offer")
        self.assertEqual(kw["status"], "sent")
        self.assertEqual(kw["recipient"], "1/1 drivers")

    def test_package_offer_is_logged(self):
        kw = self._run(is_package=True)
        self.assertEqual(kw["event"], "package.offer")
        self.assertEqual(kw["status"], "sent")
        self.assertEqual(kw["recipient"], "1/1 drivers")


class NotifyRiderLoggingTests(SimpleTestCase):
    """A ride-status push to the rider must record one push NotificationLog."""

    @patch("accounts.notifications.record_notification")
    @patch("accounts.notifications.create_customer_notification")
    @patch("menu.push._send_one", return_value="ok")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_rider_push_is_logged(self, sc_m, cust_m, sub_m, send_m, mirror_m, rec_m):
        sc_m.return_value = _noop_ctx()
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub_m.objects.filter.return_value = [_sub(customer_id=11)]

        sent = notify_rider_sync(11, "accepted")

        self.assertEqual(sent, 1)
        rec_m.assert_called_once()
        kw = rec_m.call_args.kwargs
        self.assertEqual(kw["channel"], "push")
        self.assertEqual(kw["event"], "ride.accepted")
        self.assertEqual(kw["status"], "sent")
        self.assertEqual(kw["recipient"], "rider:11")
