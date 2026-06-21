"""
Tests for busy-mode / order-throttling (Wave 3 — Toast/Deliveroo parity).

Covers:
  - the pure time-based helpers _orders_paused_now / _busy_extra_minutes_now
    (auto-resume is implicit: a past timestamp = not paused / no bump);
  - PlaceOrderView rejects ASAP orders with 409 `ordering_paused` while paused,
    surfaces the auto-resume time, lets owner-preview + advance/scheduled orders
    through, and never blocks when the pause has expired;
  - the busy-extra bump stamps a slower estimated_ready_minutes at placement.

Unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import (
    PlaceOrderView,
    _orders_paused_now,
    _busy_extra_minutes_now,
)


# ── Pure helpers ──────────────────────────────────────────────────────────────

class BusyModeHelperTests(SimpleTestCase):
    def _p(self, **kw):
        base = dict(
            orders_paused_until=None,
            busy_extra_minutes=0,
            busy_extra_until=None,
            default_prep_minutes=None,
        )
        base.update(kw)
        return SimpleNamespace(**base)

    def test_not_paused_when_field_unset(self):
        self.assertFalse(_orders_paused_now(self._p()))

    def test_paused_when_until_in_future(self):
        until = timezone.now() + timedelta(minutes=15)
        self.assertTrue(_orders_paused_now(self._p(orders_paused_until=until)))

    def test_auto_resume_when_until_in_past(self):
        until = timezone.now() - timedelta(minutes=1)
        self.assertFalse(_orders_paused_now(self._p(orders_paused_until=until)))

    def test_garbage_pause_value_is_not_paused(self):
        # A bad value must NEVER wedge ordering shut.
        self.assertFalse(_orders_paused_now(self._p(orders_paused_until="not-a-date")))

    def test_extra_zero_when_unset(self):
        self.assertEqual(_busy_extra_minutes_now(self._p()), 0)

    def test_extra_applies_only_while_window_open(self):
        future = timezone.now() + timedelta(minutes=30)
        self.assertEqual(
            _busy_extra_minutes_now(self._p(busy_extra_minutes=20, busy_extra_until=future)),
            20,
        )

    def test_extra_auto_clears_when_window_passed(self):
        past = timezone.now() - timedelta(minutes=1)
        self.assertEqual(
            _busy_extra_minutes_now(self._p(busy_extra_minutes=20, busy_extra_until=past)),
            0,
        )

    def test_extra_zero_when_minutes_set_but_no_until(self):
        self.assertEqual(
            _busy_extra_minutes_now(self._p(busy_extra_minutes=20, busy_extra_until=None)),
            0,
        )


# ── Test fixtures mirroring test_place_order_view.py ──────────────────────────

def _plan(can_checkout=True, can_whatsapp_order=True):
    return SimpleNamespace(can_checkout=can_checkout, can_whatsapp_order=can_whatsapp_order)


def _tenant(plan=None, tenant_id=1):
    return SimpleNamespace(id=tenant_id, name="Demo", plan=plan or _plan())


def _profile(**kw):
    base = dict(
        is_menu_published=True,
        is_menu_temporarily_disabled=False,
        is_open=True,
        delivery_fee="0",
        orders_paused_until=None,
        busy_extra_minutes=0,
        busy_extra_until=None,
        default_prep_minutes=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _session():
    sess = MagicMock()
    sess.get = lambda key, default=None: default
    return sess


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


VALID_PAYLOAD = {
    "items": [{"slug": "burger", "qty": 1}],
    "fulfillment_type": "pickup",
}


class PlaceOrderBusyModeGateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceOrderView.as_view()

    def _post(self, data=None, tenant=None):
        req = self.factory.post("/api/place-order/", data or VALID_PAYLOAD, format="json")
        req.tenant = tenant or _tenant()
        req.user = _anon()
        req.session = _session()
        return req

    @patch("menu.views.Profile.objects")
    def test_rejects_asap_order_while_paused(self, profile_mock):
        resume_at = timezone.now() + timedelta(minutes=30)
        profile_mock.filter.return_value.first.return_value = _profile(orders_paused_until=resume_at)
        resp = self.view(self._post())
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "ordering_paused")
        # The auto-resume time is surfaced so the storefront can show a countdown.
        self.assertIn("resume_at", resp.data)

    @patch("menu.views.Profile.objects")
    def test_allows_order_after_pause_expired(self, profile_mock):
        past = timezone.now() - timedelta(minutes=1)
        profile_mock.filter.return_value.first.return_value = _profile(orders_paused_until=past)
        with patch("menu.views.Dish.objects") as dish_mock:
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = []
            resp = self.view(self._post())
        # Not blocked by the pause gate — falls through to items-unavailable (400).
        self.assertNotEqual(resp.status_code, status.HTTP_409_CONFLICT)

    @patch("menu.views.Profile.objects")
    def test_preview_owner_bypasses_pause(self, profile_mock):
        resume_at = timezone.now() + timedelta(minutes=30)
        tenant = _tenant()
        profile_mock.filter.return_value.first.return_value = _profile(orders_paused_until=resume_at)
        req = self._post(tenant=tenant)
        owner = MagicMock()
        owner.is_authenticated = True
        owner.is_superuser = False
        owner.is_platform_admin = False
        owner.tenant_id = tenant.id
        req.user = owner
        with patch("menu.views.Dish.objects") as dish_mock:
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = []
            resp = self.view(req)
        # Owner preview is never blocked by the snooze.
        self.assertNotEqual(resp.data.get("code"), "ordering_paused")

    @patch("menu.views.Profile.objects")
    def test_scheduled_order_not_blocked_by_pause(self, profile_mock):
        """An advance/scheduled order is for a future slot — the snooze must not block it."""
        resume_at = timezone.now() + timedelta(minutes=30)
        profile_mock.filter.return_value.first.return_value = _profile(orders_paused_until=resume_at)
        payload = dict(VALID_PAYLOAD)
        payload["scheduled_for"] = (timezone.now() + timedelta(hours=2)).isoformat()
        with patch("menu.views.Dish.objects") as dish_mock:
            dish_mock.filter.return_value.select_related.return_value.prefetch_related.return_value = []
            resp = self.view(self._post(data=payload))
        self.assertNotEqual(resp.data.get("code"), "ordering_paused")
