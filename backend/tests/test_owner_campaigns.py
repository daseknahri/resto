"""
Tests for owner campaign broadcasts and related pieces.

Coverage (all unit-level, SimpleTestCase + mocks — no real DB):

 1. GET /api/owner/campaigns/ — correct response shape.
 2. POST daily-cap: 409 campaign_cap on 3rd same-day campaign.
 3. POST opted-out customer excluded from audience.
 4. POST sub-less customer excluded from audience.
 5. POST audience strictly from THIS tenant's Order rows (cross-tenant isolation).
 6. POST length validation — title > 80 and message > 200 both 400.
 7. notify_promotions pref round-trip via the profile update endpoint.
 8. Digest ledger-vs-legacy mix: cash + wallet from OrderPayment rows for ledger
    orders; wallet_amount_paid fallback for legacy orders.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from accounts.views import CustomerProfileUpdateView
from menu.views import OwnerCampaignView


# ─── helpers ────────────────────────────────────────────────────────────────

def _owner_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 42
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _tenant(tid=1, slug="acme"):
    t = MagicMock()
    t.id = tid
    t.slug = slug
    t.name = "Acme"
    t.profile = MagicMock(timezone="UTC")
    return t


def _make_campaign_view_request(method, data=None, tenant_id=1):
    factory = APIRequestFactory()
    user = _owner_user(tenant_id)
    if method == "get":
        req = factory.get("/api/owner/campaigns/")
    else:
        req = factory.post("/api/owner/campaigns/", data or {}, format="json")
    force_authenticate(req, user=user)
    req.user = user
    req.tenant = _tenant(tenant_id)
    return req


# ─── 1. GET shape ────────────────────────────────────────────────────────────

class OwnerCampaignGetTests(SimpleTestCase):

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views._campaign_day_window")
    @patch("menu.views.OwnerCampaignView._audience_ids", return_value=[1, 2, 3])
    @patch("menu.views.Campaign")
    def test_get_shape(self, mock_campaign, _aud, mock_day, _gate):
        mock_day.return_value = (MagicMock(), MagicMock())
        mock_campaign.objects.filter.return_value.count.return_value = 0

        camp = MagicMock()
        camp.id = 1
        camp.title = "Hello"
        camp.message = "World"
        camp.created_by_user_id = 42
        camp.audience_count = 3
        camp.sent_count = 3
        camp.created_at.isoformat.return_value = "2026-06-11T10:00:00"
        mock_campaign.objects.order_by.return_value.__getitem__ = MagicMock(return_value=[camp])

        req = _make_campaign_view_request("get")
        resp = OwnerCampaignView.as_view()(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("audience_estimate", resp.data)
        self.assertIn("today_remaining", resp.data)
        self.assertIn("campaigns", resp.data)
        self.assertEqual(resp.data["audience_estimate"], 3)
        self.assertEqual(resp.data["today_remaining"], 2)  # cap=2, today_count=0


# ─── 2. POST cap: 409 on 3rd campaign ────────────────────────────────────────

class OwnerCampaignCapTests(SimpleTestCase):

    def _post(self, today_count, audience_override=None, lock_held=False):
        """Post a campaign request with mocked DB and cache.

        lock_held=True simulates a concurrent request already holding the mutex
        (cache.add returns False) — triggers the concurrent-cap path.
        """
        # cache.add returns False when the lock is already held (concurrent request),
        # True when the key was freshly set (this request holds the lock).
        mock_cache = MagicMock()
        mock_cache.add.return_value = not lock_held  # True = acquired, False = blocked
        mock_cache.delete = MagicMock()

        with (
            patch("menu.views._is_tenant_owner", return_value=True),
            patch("menu.views._campaign_day_window", return_value=(MagicMock(), MagicMock())),
            patch("menu.views.Campaign") as mock_campaign,
            patch("menu.views.cache", mock_cache),
        ):
            mock_campaign.objects.filter.return_value.count.return_value = today_count
            if audience_override is not None:
                with patch.object(OwnerCampaignView, "_audience_ids", return_value=audience_override):
                    req = _make_campaign_view_request(
                        "post", {"title": "Flash sale!", "message": "20% off everything today."}
                    )
                    return OwnerCampaignView.as_view()(req)
            else:
                req = _make_campaign_view_request(
                    "post", {"title": "Flash sale!", "message": "20% off everything today."}
                )
                return OwnerCampaignView.as_view()(req)

    def test_first_campaign_not_capped(self):
        # today_count=0 should proceed past the cap check, fail with no_audience
        resp = self._post(today_count=0, audience_override=[])
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "no_audience")

    def test_second_campaign_not_capped(self):
        resp = self._post(today_count=1, audience_override=[])
        self.assertEqual(resp.data.get("code"), "no_audience")

    def test_third_campaign_is_capped(self):
        resp = self._post(today_count=2)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "campaign_cap")

    def test_concurrent_request_returns_campaign_locked(self):
        """When a concurrent POST already holds the lock (cache.add returns False),
        the view returns 409 campaign_locked — a transient retry-in-a-moment
        condition, distinct from the true daily cap."""
        resp = self._post(today_count=0, lock_held=True)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "campaign_locked")


# ─── 3 & 4. Opted-out / sub-less customers excluded ─────────────────────────

class OwnerCampaignAudienceFilterTests(SimpleTestCase):
    """Test _audience_ids() filtering logic via patching at accounts.models level."""

    def _call_audience_ids(self, orderer_ids, opted_in_ids, subscribed_ids):
        """Run the real _audience_ids method with mocked DB queries."""
        view = OwnerCampaignView()

        with patch("menu.views.Order") as mock_order:
            # Step 1: tenant Order queryset
            qs1 = MagicMock()
            qs1.distinct.return_value.exclude.return_value = orderer_ids
            mock_order.objects.values_list.return_value = qs1

            with patch("menu.views.schema_context") as mock_ctx:
                cm = MagicMock()
                cm.__enter__ = MagicMock(return_value=None)
                cm.__exit__ = MagicMock(return_value=False)
                mock_ctx.return_value = cm

                with patch("accounts.models.Customer") as mock_cust, \
                     patch("accounts.models.CustomerPushSubscription") as mock_sub:

                    mock_cust.objects.filter.return_value.values_list.return_value = opted_in_ids
                    mock_sub.objects.filter.return_value.values_list.return_value.distinct.return_value = subscribed_ids

                    return view._audience_ids()

    def test_opted_out_customer_excluded(self):
        """Customer with orders but opted out must not appear in audience."""
        ids = self._call_audience_ids(
            orderer_ids=[99],
            opted_in_ids=[],       # opted out
            subscribed_ids=[99],
        )
        self.assertEqual(ids, [])

    def test_sub_less_customer_excluded(self):
        """Customer opted-in but no subscription must not appear."""
        ids = self._call_audience_ids(
            orderer_ids=[77],
            opted_in_ids=[77],
            subscribed_ids=[],     # no subscription
        )
        self.assertEqual(ids, [])

    def test_eligible_customer_included(self):
        """Customer with orders, opted-in, and subscribed is in the audience."""
        ids = self._call_audience_ids(
            orderer_ids=[55],
            opted_in_ids=[55],
            subscribed_ids=[55],
        )
        self.assertIn(55, ids)


# ─── 5. Audience strictly from THIS tenant's Order rows ──────────────────────

class OwnerCampaignTenantIsolationTests(SimpleTestCase):
    """Verify that _audience_ids() short-circuits when this tenant has no orderers —
    never reaches the public-schema Customer table with cross-tenant data."""

    def test_empty_tenant_orders_short_circuits(self):
        """If this tenant has no orders, _audience_ids() returns [] without
        touching the public Customer table at all."""
        view = OwnerCampaignView()

        with patch("menu.views.Order") as mock_order:
            qs1 = MagicMock()
            # empty set — no orderers in this tenant
            qs1.distinct.return_value.exclude.return_value = []
            mock_order.objects.values_list.return_value = qs1

            # If the public-schema Customer is ever called, fail the test
            with patch("accounts.models.Customer") as mock_cust:
                result = view._audience_ids()
                mock_cust.objects.filter.assert_not_called()

        self.assertEqual(result, [])


# ─── 6. Length validation ─────────────────────────────────────────────────────

class OwnerCampaignLengthValidationTests(SimpleTestCase):

    def _post_raw(self, title, message):
        mock_cache = MagicMock()
        mock_cache.add.return_value = True   # always acquire the lock
        mock_cache.delete = MagicMock()
        with (
            patch("menu.views._is_tenant_owner", return_value=True),
            patch("menu.views._campaign_day_window", return_value=(MagicMock(), MagicMock())),
            patch("menu.views.Campaign") as mock_campaign,
            patch("menu.views.cache", mock_cache),
        ):
            mock_campaign.objects.filter.return_value.count.return_value = 0
            req = _make_campaign_view_request("post", {"title": title, "message": message})
            return OwnerCampaignView.as_view()(req)

    def test_title_too_long_returns_400(self):
        resp = self._post_raw("x" * 81, "valid message")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_title")

    def test_message_too_long_returns_400(self):
        resp = self._post_raw("Valid title", "x" * 201)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_message")

    def test_empty_title_returns_400(self):
        resp = self._post_raw("", "valid message")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "invalid_title")

    def test_max_length_title_and_message_pass_validation(self):
        """Exact-boundary values (80 / 200 chars) must pass validation.
        We expect no_audience (no real DB) not a 400."""
        with patch.object(OwnerCampaignView, "_audience_ids", return_value=[]):
            resp = self._post_raw("x" * 80, "y" * 200)
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data.get("code"), "no_audience")


# ─── 7. notify_promotions pref round-trip via profile update endpoint ─────────

class NotifyPromotionsPrefTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerProfileUpdateView.as_view()

    @patch("accounts.views.Customer.objects")
    def test_sets_notify_promotions_false(self, objects_mock):
        cust = MagicMock(
            pk=10, email="x@y.com",
            notify_order_updates=True,
            notify_review_prompts=True,
            notify_promotions=True,
        )
        objects_mock.get.return_value = cust
        req = self.factory.patch(
            "/api/customer/profile/",
            {"notify_promotions": False},
            format="json",
        )
        req.session = {"customer_id": 10}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(cust.notify_promotions)
        kw = cust.save.call_args.kwargs
        self.assertIn("notify_promotions", kw["update_fields"])

    def test_notify_promotions_in_serialize_output(self):
        """_serialize_customer must include notify_promotions key."""
        from accounts.views import _serialize_customer
        cust = MagicMock(
            pk=11, email="a@b.co", phone="", phone_verified=False,
            email_verified=True, google_sub=None, wallet_balance=Decimal("0"),
            loyalty_points=0, locale="en", is_driver=False,
            is_driver_online=False, notify_order_updates=True,
            notify_review_prompts=True, notify_promotions=True,
            name="Alice",
        )
        data = _serialize_customer(cust)
        self.assertIn("notify_promotions", data)
        self.assertTrue(data["notify_promotions"])

    @patch("accounts.views.Customer.objects")
    def test_promotions_pref_set_then_cleared(self, objects_mock):
        """Setting notify_promotions=True after False works (round-trip)."""
        cust = MagicMock(pk=12, notify_promotions=False)
        objects_mock.get.return_value = cust
        req = self.factory.patch(
            "/api/customer/profile/",
            {"notify_promotions": True},
            format="json",
        )
        req.session = {"customer_id": 12}
        resp = self.view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(cust.notify_promotions)


# ─── 8. Digest ledger-vs-legacy mix ─────────────────────────────────────────

class DigestLedgerVsLegacyTests(SimpleTestCase):
    """_compute_summary must derive cash/wallet from ledger rows for orders that
    have them, falling back to wallet_amount_paid for legacy orders."""

    def _run_compute(
        self,
        order_ids,
        ledger_order_ids,
        ledger_wallet,
        ledger_cash,
        legacy_wallet,
        legacy_total,
        total_revenue,
        order_count=2,
    ):
        """Patch Order/OrderItem at the module level and OrderPayment via menu.models."""
        import menu.management.commands.send_daily_summary as _mod
        from menu.management.commands.send_daily_summary import _compute_summary

        # Build a mock OrderPayment that split_revenue_for_orders will use
        # (it does `from menu.models import OrderPayment` lazily).
        mock_payment = MagicMock()
        mock_payment.Method.WALLET = "wallet"
        mock_payment.Method.CASH = "cash"

        ledger_qs = MagicMock()
        ledger_qs.values_list.return_value.distinct.return_value = list(ledger_order_ids)
        ledger_qs.filter.return_value.aggregate.return_value = {
            "ledger_wallet": Decimal(str(ledger_wallet)),
            "ledger_cash": Decimal(str(ledger_cash)),
        }
        mock_payment.objects.filter.return_value = ledger_qs

        with (
            patch.object(_mod, "Order") as mock_order,
            patch.object(_mod, "OrderItem") as mock_item,
            patch("menu.models.OrderPayment", mock_payment),
        ):
            # Configure Order mock
            mock_order.Status.COMPLETED = "completed"
            mock_order.Status.READY = "ready"
            mock_order.Status.PREPARING = "preparing"
            mock_order.Status.CONFIRMED = "confirmed"

            qs = MagicMock()
            qs.aggregate.return_value = {
                "order_count": order_count,
                "total_revenue": Decimal(str(total_revenue)),
            }
            # New subquery path: exists() signals non-empty queryset;
            # values("id") returns a mock queryset used as DB subquery.
            qs.exists.return_value = True

            mock_order.objects.filter.return_value = qs

            # For legacy orders: qs.exclude(id__in=ledger_ids).aggregate(...)
            # and qs.aggregate(...) when there are no ledger orders.
            legacy_agg = {
                "legacy_wallet": Decimal(str(legacy_wallet)),
                "legacy_total": Decimal(str(legacy_total)),
            }
            legacy_qs = MagicMock()
            legacy_qs.aggregate.return_value = legacy_agg
            qs.exclude.return_value = legacy_qs
            qs.aggregate.side_effect = None  # used by _compute_summary aggregate
            # aggregate is called twice: once for order stats, once for legacy path
            # Use a call-count side-effect to return the right value each time.
            _aggregate_calls = [0]
            _order_stats_agg = {
                "order_count": order_count,
                "total_revenue": Decimal(str(total_revenue)),
            }

            def _aggregate_side_effect(**kwargs):
                _aggregate_calls[0] += 1
                if _aggregate_calls[0] == 1:
                    return _order_stats_agg
                # second call is the legacy all-orders aggregate (no ledger_ids case)
                return legacy_agg

            qs.aggregate.side_effect = _aggregate_side_effect

            # OrderItem top dishes — return empty list
            item_qs = MagicMock()
            item_qs.filter.return_value = item_qs
            item_qs.exclude.return_value = item_qs
            item_qs.values.return_value.annotate.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=[])
            mock_item.objects = item_qs

            return _compute_summary("test_schema", MagicMock(), MagicMock())

    def test_all_ledger_orders_use_ledger_amounts(self):
        """All orders have ledger rows: wallet/cash come from OrderPayment sums."""
        result = self._run_compute(
            order_ids=[1, 2],
            ledger_order_ids=[1, 2],
            ledger_wallet=30.0,
            ledger_cash=70.0,
            legacy_wallet=0.0,
            legacy_total=0.0,
            total_revenue=100.0,
            order_count=2,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["wallet_revenue"], 30.0, places=2)
        self.assertAlmostEqual(result["cash_revenue"], 70.0, places=2)

    def test_zero_orders_returns_none(self):
        """order_count=0 must return None immediately."""
        import menu.management.commands.send_daily_summary as _mod
        from menu.management.commands.send_daily_summary import _compute_summary

        with (
            patch.object(_mod, "Order") as mock_order,
            patch.object(_mod, "OrderItem"),
        ):
            mock_order.Status.COMPLETED = "completed"
            mock_order.Status.READY = "ready"
            mock_order.Status.PREPARING = "preparing"
            mock_order.Status.CONFIRMED = "confirmed"

            qs = MagicMock()
            qs.filter.return_value = qs
            qs.aggregate.return_value = {
                "order_count": 0,
                "total_revenue": None,
            }
            mock_order.objects.filter.return_value = qs

            result = _compute_summary("empty", MagicMock(), MagicMock())
        self.assertIsNone(result)

    def test_summary_fields_present(self):
        """Result dict must contain all expected keys."""
        result = self._run_compute(
            order_ids=[5],
            ledger_order_ids=[5],
            ledger_wallet=10.0,
            ledger_cash=40.0,
            legacy_wallet=0.0,
            legacy_total=0.0,
            total_revenue=50.0,
            order_count=1,
        )
        self.assertIsNotNone(result)
        for key in ("order_count", "total_revenue", "wallet_revenue", "cash_revenue", "top_dishes"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_mixed_day_ledger_and_legacy_combined(self):
        """Same day has BOTH a ledger order (has OrderPayment rows) and a legacy order
        (no rows — only wallet_amount_paid).  wallet/cash must equal the sum of both
        paths combined: ledger sums + legacy fallback sums."""
        # order 1: ledger → wallet=20, cash=30 (total=50)
        # order 2: legacy → wallet_amount_paid=15, total=40 → cash=25
        # combined wallet = 20+15=35, combined cash = 30+25=55
        result = self._run_compute(
            order_ids=[1, 2],
            ledger_order_ids=[1],      # only order 1 has ledger rows
            ledger_wallet=20.0,
            ledger_cash=30.0,
            legacy_wallet=15.0,        # order 2 wallet_amount_paid
            legacy_total=40.0,         # order 2 total (cash = 40-15=25)
            total_revenue=90.0,        # 50 + 40
            order_count=2,
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["wallet_revenue"], 35.0, places=2)
        self.assertAlmostEqual(result["cash_revenue"], 55.0, places=2)
