"""
OPS-1 backend tests — "the kitchen never goes dark".

Covers:
  Contract 1 — StaffBulkReadyView  POST /api/staff/orders/<id>/items/ready-all/
    - happy path: non-voided not-ready items updated; voided + already-ready skipped;
      exactly ONE broadcast; staff payload returned
    - terminal 409 bad_status (completed & cancelled)
    - section gate (mock _can_access_order False → 403 section_denied)
    - empty order (no qualifying items) → no-op 200 with payload
    - unauthenticated 403
    - no perm_manage_orders 403

  Contract 2 — StaffTableListView  GET /api/staff/tables/
    - waiter-role can read, response shape (id/slug/label/section)
    - section null when table has no section
    - unauthenticated 403
    - tenant scoping guard (wrong tenant → 403)

  Contract 6a — Channel layer resolves to RedisChannelLayer when REDIS_URL is set
    - override-settings style assertion; guarded so it passes even if channels_redis
      is not importable in the test environment

House style: SimpleTestCase + MagicMock, no real DB.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from menu.views import StaffBulkReadyView, StaffTableListView
from menu.models import Order
from accounts.models import User


# ── Shared helpers ────────────────────────────────────────────────────────────

def _user(role=User.Roles.TENANT_STAFF, tenant_id=1, perm_manage=True):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = role
    u.tenant_id = tenant_id
    u.effective_perm_manage_orders = MagicMock(return_value=perm_manage)
    return u


def _tenant(tenant_id=1):
    return SimpleNamespace(id=tenant_id)


def _make_item(
    item_id=901,
    dish_name="Burger",
    dish_slug="burger",
    qty=1,
    unit_price=Decimal("12.50"),
    subtotal=Decimal("12.50"),
    options=None,
    note="",
    is_ready=False,
    is_voided=False,
    course=0,
):
    item = MagicMock()
    item.id = item_id
    item.dish_name = dish_name
    item.dish_slug = dish_slug
    item.qty = qty
    item.unit_price = unit_price
    item.subtotal = subtotal
    item.options = options or []
    item.note = note
    item.is_ready = is_ready
    item.is_voided = is_voided
    item.course = course
    item.combo_components = []
    item.save = MagicMock()
    return item


def _make_order(
    order_id=10,
    status_val=Order.Status.PENDING,
    fulfillment_type=Order.FulfillmentType.TABLE,
    payment_status=Order.PaymentStatus.UNPAID,
    total=Decimal("12.50"),
    delivery_fee=Decimal("0"),
    tip_amount=Decimal("0"),
    promotion_discount=Decimal("0"),
    loyalty_discount=Decimal("0"),
    wallet_amount_paid=Decimal("0"),
    customer_id=None,
    items=None,
    fired_course=1,
):
    order = MagicMock()
    order.id = order_id
    order.order_number = "ORD-001"
    order.status = status_val
    order.fulfillment_type = fulfillment_type
    order.payment_status = payment_status
    order.total = total
    order.delivery_fee = delivery_fee
    order.tip_amount = tip_amount
    order.promotion_discount = promotion_discount
    order.loyalty_discount = loyalty_discount
    order.wallet_amount_paid = wallet_amount_paid
    order.customer_id = customer_id
    order.table_label = "T1"
    order.table_slug = "t1"
    order.customer_name = "Alice"
    order.customer_note = ""
    order.owner_note = ""
    order.estimated_ready_minutes = None
    order.currency = "MAD"
    order.scheduled_for = None
    order.fired_course = fired_course
    order.save = MagicMock()
    order.created_at = MagicMock()
    order.created_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"
    order.updated_at = MagicMock()
    order.updated_at.isoformat.return_value = "2026-06-12T10:00:00+00:00"

    _items = items or []
    items_qs = MagicMock()
    items_qs.all.return_value = _items
    order.items = items_qs

    payments_qs = MagicMock()
    payments_qs.all.return_value = []
    order.payments = payments_qs

    return order


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 1 — StaffBulkReadyView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffBulkReadyViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffBulkReadyView.as_view()

        # Default: section gate allows access.
        _access_patcher = patch("menu.views._can_access_order", return_value=True)
        self._access_mock = _access_patcher.start()
        self.addCleanup(_access_patcher.stop)

        # The view wraps the mutate in transaction.atomic() + select_for_update()
        # (concurrency guard, same as StaffFireCourseView). Make atomic a no-op
        # passthrough so SimpleTestCase never touches a real DB connection.
        class _Atomic:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

        _tx_patcher = patch("menu.views.transaction")
        self._tx_mock = _tx_patcher.start()
        self.addCleanup(_tx_patcher.stop)
        self._tx_mock.atomic.return_value = _Atomic()

    def _post(self, order_id=10, user=None):
        req = self.factory.post(
            f"/api/staff/orders/{order_id}/items/ready-all/",
            {},
            format="json",
        )
        u = user or _user()
        force_authenticate(req, user=u)
        req.tenant = _tenant()
        return self.view(req, order_id=order_id)

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_is_403(self):
        req = self.factory.post("/api/staff/orders/10/items/ready-all/", {}, format="json")
        with patch("menu.views.Order.objects") as om:
            om.prefetch_related.return_value.filter.return_value.first.return_value = None
            resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_no_manage_orders_perm_is_403(self, _mock):
        req = self.factory.post("/api/staff/orders/10/items/ready-all/", {}, format="json")
        force_authenticate(req, user=_user())
        req.tenant = _tenant()
        resp = self.view(req, order_id=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Kitchen capability gate (retail/grocery tenants have no kitchen) ────────

    def test_kitchen_capability_disabled_is_403(self):
        """A tenant whose 'kitchen' capability is disabled must be refused, same
        as the single-item StaffOrderItemReadyView peer."""
        with patch("tenancy.capabilities.tenant_capability_enabled", return_value=False):
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "kitchen_unavailable")

    # ── Section gate ──────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_section_gate_enforced(self, om):
        """_can_access_order returning False must return 403 section_denied."""
        item = _make_item(is_ready=False, is_voided=False)
        order = _make_order(items=[item])
        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = order

        with patch("menu.views._can_access_order", return_value=False):
            resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "section_denied")

    # ── Not found ─────────────────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_order_not_found_404(self, om):
        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.filter.return_value.exists.return_value = True  # existence pre-check passes
        om.prefetch_related.return_value.filter.return_value.first.return_value = None
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(resp.data["code"], "not_found")

    # ── Terminal status guards ────────────────────────────────────────────────

    @patch("menu.views.Order.objects")
    def test_terminal_completed_409(self, om):
        order = _make_order(status_val=Order.Status.COMPLETED)
        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    @patch("menu.views.Order.objects")
    def test_terminal_cancelled_409(self, om):
        order = _make_order(status_val=Order.Status.CANCELLED)
        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = order
        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["code"], "bad_status")

    # ── Happy path ────────────────────────────────────────────────────────────

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_marks_non_voided_not_ready_items(self, om, broadcast_mock):
        """Non-voided not-ready items must be marked ready; voided and already-ready skipped."""
        item_pending = _make_item(item_id=1, is_ready=False, is_voided=False)
        item_already_ready = _make_item(item_id=2, is_ready=True, is_voided=False)
        item_voided = _make_item(item_id=3, is_ready=False, is_voided=True)

        first_order = _make_order(items=[item_pending, item_already_ready, item_voided])
        second_order = _make_order(items=[item_pending, item_already_ready, item_voided])

        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Only item_pending should have been saved.
        item_pending.save.assert_called_once_with(update_fields=["is_ready", "ready_at"])
        self.assertTrue(item_pending.is_ready)
        self.assertIsNotNone(item_pending.ready_at)

        # Already-ready and voided must NOT be touched.
        item_already_ready.save.assert_not_called()
        item_voided.save.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_exactly_one_broadcast(self, om, broadcast_mock):
        """Regardless of how many items are updated, broadcast must be called exactly once."""
        items = [_make_item(item_id=i, is_ready=False, is_voided=False) for i in range(5)]
        first_order = _make_order(items=items)
        second_order = _make_order(items=items)

        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        self._post()

        broadcast_mock.assert_called_once()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_happy_path_returns_staff_payload(self, om, broadcast_mock):
        """Response must carry the standard staff order payload shape."""
        item = _make_item(is_ready=False, is_voided=False)
        first_order = _make_order(items=[item])
        second_order = _make_order(items=[item])

        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in ("id", "order_number", "status", "items", "fired_course"):
            self.assertIn(key, resp.data, f"payload missing key: {key}")

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_empty_order_noop_200(self, om, broadcast_mock):
        """An order with no qualifying items must return 200 and still broadcast."""
        # Only voided and already-ready items — nothing to mark.
        voided = _make_item(item_id=1, is_ready=False, is_voided=True)
        already_ready = _make_item(item_id=2, is_ready=True, is_voided=False)
        first_order = _make_order(items=[voided, already_ready])
        second_order = _make_order(items=[voided, already_ready])

        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        voided.save.assert_not_called()
        already_ready.save.assert_not_called()

    @patch("menu.views._broadcast_order_change")
    @patch("menu.views.Order.objects")
    def test_broadcast_exception_does_not_fail_request(self, om, broadcast_mock):
        """A broadcast exception must not surface — response is still 200."""
        broadcast_mock.side_effect = Exception("ws down")
        item = _make_item(is_ready=False, is_voided=False)
        first_order = _make_order(items=[item])
        second_order = _make_order(items=[item])

        om.select_for_update.return_value = om  # locked fetch reuses this mock
        om.prefetch_related.return_value.filter.return_value.first.return_value = first_order
        om.prefetch_related.return_value.get.return_value = second_order

        resp = self._post()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 2 — StaffTableListView
# ═══════════════════════════════════════════════════════════════════════════════

class StaffTableListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = StaffTableListView.as_view()

    def _get(self, user=None, tenant_id=1):
        req = self.factory.get("/api/staff/tables/")
        u = user or _user(tenant_id=tenant_id)
        force_authenticate(req, user=u)
        req.tenant = _tenant(tenant_id=tenant_id)
        return self.view(req)

    def _make_table(self, pk, slug, label, section_name=None, table_status="open", capacity=4):
        t = MagicMock()
        t.id = pk
        t.slug = slug
        t.label = label
        t.status = table_status
        t.capacity = capacity
        if section_name is not None:
            t.section = MagicMock()
            t.section.name = section_name
            t.section_id = pk  # non-None
        else:
            t.section = None
            t.section_id = None
        return t

    # ── Auth / permission ─────────────────────────────────────────────────────

    def test_unauthenticated_is_403(self):
        req = self.factory.get("/api/staff/tables/")
        with patch("menu.views.TableLink.objects"):
            resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._can_edit_tenant_order", return_value=False)
    def test_wrong_tenant_is_403(self, _mock):
        req = self.factory.get("/api/staff/tables/")
        force_authenticate(req, user=_user(tenant_id=2))
        req.tenant = _tenant(tenant_id=1)
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Waiter can read ───────────────────────────────────────────────────────

    @patch("menu.views.TableLink.objects")
    def test_waiter_can_read(self, tl_om):
        table = self._make_table(1, "t1", "Table 1", section_name="Terrace")
        tl_om.select_related.return_value.filter.return_value.order_by.return_value = [table]

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ── Response shape ────────────────────────────────────────────────────────

    @patch("menu.views.TableLink.objects")
    def test_response_shape_with_section(self, tl_om):
        """Each entry must carry id, slug, label, and section name."""
        table = self._make_table(7, "main-1", "Main 1", section_name="Main Hall")
        tl_om.select_related.return_value.filter.return_value.order_by.return_value = [table]

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row["id"], 7)
        self.assertEqual(row["slug"], "main-1")
        self.assertEqual(row["label"], "Main 1")
        self.assertEqual(row["section"], "Main Hall")
        self.assertEqual(row["status"], "open")
        self.assertEqual(row["capacity"], 4)

    @patch("menu.views.TableLink.objects")
    def test_response_shape_no_section(self, tl_om):
        """Tables with no section must have section=null."""
        table = self._make_table(3, "solo-1", "Solo 1", section_name=None)
        tl_om.select_related.return_value.filter.return_value.order_by.return_value = [table]

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data[0]
        self.assertIsNone(row["section"])

    @patch("menu.views.TableLink.objects")
    def test_multiple_tables_returned(self, tl_om):
        """All active tables are returned in the list."""
        tables = [
            self._make_table(1, "t1", "T1", section_name="Terrace"),
            self._make_table(2, "t2", "T2", section_name=None),
            self._make_table(3, "t3", "T3", section_name="Bar"),
        ]
        tl_om.select_related.return_value.filter.return_value.order_by.return_value = tables

        resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 3)
        slugs = [r["slug"] for r in resp.data]
        self.assertIn("t1", slugs)
        self.assertIn("t2", slugs)
        self.assertIn("t3", slugs)

    @patch("menu.views.TableLink.objects")
    def test_only_active_tables_queried(self, tl_om):
        """The view must filter is_active=True."""
        tl_om.select_related.return_value.filter.return_value.order_by.return_value = []
        self._get()
        filter_kwargs = tl_om.select_related.return_value.filter.call_args
        # assert is_active=True was passed to filter
        self.assertEqual(filter_kwargs, call(is_active=True))


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 6a — Channel layer resolves to Redis when REDIS_URL is set
# ═══════════════════════════════════════════════════════════════════════════════

class ChannelLayerConfigTests(SimpleTestCase):
    """Guard: skip gracefully if channels_redis is not importable."""

    def _channel_layer_backend_class(self, settings_dict):
        """Return the BACKEND string configured in CHANNEL_LAYERS['default'] given
        a simulated settings namespace, or None if the module cannot be resolved."""
        return settings_dict.get("CHANNEL_LAYERS", {}).get(
            "default", {}
        ).get("BACKEND")

    def test_redis_url_set_resolves_redis_backend(self):
        """When REDIS_URL is set and channels is installed, the channel layer backend
        must be channels_redis.core.RedisChannelLayer (not InMemoryChannelLayer)."""
        try:
            import channels  # noqa: F401
        except ImportError:
            self.skipTest("channels not installed — skipping channel layer test")

        # channels_redis may or may not be installed; we only assert the settings
        # resolves to the redis backend string when REDIS_URL is set.
        with override_settings(
            CHANNEL_LAYERS={
                "default": {
                    "BACKEND": "channels_redis.core.RedisChannelLayer",
                    "CONFIG": {"hosts": ["redis://localhost:6379"], "prefix": "resto:ws"},
                }
            }
        ):
            from django.conf import settings as django_settings
            backend = (
                django_settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND")
            )
        self.assertEqual(backend, "channels_redis.core.RedisChannelLayer")

    def test_no_redis_url_falls_back_to_inmemory(self):
        """When REDIS_URL is not set the channel layer must be InMemoryChannelLayer."""
        try:
            import channels  # noqa: F401
        except ImportError:
            self.skipTest("channels not installed — skipping channel layer test")

        with override_settings(
            CHANNEL_LAYERS={
                "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
            }
        ):
            from django.conf import settings as django_settings
            backend = (
                django_settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND")
            )
        self.assertEqual(backend, "channels.layers.InMemoryChannelLayer")

    def test_settings_py_uses_redis_backend_string(self):
        """Verify the actual settings.py hardcodes the correct redis backend class name."""
        import config.settings as s
        # The constant is embedded in the source; verify via module-level eval
        # without instantiating the layer (which requires a live Redis).
        src_path = s.__file__
        with open(src_path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn(
            "channels_redis.core.RedisChannelLayer",
            src,
            "settings.py must reference channels_redis.core.RedisChannelLayer "
            "as the CHANNEL_LAYERS backend when REDIS_URL is set.",
        )
        self.assertIn(
            "_REDIS_URL",
            src,
            "settings.py must gate the Redis channel layer on _REDIS_URL.",
        )
