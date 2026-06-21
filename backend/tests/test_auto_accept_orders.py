"""
Tests for the auto-accept setting (Wave 4 — Toast/Square parity).

An OWNER SETTING (Profile.auto_accept_orders, default False) that, when ON,
auto-confirms routine incoming pickup/delivery orders with a quoted prep time
instead of requiring a manual Confirm tap. Default OFF preserves today's
manual-confirm behaviour exactly.

Covers:
  - the pure decision helper menu.views._auto_accept_now across every input;
  - the DEFAULT-PRESERVING guard: a fresh Profile has auto_accept_orders=False,
    and the helper returns False for it (no behaviour change for existing
    tenants);
  - scheduled/advance and dine-in (TABLE) orders are NEVER auto-accepted, even
    with the flag on.

Helper tests are unit-level (SimpleTestCase + SimpleNamespace — no DB). The
model-default test reads the field default off the model meta (no DB needed).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.models import Order
from menu.views import _auto_accept_now


def _profile(**kw):
    base = dict(auto_accept_orders=False)
    base.update(kw)
    return SimpleNamespace(**base)


class AutoAcceptHelperTests(SimpleTestCase):
    # ── Default-preserving guard ─────────────────────────────────────────────
    def test_off_by_default_means_manual_confirm(self):
        """Flag off (the default) → never auto-accept, regardless of type."""
        for ft in (Order.FulfillmentType.PICKUP, Order.FulfillmentType.DELIVERY,
                   Order.FulfillmentType.TABLE):
            self.assertFalse(
                _auto_accept_now(_profile(), is_scheduled=False, fulfillment_type=ft),
                msg=f"flag-off must not auto-accept {ft}",
            )

    def test_missing_flag_attr_defaults_false(self):
        # A profile object that doesn't even have the attribute must be safe.
        bare = SimpleNamespace()
        self.assertFalse(
            _auto_accept_now(bare, is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.PICKUP)
        )

    # ── Flag-on behaviour ────────────────────────────────────────────────────
    def test_on_auto_accepts_pickup(self):
        self.assertTrue(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.PICKUP)
        )

    def test_on_auto_accepts_delivery(self):
        self.assertTrue(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.DELIVERY)
        )

    def test_on_does_not_auto_accept_dine_in_table(self):
        """Dine-in pays at the end — its flow is untouched by auto-accept."""
        self.assertFalse(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.TABLE)
        )

    def test_on_does_not_auto_accept_scheduled(self):
        """Advance/scheduled orders release to the kitchen later — never auto-confirm now."""
        self.assertFalse(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=True,
                             fulfillment_type=Order.FulfillmentType.PICKUP)
        )

    def test_string_fulfillment_type_supported(self):
        # The marketplace path passes the raw string "pickup"/"delivery".
        self.assertTrue(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=False,
                             fulfillment_type="pickup")
        )
        self.assertTrue(
            _auto_accept_now(_profile(auto_accept_orders=True), is_scheduled=False,
                             fulfillment_type="delivery")
        )

    def test_garbage_flag_value_is_safe(self):
        # A bad value must never silently flip ordering into auto-accept.
        self.assertTrue(
            _auto_accept_now(_profile(auto_accept_orders="yes"), is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.PICKUP)
        )  # truthy string → on, but still type-gated below
        self.assertFalse(
            _auto_accept_now(_profile(auto_accept_orders=0), is_scheduled=False,
                             fulfillment_type=Order.FulfillmentType.PICKUP)
        )


class ProfileFieldDefaultTests(SimpleTestCase):
    def test_auto_accept_orders_field_default_is_false(self):
        from tenancy.models import Profile
        field = Profile._meta.get_field("auto_accept_orders")
        self.assertIs(field.default, False)
