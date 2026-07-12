"""Tests for the in-app notification center / inbox (Wave 2, NOTIFICATION-INBOX).

Covers:
  * CustomerNotification model basics (is_read property, ordering meta).
  * create_customer_notification() helper — writes a row, is best-effort/no-op on bad input.
  * CustomerNotificationsView — auth gate, list shape, unread_count, count_only, paging.
  * CustomerNotificationsMarkReadView — auth gate, mark-all vs mark-some, customer scoping.

DB-free: the views/helper are exercised with mocked querysets (mirrors the existing
test_customer_charge_requests.py style) so they run without Postgres.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer, CustomerNotification
from accounts.views import (
    CustomerNotificationsView,
    CustomerNotificationsMarkReadView,
    _serialize_notification,
)


class CustomerNotificationModelTests(SimpleTestCase):
    def test_is_read_property(self):
        n = CustomerNotification(customer_id=1, title="hi")
        self.assertFalse(n.is_read)
        from django.utils import timezone
        n.read_at = timezone.now()
        self.assertTrue(n.is_read)

    def test_meta_orders_newest_first(self):
        self.assertEqual(CustomerNotification._meta.ordering, ("-created_at",))

    def test_vertical_choices_include_cross_vertical_set(self):
        values = {v for v, _ in CustomerNotification.Vertical.choices}
        self.assertTrue({"food", "ride", "courier", "wallet", "general"} <= values)

    def test_serialize_shape(self):
        from django.utils import timezone
        now = timezone.now()
        n = MagicMock(
            id=7, type="delivery.delivered", vertical="food", title="Delivered",
            body="Your order arrived", url="/orders/ORD-1", read_at=None, created_at=now,
        )
        out = _serialize_notification(n)
        self.assertEqual(out["id"], 7)
        self.assertEqual(out["vertical"], "food")
        self.assertEqual(out["url"], "/orders/ORD-1")
        self.assertFalse(out["is_read"])
        self.assertEqual(out["created_at"], now.isoformat())


class CreateCustomerNotificationHelperTests(SimpleTestCase):
    def test_writes_row_in_public_schema(self):
        from accounts.notifications import create_customer_notification
        with patch("accounts.models.CustomerNotification.objects") as mock_objs, \
             patch("django_tenants.utils.schema_context"):
            create_customer_notification(
                customer_id=42, title="Delivered", body="b", url="/orders/X",
                type="delivery.delivered", vertical="food",
            )
        self.assertTrue(mock_objs.create.called)
        kwargs = mock_objs.create.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], 42)
        self.assertEqual(kwargs["title"], "Delivered")
        self.assertEqual(kwargs["vertical"], "food")

    def test_noop_without_customer_or_title(self):
        from accounts.notifications import create_customer_notification
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            create_customer_notification(customer_id=0, title="x")
            create_customer_notification(customer_id=5, title="")
        self.assertFalse(mock_objs.create.called)

    def test_truncates_overlong_fields(self):
        from accounts.notifications import create_customer_notification
        with patch("accounts.models.CustomerNotification.objects") as mock_objs, \
             patch("django_tenants.utils.schema_context"):
            create_customer_notification(customer_id=1, title="t" * 500, body="b" * 999, url="u" * 999)
        kwargs = mock_objs.create.call_args.kwargs
        self.assertEqual(len(kwargs["title"]), 160)
        self.assertEqual(len(kwargs["body"]), 400)
        self.assertEqual(len(kwargs["url"]), 300)

    def test_swallows_exceptions(self):
        from accounts.notifications import create_customer_notification
        with patch("accounts.models.CustomerNotification.objects") as mock_objs, \
             patch("django_tenants.utils.schema_context"):
            mock_objs.create.side_effect = RuntimeError("boom")
            # Must not raise.
            create_customer_notification(customer_id=1, title="t")


def _fake_notification(nid, *, read=False, title="T", url="/u"):
    from django.utils import timezone
    n = MagicMock()
    n.id = nid
    n.type = "delivery.delivered"
    n.vertical = "food"
    n.title = title
    n.body = "body"
    n.url = url
    n.read_at = timezone.now() if read else None
    n.created_at = timezone.now()
    return n


class CustomerNotificationsListTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerNotificationsView.as_view()

    def _get(self, customer_id=5, query=""):
        req = self.factory.get(f"/api/customer/notifications/{query}")
        req.session = {"customer_id": customer_id} if customer_id else {}
        if customer_id:
            force_authenticate(req, user=Customer(id=customer_id))
        return self.view(req)

    def test_unauthenticated_401(self):
        self.assertEqual(self._get(customer_id=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_rows_and_unread_count(self):
        rows = [_fake_notification(3), _fake_notification(2, read=True)]
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            mock_objs.filter.return_value.count.return_value = 4
            ordered = mock_objs.filter.return_value.order_by.return_value
            ordered.__getitem__.return_value = rows
            resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["unread_count"], 4)
        self.assertEqual(len(resp.data["notifications"]), 2)
        self.assertEqual(resp.data["notifications"][0]["id"], 3)
        self.assertFalse(resp.data["has_more"])

    def test_count_only_skips_list(self):
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            mock_objs.filter.return_value.count.return_value = 9
            resp = self._get(query="?count_only=1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"unread_count": 9})
        # The list query (order_by) is never built for a count-only poll.
        self.assertFalse(mock_objs.filter.return_value.order_by.called)

    def test_has_more_paging_signals_next_before(self):
        # PAGE_SIZE+1 rows returned -> has_more True, list trimmed to PAGE_SIZE.
        page = CustomerNotificationsView.PAGE_SIZE
        rows = [_fake_notification(i) for i in range(page + 1, 0, -1)]  # ids descending
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            mock_objs.filter.return_value.count.return_value = 0
            ordered = mock_objs.filter.return_value.order_by.return_value
            ordered.__getitem__.return_value = rows
            resp = self._get()
        self.assertTrue(resp.data["has_more"])
        self.assertEqual(len(resp.data["notifications"]), page)
        self.assertIsNotNone(resp.data["next_before"])


class CustomerNotificationsMarkReadTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerNotificationsMarkReadView.as_view()

    def _post(self, body=None, customer_id=5):
        req = self.factory.post("/api/customer/notifications/mark-read/", body or {}, format="json")
        req.session = {"customer_id": customer_id} if customer_id else {}
        if customer_id:
            force_authenticate(req, user=Customer(id=customer_id))
        return self.view(req)

    def test_unauthenticated_401(self):
        self.assertEqual(self._post(customer_id=None).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_all_updates_unread(self):
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            unread_qs = MagicMock()
            unread_qs.update.return_value = 3
            mock_objs.filter.side_effect = [unread_qs, MagicMock(count=MagicMock(return_value=0))]
            resp = self._post(body={})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["marked"], 3)
        self.assertEqual(resp.data["unread_count"], 0)
        # mark-all -> the queryset is NOT further filtered by ids.
        self.assertFalse(unread_qs.filter.called)

    def test_mark_some_filters_by_ids(self):
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            unread_qs = MagicMock()
            scoped = MagicMock()
            scoped.update.return_value = 1
            unread_qs.filter.return_value = scoped
            mock_objs.filter.side_effect = [unread_qs, MagicMock(count=MagicMock(return_value=2))]
            resp = self._post(body={"ids": [7]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["marked"], 1)
        self.assertEqual(resp.data["unread_count"], 2)
        self.assertTrue(unread_qs.filter.called)

    def test_invalid_ids_400(self):
        with patch("accounts.models.CustomerNotification.objects") as mock_objs:
            mock_objs.filter.return_value = MagicMock()
            resp = self._post(body={"ids": ["not-an-int"]})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


def _sub(sid=1):
    s = MagicMock()
    s.id = sid
    s.endpoint = f"https://push.example/{sid}"
    s.p256dh = "p256dh"
    s.auth = "auth"
    return s


class PushCallSitesMirrorToInboxTests(SimpleTestCase):
    """Every key customer push call-site ALSO persists a mirrored inbox row — even when
    the customer has NO push subscriptions (the whole point of the durable inbox)."""

    @patch("accounts.notifications.create_customer_notification")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_review_request_mirrors_even_without_subs(self, cust_m, sub_m, _sc, mirror):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(
            locale="en", notify_review_prompts=True
        )
        sub_m.objects.filter.return_value = []  # no subscriptions at all
        from accounts.push import send_review_request_sync
        send_review_request_sync(42, "Bella Pizza", "ORD-9")
        self.assertTrue(mirror.called)
        kwargs = mirror.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], 42)
        self.assertEqual(kwargs["url"], "/orders/ORD-9")
        self.assertEqual(kwargs["type"], "review_prompt")
        self.assertEqual(kwargs["vertical"], "food")

    @patch("accounts.notifications.create_customer_notification")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_charge_request_mirrors_wallet_vertical(self, cust_m, sub_m, _sc, mirror):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub_m.objects.filter.return_value = []
        from accounts.push import _send_charge_request_sync
        _send_charge_request_sync(7, "Cafe Noir", "120.00")
        self.assertTrue(mirror.called)
        kwargs = mirror.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], 7)
        self.assertEqual(kwargs["url"], "/account")
        self.assertEqual(kwargs["vertical"], "wallet")
        self.assertEqual(kwargs["type"], "charge_request")

    @patch("accounts.notifications.create_customer_notification")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_ride_accepted_mirrors_ride_vertical(self, cust_m, sub_m, _sc, mirror):
        cust_m.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub_m.objects.filter.return_value = []
        from accounts.push import notify_rider_sync
        notify_rider_sync(11, "accepted")
        self.assertTrue(mirror.called)
        kwargs = mirror.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], 11)
        self.assertEqual(kwargs["url"], "/rides")
        self.assertEqual(kwargs["vertical"], "ride")
        self.assertEqual(kwargs["type"], "ride.accepted")
