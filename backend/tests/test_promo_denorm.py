"""
B8-followup — marketplace promo-badge cross-schema N+1 kill via promo denorm.

Promotions (menu.Promotion) live per-tenant; the marketplace listing used to
switch into every tenant's schema to fetch active promos and derive a
"promo_badge" (the LAST cross-schema N+1 in the listing loop; ratings were already
killed in B8). The promo SCHEDULE is now denormalized onto the public
Profile.marketplace_promos, kept in sync by the menu.Promotion
post_save/post_delete signals and backfilled by a management command. The badge's
"live now" decision is evaluated in-memory at REQUEST time (same windowing rule as
the checkout path), mirroring the flash-sale schedule denorm.

Contracts covered:

  recompute_tenant_promos (menu.promos_denorm)
    - serializes is_active promos (ONLY the badge fields) to the PUBLIC Profile,
      ordered by highest discount first (the selection the view relied on)
    - busts the public list cache
    - no-op when tenant is None / has no schema / is the public schema
    - best-effort: swallows errors

  _is_promo_active_now / _promo_badge_from_denorm (accounts.views)
    - one windowing rule evaluates a denormalized DICT in-memory
    - active vs out-of-window (time) vs out-of-date-range vs wrong-day → None
    - emits the SAME badge strings as the old in-loop code

  signals (menu.signals)
    - Promotion post_save / post_delete call recompute for the connection tenant
    - no-op on the public schema and when there's no real tenant

  views (accounts.views)
    - MarketplaceView builds promo_badge from profile.marketplace_promos WITHOUT
      entering a per-tenant schema_context or querying menu.Promotion

House style: SimpleTestCase + MagicMock, no real DB or schema switch.
"""
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import (
    MarketplaceView,
    _is_promo_active_now,
    _promo_badge_from_denorm,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _tenant(schema_name="bistro", tid=1):
    t = MagicMock()
    t.id = tid
    t.schema_name = schema_name
    t.name = "Bistro"
    t.slug = "bistro"
    return t


def _denorm_promo(**kwargs):
    """A denormalized promo dict as stored in Profile.marketplace_promos.

    Defaults to an always-live percentage promo (no day/time/date window).
    """
    p = {
        "promo_type": "percentage",
        "discount_value": "20.00",
        "days": [],
        "time_start": "",
        "time_end": "",
        "active_from": None,
        "active_until": None,
    }
    p.update(kwargs)
    return p


def _today_weekday_token():
    """The mon..sun token for today's UTC weekday (matches the windowing rule)."""
    _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return _WDAY[datetime.utcnow().weekday()]


def _other_weekday_token():
    _WDAY = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
    return _WDAY[(datetime.utcnow().weekday() + 1) % 7]


# ═══════════════════════════════════════════════════════════════════════════════
# recompute_tenant_promos
# ═══════════════════════════════════════════════════════════════════════════════

class RecomputeTenantPromosTests(SimpleTestCase):
    """menu.promos_denorm.recompute_tenant_promos writes the denormalized schedule."""

    def _run(self, promo_models, schema_name="bistro"):
        """Invoke recompute_tenant_promos with Promotion + Profile mocked.

        promo_models: list of MagicMock promos returned (in order) by
        Promotion.objects.filter(is_active=True).order_by(...)[:5].
        Returns (mock_profile, tenant, bust_mock).
        """
        from menu import promos_denorm as mod

        tenant = _tenant(schema_name=schema_name)

        mock_promotion = MagicMock()
        # filter(...).order_by(...)[:5] → iterable of promo models
        ordered = MagicMock()
        ordered.__getitem__ = lambda s, k: promo_models
        mock_promotion.objects.filter.return_value.order_by.return_value = ordered

        mock_profile = MagicMock()

        @contextmanager
        def _sc(*a, **k):
            yield

        fake_menu_models = MagicMock()
        fake_menu_models.Promotion = mock_promotion

        import sys
        original = sys.modules.get("menu.models")
        sys.modules["menu.models"] = fake_menu_models
        try:
            with patch("django_tenants.utils.schema_context", _sc), \
                    patch("tenancy.models.Profile", mock_profile), \
                    patch("accounts.views._bust_public_list_cache") as bust:
                mod.recompute_tenant_promos(tenant)
        finally:
            if original is None:
                sys.modules.pop("menu.models", None)
            else:
                sys.modules["menu.models"] = original
        return mock_profile, tenant, bust

    def _promo_model(self, **kwargs):
        m = MagicMock()
        m.promo_type = kwargs.get("promo_type", "percentage")
        m.discount_value = kwargs.get("discount_value", "20.00")
        m.days = kwargs.get("days", [])
        m.time_start = kwargs.get("time_start", "")
        m.time_end = kwargs.get("time_end", "")
        m.active_from = kwargs.get("active_from", None)
        m.active_until = kwargs.get("active_until", None)
        return m

    def test_serializes_only_badge_fields_to_public_profile(self):
        promo = self._promo_model(
            promo_type="percentage",
            discount_value="25.00",
            days=["mon", "tue"],
            time_start="09:00",
            time_end="17:00",
            active_from=date(2026, 1, 1),
            active_until=date(2026, 12, 31),
        )
        mock_profile, tenant, _ = self._run([promo])
        mock_profile.objects.filter.assert_called_once_with(tenant=tenant)
        update_kwargs = mock_profile.objects.filter.return_value.update.call_args.kwargs
        promos = update_kwargs["marketplace_promos"]
        self.assertEqual(len(promos), 1)
        entry = promos[0]
        self.assertEqual(set(entry.keys()), {
            "promo_type", "discount_value", "days",
            "time_start", "time_end", "active_from", "active_until",
        })
        self.assertEqual(entry["promo_type"], "percentage")
        self.assertEqual(entry["discount_value"], "25.00")  # serialized as str
        self.assertEqual(entry["days"], ["mon", "tue"])
        self.assertEqual(entry["time_start"], "09:00")
        self.assertEqual(entry["time_end"], "17:00")
        self.assertEqual(entry["active_from"], "2026-01-01")  # ISO
        self.assertEqual(entry["active_until"], "2026-12-31")

    def test_preserves_selection_ordering(self):
        """The list is written in the SAME order the query yielded (highest discount
        first) — the view's selection relied on it."""
        p1 = self._promo_model(discount_value="30.00")
        p2 = self._promo_model(discount_value="10.00")
        mock_profile, _, _ = self._run([p1, p2])
        promos = mock_profile.objects.filter.return_value.update.call_args.kwargs["marketplace_promos"]
        self.assertEqual([e["discount_value"] for e in promos], ["30.00", "10.00"])

    def test_no_promos_writes_empty_list(self):
        mock_profile, _, _ = self._run([])
        promos = mock_profile.objects.filter.return_value.update.call_args.kwargs["marketplace_promos"]
        self.assertEqual(promos, [])

    def test_busts_public_list_cache(self):
        _, _, bust = self._run([self._promo_model()])
        bust.assert_called_once()

    def test_null_dates_serialize_to_none(self):
        promo = self._promo_model(active_from=None, active_until=None)
        mock_profile, _, _ = self._run([promo])
        entry = mock_profile.objects.filter.return_value.update.call_args.kwargs["marketplace_promos"][0]
        self.assertIsNone(entry["active_from"])
        self.assertIsNone(entry["active_until"])

    def test_noop_when_tenant_none(self):
        from menu import promos_denorm as mod
        with patch("tenancy.models.Profile") as mock_profile:
            mod.recompute_tenant_promos(None)
        mock_profile.objects.filter.assert_not_called()

    def test_noop_on_public_schema(self):
        from menu import promos_denorm as mod
        from django_tenants.utils import get_public_schema_name

        tenant = _tenant(schema_name=get_public_schema_name())
        with patch("tenancy.models.Profile") as mock_profile:
            mod.recompute_tenant_promos(tenant)
        mock_profile.objects.filter.assert_not_called()

    def test_best_effort_swallows_errors(self):
        from menu import promos_denorm as mod

        tenant = _tenant()

        @contextmanager
        def _boom(*a, **k):
            raise RuntimeError("schema down")
            yield  # pragma: no cover

        with patch("django_tenants.utils.schema_context", _boom):
            mod.recompute_tenant_promos(tenant)  # must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# _is_promo_active_now / _promo_badge_from_denorm — in-memory windowing on a dict
# ═══════════════════════════════════════════════════════════════════════════════

class PromoWindowingOnDictTests(SimpleTestCase):
    """The SAME windowing rule evaluates a denormalized DICT in-memory."""

    def test_always_live_promo_is_active(self):
        self.assertTrue(_is_promo_active_now(_denorm_promo()))

    def test_out_of_date_range_before_start(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        self.assertFalse(_is_promo_active_now(_denorm_promo(active_from=future)))

    def test_out_of_date_range_after_end(self):
        past = (date.today() - timedelta(days=5)).isoformat()
        self.assertFalse(_is_promo_active_now(_denorm_promo(active_until=past)))

    def test_inside_date_range(self):
        past = (date.today() - timedelta(days=5)).isoformat()
        future = (date.today() + timedelta(days=5)).isoformat()
        self.assertTrue(_is_promo_active_now(
            _denorm_promo(active_from=past, active_until=future)
        ))

    def test_wrong_day_is_inactive(self):
        self.assertFalse(_is_promo_active_now(
            _denorm_promo(days=[_other_weekday_token()])
        ))

    def test_right_day_is_active(self):
        self.assertTrue(_is_promo_active_now(
            _denorm_promo(days=[_today_weekday_token()])
        ))

    def test_out_of_time_window_is_inactive(self):
        # A window that has already closed today (UTC).
        self.assertFalse(_is_promo_active_now(
            _denorm_promo(time_start="00:00", time_end="00:01")
        ))

    def test_inside_time_window_is_active(self):
        # A window spanning the whole day → always inside.
        self.assertTrue(_is_promo_active_now(
            _denorm_promo(time_start="00:00", time_end="23:59")
        ))


class PromoBadgeStringTests(SimpleTestCase):
    """_promo_badge_from_denorm emits the SAME strings as the old in-loop code."""

    def test_percentage_badge_string(self):
        badge = _promo_badge_from_denorm([_denorm_promo(
            promo_type="percentage", discount_value="20.00"
        )])
        self.assertEqual(badge, "20% off")  # int() of the value, as before

    def test_fixed_badge_string(self):
        badge = _promo_badge_from_denorm([_denorm_promo(
            promo_type="fixed", discount_value="5.00"
        )])
        # Byte-identical to old f"-{Decimal('5.00')} off".
        self.assertEqual(badge, "-5.00 off")

    def test_free_delivery_badge_string(self):
        badge = _promo_badge_from_denorm([_denorm_promo(
            promo_type="free_delivery", discount_value="0.00"
        )])
        self.assertEqual(badge, "Free delivery")

    def test_first_live_entry_wins(self):
        """Selection: the first live entry in the (highest-discount-first) list wins."""
        out_of_window = _denorm_promo(
            discount_value="30.00", time_start="00:00", time_end="00:01"
        )
        live = _denorm_promo(promo_type="percentage", discount_value="15.00")
        badge = _promo_badge_from_denorm([out_of_window, live])
        self.assertEqual(badge, "15% off")

    def test_no_live_promo_returns_none(self):
        out_of_window = _denorm_promo(time_start="00:00", time_end="00:01")
        self.assertIsNone(_promo_badge_from_denorm([out_of_window]))

    def test_empty_list_returns_none(self):
        self.assertIsNone(_promo_badge_from_denorm([]))

    def test_none_returns_none(self):
        self.assertIsNone(_promo_badge_from_denorm(None))


# ═══════════════════════════════════════════════════════════════════════════════
# signals
# ═══════════════════════════════════════════════════════════════════════════════

class PromoSignalTests(SimpleTestCase):
    """menu.Promotion post_save/post_delete refresh the denormalized schedule."""

    def test_post_save_recomputes_for_connection_tenant(self):
        from menu.signals import denormalize_promos_on_save

        tenant = _tenant()
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.promos_denorm.recompute_tenant_promos") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_promos_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_called_once_with(tenant)

    def test_post_delete_recomputes_for_connection_tenant(self):
        from menu.signals import denormalize_promos_on_delete

        tenant = _tenant()
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.promos_denorm.recompute_tenant_promos") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_promos_on_delete(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_called_once_with(tenant)

    def test_noop_on_public_schema(self):
        from menu.signals import denormalize_promos_on_save
        from django_tenants.utils import get_public_schema_name

        tenant = _tenant(schema_name=get_public_schema_name())
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.promos_denorm.recompute_tenant_promos") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_promos_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_not_called()

    def test_noop_when_no_tenant(self):
        from menu.signals import denormalize_promos_on_save

        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.promos_denorm.recompute_tenant_promos") as mock_recompute:
            mock_conn.tenant = None
            denormalize_promos_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# MarketplaceView — promo badge built in-memory, NO schema_context
# ═══════════════════════════════════════════════════════════════════════════════

def _make_profile(**kwargs):
    """A marketplace Profile row with the denormalized rating + promo fields."""
    p = MagicMock()
    p.directory_opt_in = True
    p.is_menu_published = True
    p.is_open = True
    p.is_menu_temporarily_disabled = False
    p.tagline = "Great food"
    p.logo_url = "https://example.com/logo.png"
    p.cuisine_type = "Italian"
    p.business_type = "restaurant"
    p.city = "Paris"
    p.delivery_enabled = True
    p.lat = 48.8566
    p.lng = 2.3522
    p.delivery_fee = "2.00"
    p.delivery_minimum_order = "15.00"
    p.price_tier = 2
    p.tags = ["halal"]
    p.address = "1 Rue de la Paix"
    p.business_hours_schedule = {}
    p.rating_avg = None
    p.rating_count = 0
    # B8-followup denormalized promo schedule
    p.marketplace_promos = []
    tenant = MagicMock()
    tenant.id = 1
    tenant.slug = "bistro"
    tenant.name = "Bistro Paris"
    tenant.schema_name = "bistro"
    p.tenant = tenant
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class MarketplacePromoBadgeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = MarketplaceView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/marketplace/", params or {})
        req.user = _anon()
        return self.view(req)

    def _run_with_one_profile(self, profile):
        """Drive the view with a single profile row; patch flash sales to empty."""
        with patch("tenancy.models.Profile") as mock_p:
            qs = MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            with patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("django_tenants.utils.schema_context") as mock_sc, \
                    patch("menu.models.Promotion") as mock_promo:
                optin_m = MagicMock()
                optin_m.objects.values.return_value = []
                fs_m = MagicMock()
                fs_m.objects.filter.return_value = []
                with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                        patch("accounts.models.PlatformFlashSale", fs_m):
                    resp = self._get()
            return resp, mock_sc, mock_promo

    def test_badge_built_from_denorm_no_schema_context(self):
        """promo_badge comes from profile.marketplace_promos; the loop enters NO
        per-tenant schema_context and never queries menu.Promotion."""
        profile = _make_profile(marketplace_promos=[
            _denorm_promo(promo_type="percentage", discount_value="20.00")
        ])
        resp, mock_sc, mock_promo = self._run_with_one_profile(profile)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        r = resp.data["restaurants"][0]
        self.assertEqual(r["promo_badge"], "20% off")
        # The promo N+1 is gone: no schema switch, no Promotion query in the loop.
        mock_sc.assert_not_called()
        mock_promo.objects.filter.assert_not_called()

    def test_no_promos_yields_null_badge(self):
        profile = _make_profile(marketplace_promos=[])
        resp, mock_sc, mock_promo = self._run_with_one_profile(profile)
        r = resp.data["restaurants"][0]
        self.assertIsNone(r["promo_badge"])
        mock_sc.assert_not_called()

    def test_out_of_window_promo_yields_null_badge(self):
        """A denormalized promo that is not live now produces no badge (in-memory
        windowing at request time)."""
        profile = _make_profile(marketplace_promos=[
            _denorm_promo(time_start="00:00", time_end="00:01")
        ])
        resp, mock_sc, _ = self._run_with_one_profile(profile)
        r = resp.data["restaurants"][0]
        self.assertIsNone(r["promo_badge"])
        mock_sc.assert_not_called()

    def test_fixed_badge_matches_old_format(self):
        profile = _make_profile(marketplace_promos=[
            _denorm_promo(promo_type="fixed", discount_value="5.00")
        ])
        resp, _, _ = self._run_with_one_profile(profile)
        self.assertEqual(resp.data["restaurants"][0]["promo_badge"], "-5.00 off")
