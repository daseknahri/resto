"""
A5 — Marketplace commission correctness.

Covers the per-tenant commission RATE, the rate SNAPSHOT onto each order, the
tenant-local-month bucketing of the commission statement, and the
admin-only / NOT-owner-editable nature of the platform take-rate knob.

  * commission uses the tenant's Profile.marketplace_commission_pct (a fraction —
    0.15 → 15% of the PRE-discount food_subtotal);
  * commission falls back to 0.10 when the field is null/missing
    (default behaviour MUST be unchanged);
  * the rate used is snapshotted onto the order (Order.commission_rate_applied);
  * the commission statement buckets by the TENANT-LOCAL month — a late-night
    month-boundary order for a non-UTC tenant lands in the right month (the
    queryset is filtered on an aware [month_start, next_month_start) range in the
    tenant's tz, NOT created_at__year/__month in UTC) — and surfaces the rate;
  * marketplace_commission_pct is a PLATFORM revenue knob: it is absent from the
    owner ProfileSerializer write path (an owner cannot set its own commission)
    and is set only via the platform-admin AdminTenantDeliveryView endpoint.

All tests are unit-level (SimpleTestCase + mocks — no real DB or schema switch).
The order view imports its models at function scope INSIDE schema_context, so we
inject fakes through sys.modules (same technique as test_a4_marketplace_cod.py).
"""
import sys
from contextlib import contextmanager
from io import BytesIO
from datetime import datetime, timezone as _tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.views import MarketplacePlaceOrderView
from menu.views import OwnerCommissionStatementView
from sales.views import AdminTenantDeliveryView
from tenancy.serializers import ProfileSerializer


# ── Helpers (mirror test_a4_marketplace_cod.py) ───────────────────────────────

class _FakeDNE(Exception):
    """Stand-in for Model.DoesNotExist so the view's except clause works."""


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _sc_mock():
    @contextmanager
    def _inner(*args, **kwargs):
        yield
    return _inner


def _profile(marketplace_commission_pct="0.10"):
    p = MagicMock()
    p.is_menu_published = True
    p.cod_enabled = False
    p.cod_min_paid_orders = 3
    p.lat = None
    p.lng = None
    p.marketplace_commission_pct = (
        Decimal(marketplace_commission_pct) if marketplace_commission_pct is not None else None
    )
    return p


def _dish(slug="burger", price="10.00", currency="MAD", stock_qty=None):
    d = MagicMock()
    d.slug = slug
    d.name = "Burger"
    d.price = Decimal(price)
    d.currency = currency
    d.stock_qty = stock_qty
    d.category = MagicMock()
    d.category.course = 0
    d.combo_components.all.return_value = []
    return d


def _customer(cid=7, wallet="1000"):
    c = MagicMock()
    c.id = cid
    c.pk = cid
    c.wallet_balance = Decimal(wallet)
    c.name = "Repeat Diner"
    c.phone = "+212600000000"
    c.loyalty_points = 0
    return c


def _fake_menu_models(dish):
    order_cls = MagicMock()
    order_cls.objects.filter.return_value.first.return_value = None
    order_cls.objects.filter.return_value.exists.return_value = False

    dish_cls = MagicMock()
    dish_qs = MagicMock()
    dish_qs.select_related.return_value = dish_qs
    dish_qs.prefetch_related.return_value = [dish]
    dish_cls.objects.filter.return_value = dish_qs
    dish_cls.objects.select_for_update.return_value.filter.return_value = []

    promo_cls = MagicMock()
    promo_cls.objects.filter.return_value.order_by.return_value = []

    do_cls = MagicMock()
    do_cls.objects.filter.return_value.select_related.return_value = []

    m = MagicMock()
    m.Dish = dish_cls
    m.DishOption = do_cls
    m.Order = order_cls
    m.OrderItem = MagicMock()
    m.Promotion = promo_cls
    return m, order_cls


@contextmanager
def _inject_module(name, module):
    original = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield
    finally:
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ── Commission RATE + SNAPSHOT at marketplace checkout ────────────────────────

class MarketplaceCommissionRateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = MarketplacePlaceOrderView.as_view()

    def _post(self, data, session=None):
        req = self.factory.post("/api/marketplace/order/", data, format="json")
        req.user = _anon()
        req.session = session or {}
        return self.view(req)

    def _run_order(self, *, profile, customer):
        """Drive a marketplace pickup order to creation; return (response, order_cls)."""
        dish = _dish()  # 10.00 each
        fake_menu, order_cls = _fake_menu_models(dish)

        created_order = MagicMock()
        created_order.order_number = "ORD-A5"
        created_order.status = "pending"
        created_order.total = Decimal("20.00")
        created_order.delivery_fee = Decimal("0")
        created_order.currency = "MAD"
        created_order.wallet_amount_paid = Decimal("20.00")
        created_order.scheduled_for = None
        order_cls.objects.create.return_value = created_order

        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=None)
        cm.__exit__ = MagicMock(return_value=False)

        payload = {
            "restaurant": "bistro",
            "items": [{"slug": "burger", "qty": 2}],  # food_subtotal = 20.00
            "fulfillment_type": "pickup",
        }

        # Fake wallet_tx returned by debit_wallet — amount matches the order total.
        fake_wallet_tx = MagicMock()
        fake_wallet_tx.amount = Decimal("20.00")

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.DoesNotExist = _FakeDNE
            tenant.lifecycle_status = mock_tenant.LifecycleStatus.ACTIVE
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()), \
                    patch("tenancy.models.Profile") as mock_profile_cls, \
                    patch("accounts.views.Customer") as mock_cust_cls, \
                    patch("accounts.wallet_service.debit_wallet", return_value=fake_wallet_tx), \
                    patch("django.db.transaction.atomic", return_value=cm), \
                    patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("menu.views._cod_eligible", return_value=False), \
                    patch("menu.views._profile_now", return_value=None), \
                    patch("menu.pricing.get_active_happy_hours", return_value=[]), \
                    patch("menu.pricing.effective_unit_price",
                          side_effect=lambda d, hh: (d.price, None)):
                mock_profile_cls.objects.filter.return_value.first.return_value = profile
                mock_cust_cls.DoesNotExist = _FakeDNE
                mock_cust_cls.objects.get.return_value = customer
                with _inject_module("menu.models", fake_menu):
                    resp = self._post(payload, session={"customer_id": customer.id})
        return resp, order_cls

    def test_commission_uses_tenant_rate(self):
        """0.15 rate → commission = 15% of the 20.00 food_subtotal = 3.00, and the
        rate is snapshotted onto the order."""
        resp, order_cls = self._run_order(
            profile=_profile(marketplace_commission_pct="0.15"),
            customer=_customer(wallet="1000"),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        kwargs = order_cls.objects.create.call_args.kwargs
        self.assertEqual(kwargs["commission_amount"], Decimal("3.00"))
        self.assertEqual(kwargs["commission_rate_applied"], Decimal("0.15"))

    def test_commission_defaults_to_10pct_when_null(self):
        """Null rate → falls back to the historical 0.10 (default behaviour unchanged):
        commission = 10% of 20.00 = 2.00; the 0.10 fallback is snapshotted."""
        resp, order_cls = self._run_order(
            profile=_profile(marketplace_commission_pct=None),
            customer=_customer(wallet="1000"),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        kwargs = order_cls.objects.create.call_args.kwargs
        self.assertEqual(kwargs["commission_amount"], Decimal("2.00"))
        self.assertEqual(kwargs["commission_rate_applied"], Decimal("0.10"))


# ── Commission STATEMENT — tenant-local month bucketing ───────────────────────

class CommissionStatementBucketTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerCommissionStatementView.as_view()

    def _run(self, *, year, month, tz_name, capture):
        """Drive the statement GET; `capture` collects Order.objects.filter kwargs."""
        tenant = MagicMock()
        tenant.id = 1
        tenant.slug = "bistro"
        profile = MagicMock()
        profile.timezone = tz_name
        profile.service_day_cutover_hour = 0
        tenant.profile = profile

        qs = MagicMock()
        # A5-followup: the statement query is now filter(...).exclude(...).order_by(...)
        # — the .exclude() drops cancelled orders. Chain it back to the same qs.
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.aggregate.return_value = {"order_count": 0, "total_revenue": None, "total_commission": None}
        qs.__iter__ = lambda s: iter([])

        def _filter(**kwargs):
            capture.update(kwargs)
            return qs

        with patch("menu.views._is_tenant_owner", return_value=True), \
                patch("menu.views.Order") as mock_order:
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status.CANCELLED = "cancelled"
            mock_order.objects.filter.side_effect = _filter
            req = self.factory.get(f"/api/owner/commission-statement/?year={year}&month={month}")
            req.user = MagicMock(is_authenticated=True)
            req.tenant = tenant
            resp = self.view(req)
        return resp

    def test_buckets_by_tenant_local_month_not_utc(self):
        """A non-UTC tenant's statement filters on an aware [month_start, next) range
        in the tenant tz — NOT created_at__year/__month (UTC). The June window for an
        Asia/Dubai (UTC+4) tenant therefore starts at 2026-06-01 00:00 +04:00, which
        is 2026-05-31 20:00 UTC — so a 23:30-on-May-31 *Dubai-local* order (already
        June 1 in UTC) is correctly EXCLUDED from June and a 23:30-on-June-30 Dubai
        order (July in UTC) is correctly INCLUDED."""
        capture = {}
        resp = self._run(year=2026, month=6, tz_name="Asia/Dubai", capture=capture)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Must NOT use the buggy UTC calendar-field filter.
        self.assertNotIn("created_at__year", capture)
        self.assertNotIn("created_at__month", capture)

        # Must use an aware tenant-local half-open range.
        self.assertIn("created_at__gte", capture)
        self.assertIn("created_at__lt", capture)
        start = capture["created_at__gte"]
        end = capture["created_at__lt"]
        self.assertIsNotNone(start.tzinfo)
        # Start is June 1 00:00 in the tenant's local wall clock…
        self.assertEqual((start.year, start.month, start.day, start.hour), (2026, 6, 1, 0))
        self.assertEqual((end.year, end.month, end.day, end.hour), (2026, 7, 1, 0))
        # …which is offset from UTC (UTC+4 → 4h ahead).
        self.assertEqual(start.utcoffset().total_seconds(), 4 * 3600)
        # The half-open UTC instant for June-start is 2026-05-31 20:00Z.
        self.assertEqual(start.astimezone(_tz.utc), datetime(2026, 5, 31, 20, 0, tzinfo=_tz.utc))

    def test_december_rolls_to_next_year(self):
        """December's upper bound is Jan 1 of the next year (no month-13)."""
        capture = {}
        resp = self._run(year=2026, month=12, tz_name="UTC", capture=capture)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        start = capture["created_at__gte"]
        end = capture["created_at__lt"]
        self.assertEqual((start.year, start.month), (2026, 12))
        self.assertEqual((end.year, end.month), (2027, 1))

    def test_statement_rows_surface_commission_rate_applied(self):
        """Per-order rows expose the snapshotted commission_rate_applied for audit."""
        tenant = MagicMock()
        tenant.id = 1
        profile = MagicMock()
        profile.timezone = "UTC"
        profile.service_day_cutover_hour = 0
        tenant.profile = profile

        order = SimpleNamespace(
            order_number="ORD-1",
            created_at=datetime(2026, 6, 15, 12, 0, tzinfo=_tz.utc),
            customer_name="Diner",
            total=Decimal("20.00"),
            commission_amount=Decimal("3.00"),
            commission_rate_applied=Decimal("0.15"),
            currency="MAD",
            status="completed",
        )
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.aggregate.return_value = {
            "order_count": 1,
            "total_revenue": Decimal("20.00"),
            "total_commission": Decimal("3.00"),
        }
        qs.__iter__ = lambda s: iter([order])

        with patch("menu.views._is_tenant_owner", return_value=True), \
                patch("menu.views.Order") as mock_order:
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status.CANCELLED = "cancelled"
            mock_order.objects.filter.return_value = qs
            req = self.factory.get("/api/owner/commission-statement/?year=2026&month=6")
            req.user = MagicMock(is_authenticated=True)
            req.tenant = tenant
            resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["orders"][0]["commission_rate_applied"], 0.15)


# ── PDF statement commission LABEL reflects the actual rate (not a literal 10%) ─

class CommissionStatementPdfLabelTests(SimpleTestCase):
    """The PDF summary's commission line must state the ACTUAL rate, derived from
    the per-order commission_rate_applied snapshots — never a hardcoded 10%. For a
    non-default-rate tenant a literal "10%" next to a 15%-derived total would
    misstate an official money document the owner uses for payout reconciliation."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def _order(self, *, number, total, commission, rate):
        return SimpleNamespace(
            order_number=number,
            created_at=datetime(2026, 6, 15, 12, 0, tzinfo=_tz.utc),
            customer_name="Diner",
            total=Decimal(total),
            commission_amount=Decimal(commission),
            commission_rate_applied=Decimal(rate),
            currency="MAD",
            status="completed",
        )

    def _pdf_text(self, orders):
        """Drive the PDF branch and return the extracted text of the rendered PDF."""
        tenant = MagicMock()
        tenant.id = 1
        profile = MagicMock()
        profile.timezone = "UTC"
        profile.service_day_cutover_hour = 0
        tenant.profile = profile

        total_rev = sum((o.total for o in orders), Decimal("0"))
        total_com = sum((o.commission_amount for o in orders), Decimal("0"))
        qs = MagicMock()
        qs.exclude.return_value = qs
        qs.order_by.return_value = qs
        qs.aggregate.return_value = {
            "order_count": len(orders),
            "total_revenue": total_rev,
            "total_commission": total_com,
        }
        qs.__iter__ = lambda s: iter(orders)

        with patch("menu.views._is_tenant_owner", return_value=True), \
                patch("menu.views.Order") as mock_order:
            mock_order.Source.MARKETPLACE = "marketplace"
            mock_order.Status.CANCELLED = "cancelled"
            mock_order.objects.filter.return_value = qs
            req = self.factory.get(
                "/api/owner/commission-statement/?year=2026&month=6&format=pdf"
            )
            req.user = MagicMock(is_authenticated=True)
            req.tenant = tenant
            # Drive .get() directly (not via as_view dispatch): DRF's ?format=
            # URL_FORMAT_OVERRIDE negotiation would reject the unknown "pdf" format
            # before the view body runs. The view reads request.query_params["format"]
            # itself, so disable DRF's format_kwarg and invoke the handler.
            view = OwnerCommissionStatementView()
            view.format_kwarg = None
            drf_req = view.initialize_request(req)
            resp = view.get(drf_req)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(b"".join(resp.streaming_content)
                                   if hasattr(resp, "streaming_content")
                                   else resp.content))
        return "".join(page.extract_text() for page in reader.pages)

    def test_non_default_rate_label_shows_actual_rate(self):
        """A 15%-rate tenant's PDF says 'Platform commission (15%)', not '(10%)'."""
        text = self._pdf_text([self._order(number="ORD-1", total="20.00",
                                           commission="3.00", rate="0.15")])
        self.assertIn("Platform commission (15%)", text)
        self.assertNotIn("(10%)", text)

    def test_default_rate_label_still_shows_10pct(self):
        """The default 10%-rate tenant keeps the familiar 'Platform commission (10%)'."""
        text = self._pdf_text([self._order(number="ORD-1", total="20.00",
                                           commission="2.00", rate="0.10")])
        self.assertIn("Platform commission (10%)", text)

    def test_mixed_rates_drop_the_percentage_literal(self):
        """When the month mixes rates (e.g. a mid-month rate change), no single
        percentage is shown — just 'Platform commission:' — since one number can't
        summarise multiple rates. The total stays correct (sum of actuals)."""
        text = self._pdf_text([
            self._order(number="ORD-1", total="20.00", commission="2.00", rate="0.10"),
            self._order(number="ORD-2", total="20.00", commission="3.00", rate="0.15"),
        ])
        self.assertIn("Platform commission:", text)
        self.assertNotIn("(10%)", text)
        self.assertNotIn("(15%)", text)


# ── NOT owner-editable + admin-editable ───────────────────────────────────────

class MarketplaceCommissionNotOwnerEditableTests(SimpleTestCase):
    def test_field_absent_from_owner_serializer(self):
        """The platform take-rate must NOT be on the owner ProfileSerializer at all —
        an owner cannot read or write its own commission."""
        self.assertNotIn("marketplace_commission_pct", ProfileSerializer.Meta.fields)

    def test_owner_cannot_write_marketplace_commission(self):
        """Even if an owner posts the field, it never lands in validated_data."""
        s = ProfileSerializer(data={"marketplace_commission_pct": "0.01"}, partial=True)
        s.is_valid()
        self.assertNotIn("marketplace_commission_pct", s.validated_data)


def _passthrough_cm():
    cm = Mock()
    cm.__enter__ = Mock(return_value=None)
    cm.__exit__ = Mock(return_value=False)
    return cm


def _admin():
    return Mock(is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True, pk=1, id=1)


def _admin_tenant():
    return SimpleNamespace(id=1, pk=1, slug="demo", name="Demo", schema_name="demo")


def _admin_profile(**kw):
    p = SimpleNamespace(
        delivery_enabled=True,
        platform_delivery_enabled=False,
        delivery_fee=Decimal("0.00"),
        delivery_base_fee=Decimal("0.00"),
        delivery_per_km=Decimal("0.00"),
        delivery_free_over=Decimal("0.00"),
        delivery_minimum_order=Decimal("0.00"),
        delivery_radius_km=None,
        delivery_zone_description="",
        delivery_commission_pct=Decimal("0.00"),
        marketplace_commission_pct=Decimal("0.10"),
        save=Mock(),
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class AdminCanSetMarketplaceCommissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminTenantDeliveryView.as_view()

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_sets_marketplace_commission(self, mock_g404, mock_profile):
        mock_g404.return_value = _admin_tenant()
        prof = _admin_profile()
        mock_profile.objects.filter.return_value.first.return_value = prof
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/", {"marketplace_commission_pct": "0.15"}, format="json"
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(prof.marketplace_commission_pct, Decimal("0.15"))
        self.assertEqual(resp.data["delivery"]["marketplace_commission_pct"], "0.15")

    @patch("tenancy.models.Profile")
    @patch("sales.views.schema_context", lambda *a, **k: _passthrough_cm())
    @patch("sales.views.get_object_or_404")
    def test_admin_patch_rejects_rate_over_one(self, mock_g404, mock_profile):
        mock_g404.return_value = _admin_tenant()
        mock_profile.objects.filter.return_value.first.return_value = _admin_profile()
        req = self.factory.patch(
            "/api/admin-tenants/1/delivery/", {"marketplace_commission_pct": "1.5"}, format="json"
        )
        force_authenticate(req, user=_admin())
        resp = self.view(req, tenant_id=1)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
