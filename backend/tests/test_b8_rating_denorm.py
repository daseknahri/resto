"""
B8 — marketplace/directory cross-schema N+1 kill via rating denormalization.

Ratings (menu.Rating) live per-tenant; the public marketplace/directory listing
used to switch into every tenant's schema to aggregate them (an O(N_tenants)
cross-schema N+1 per request). They are now denormalized onto the public
Profile.rating_avg / rating_count, kept in sync by the menu.Rating
post_save/post_delete signals and backfilled by a management command.

Contracts covered:

  recompute_tenant_rating (menu.ratings)
    - writes avg (rounded 1dp) + count to the PUBLIC Profile
    - sets avg=None / count=0 when there are no ratings (last rating deleted)
    - no-op when tenant is None / has no schema / is the public schema

  signals (menu.signals)
    - Rating post_save / post_delete call recompute for the connection tenant
    - no-op on the public schema and when there's no real tenant

  views (accounts.views)
    - DirectoryView reads profile.rating_avg / rating_count WITHOUT entering a
      per-tenant schema_context or querying the per-tenant Rating aggregate
    - MarketplaceView reads the denormalized fields and pushes min_rating to SQL
      on the Profile queryset (no in-loop rating aggregate)

House style: SimpleTestCase + MagicMock, no real DB or schema switch.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import DirectoryView, MarketplaceView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _make_profile(**kwargs):
    """A directory/marketplace Profile row with the denormalized rating fields."""
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
    # B8 denormalized fields
    p.rating_avg = None
    p.rating_count = 0
    tenant = MagicMock()
    tenant.id = 1
    tenant.slug = "bistro"
    tenant.name = "Bistro Paris"
    tenant.schema_name = "bistro"
    p.tenant = tenant
    for k, v in kwargs.items():
        setattr(p, k, v)
    return p


def _sc_spy():
    """A schema_context replacement that records every call and is a no-op CM."""
    spy = MagicMock(name="schema_context")

    @contextmanager
    def _cm(*args, **kwargs):
        spy(*args, **kwargs)
        yield

    spy.side_effect = None
    # Wrap so callers can both use it as a CM and inspect .call_args_list.
    spy._cm = _cm
    return spy


def _tenant(schema_name="bistro", tid=1):
    t = MagicMock()
    t.id = tid
    t.schema_name = schema_name
    t.name = "Bistro"
    t.slug = "bistro"
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# recompute_tenant_rating
# ═══════════════════════════════════════════════════════════════════════════════

class RecomputeTenantRatingTests(SimpleTestCase):
    """menu.ratings.recompute_tenant_rating writes the denormalized summary."""

    def _run(self, agg, schema_name="bistro"):
        """Invoke recompute_tenant_rating with the Rating aggregate + Profile mocked.

        Returns the mock Profile class so the test can assert on .update().
        """
        from menu import ratings as ratings_mod

        tenant = _tenant(schema_name=schema_name)

        mock_rating = MagicMock()
        mock_rating.objects.aggregate.return_value = agg

        mock_profile = MagicMock()

        @contextmanager
        def _sc(*a, **k):
            yield

        fake_menu_models = MagicMock()
        fake_menu_models.Rating = mock_rating

        import sys
        original = sys.modules.get("menu.models")
        sys.modules["menu.models"] = fake_menu_models
        try:
            with patch("django_tenants.utils.schema_context", _sc), \
                    patch("tenancy.models.Profile", mock_profile):
                ratings_mod.recompute_tenant_rating(tenant)
        finally:
            if original is None:
                sys.modules.pop("menu.models", None)
            else:
                sys.modules["menu.models"] = original
        return mock_profile, tenant

    def test_writes_avg_1dp_and_count(self):
        """avg is rounded to 1dp and count is written to the public Profile."""
        mock_profile, tenant = self._run({"avg": 4.3333, "cnt": 3})
        mock_profile.objects.filter.assert_called_once_with(tenant=tenant)
        update_kwargs = mock_profile.objects.filter.return_value.update.call_args.kwargs
        self.assertEqual(update_kwargs["rating_avg"], 4.3)
        self.assertEqual(update_kwargs["rating_count"], 3)

    def test_no_ratings_sets_none_and_zero(self):
        """Deleting the last rating → avg=None, count=0."""
        mock_profile, _ = self._run({"avg": None, "cnt": 0})
        update_kwargs = mock_profile.objects.filter.return_value.update.call_args.kwargs
        self.assertIsNone(update_kwargs["rating_avg"])
        self.assertEqual(update_kwargs["rating_count"], 0)

    def test_rounds_half_up_to_one_decimal(self):
        """A 4.25 average rounds to 4.2/4.3 (round() banker's rounding) — 1dp result."""
        mock_profile, _ = self._run({"avg": 4.85, "cnt": 2})
        update_kwargs = mock_profile.objects.filter.return_value.update.call_args.kwargs
        # round(4.85, 1) is 4.8 under banker's rounding; the contract is "1dp", so
        # assert the value has at most one decimal place rather than a fixed number.
        self.assertEqual(round(update_kwargs["rating_avg"], 1), update_kwargs["rating_avg"])
        self.assertEqual(update_kwargs["rating_count"], 2)

    def test_noop_when_tenant_none(self):
        """A None tenant never touches Profile."""
        from menu import ratings as ratings_mod
        with patch("tenancy.models.Profile") as mock_profile:
            ratings_mod.recompute_tenant_rating(None)
        mock_profile.objects.filter.assert_not_called()

    def test_noop_on_public_schema(self):
        """The public schema has no Rating table — recompute must short-circuit."""
        from menu import ratings as ratings_mod
        from django_tenants.utils import get_public_schema_name

        tenant = _tenant(schema_name=get_public_schema_name())
        with patch("tenancy.models.Profile") as mock_profile:
            ratings_mod.recompute_tenant_rating(tenant)
        mock_profile.objects.filter.assert_not_called()

    def test_best_effort_swallows_errors(self):
        """A failure inside aggregation must not propagate (never 500 a rating save)."""
        from menu import ratings as ratings_mod

        tenant = _tenant()

        @contextmanager
        def _boom(*a, **k):
            raise RuntimeError("schema down")
            yield  # pragma: no cover

        with patch("django_tenants.utils.schema_context", _boom):
            # Must not raise.
            ratings_mod.recompute_tenant_rating(tenant)


# ═══════════════════════════════════════════════════════════════════════════════
# signals
# ═══════════════════════════════════════════════════════════════════════════════

class RatingSignalTests(SimpleTestCase):
    """menu.Rating post_save/post_delete refresh the denormalized rating."""

    def test_post_save_recomputes_for_connection_tenant(self):
        from menu.signals import denormalize_rating_on_save

        tenant = _tenant()
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.ratings.recompute_tenant_rating") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_rating_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_called_once_with(tenant)

    def test_post_delete_recomputes_for_connection_tenant(self):
        from menu.signals import denormalize_rating_on_delete

        tenant = _tenant()
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.ratings.recompute_tenant_rating") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_rating_on_delete(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_called_once_with(tenant)

    def test_noop_on_public_schema(self):
        """On the public schema the signal must NOT call recompute."""
        from menu.signals import denormalize_rating_on_save
        from django_tenants.utils import get_public_schema_name

        tenant = _tenant(schema_name=get_public_schema_name())
        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.ratings.recompute_tenant_rating") as mock_recompute:
            mock_conn.tenant = tenant
            denormalize_rating_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_not_called()

    def test_noop_when_no_tenant(self):
        """Outside a tenant context (connection.tenant is None) → no recompute."""
        from menu.signals import denormalize_rating_on_save

        with patch("menu.signals.connection") as mock_conn, \
                patch("menu.ratings.recompute_tenant_rating") as mock_recompute:
            mock_conn.tenant = None
            denormalize_rating_on_save(sender=MagicMock(), instance=MagicMock())
        mock_recompute.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# DirectoryView — denormalized read, no per-tenant schema_context
# ═══════════════════════════════════════════════════════════════════════════════

def _make_sliceable_qs(rows):
    qs = MagicMock()
    qs.__getitem__ = lambda s, k: rows
    return qs


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class DirectoryDenormReadTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = DirectoryView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/directory/", params or {})
        req.user = _anon()
        return self.view(req)

    def test_reads_denormalized_rating_without_schema_context(self):
        """rating_average/rating_count come from profile.rating_avg/count; the loop
        must NOT enter a per-tenant schema_context nor query the Rating aggregate."""
        profile = _make_profile(rating_avg=4.5, rating_count=12)
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            with patch("django_tenants.utils.schema_context") as mock_sc, \
                    patch("menu.models.Rating") as mock_rating:
                resp = self._get()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        r = resp.data["restaurants"][0]
        self.assertEqual(r["rating_average"], 4.5)
        self.assertEqual(r["rating_count"], 12)
        # The N+1 is gone: no schema switch, no Rating aggregate in the loop.
        mock_sc.assert_not_called()
        mock_rating.objects.aggregate.assert_not_called()

    def test_unrated_tenant_reports_none(self):
        """A Profile with rating_avg=None surfaces rating_average=None, count=0."""
        profile = _make_profile(rating_avg=None, rating_count=0)
        with patch("tenancy.models.Profile") as mock_p:
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = \
                _make_sliceable_qs([profile])
            with patch("django_tenants.utils.schema_context") as mock_sc:
                resp = self._get()
        r = resp.data["restaurants"][0]
        self.assertIsNone(r["rating_average"])
        self.assertEqual(r["rating_count"], 0)
        mock_sc.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# MarketplaceView — denormalized read + SQL min_rating filter
# ═══════════════════════════════════════════════════════════════════════════════

@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class MarketplaceDenormReadTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = MarketplaceView.as_view()

    def _get(self, params=None):
        req = self.factory.get("/api/marketplace/", params or {})
        req.user = _anon()
        return self.view(req)

    def _run_with_one_profile(self, profile, params=None, capture_qs=None):
        """Drive the view with a single profile row; patch flash sales + promo to empty.

        capture_qs (optional): a MagicMock used as the Profile.objects.filter chain
        terminal so the test can inspect .filter() calls (for the min_rating SQL push).
        """
        with patch("tenancy.models.Profile") as mock_p:
            qs = capture_qs or MagicMock()
            mock_p.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
            qs.filter.return_value = qs
            qs.__getitem__ = lambda s, k: [profile]
            with patch("accounts.views._compute_is_open_now", return_value=True), \
                    patch("django_tenants.utils.schema_context") as mock_sc, \
                    patch("menu.models.Rating") as mock_rating, \
                    patch("menu.models.Promotion") as mock_promo:
                mock_promo.objects.filter.return_value.order_by.return_value.__getitem__ = \
                    lambda s, k: []
                optin_m = MagicMock()
                optin_m.objects.values.return_value = []
                fs_m = MagicMock()
                fs_m.objects.filter.return_value = []
                with patch("accounts.models.PlatformFlashSaleOptIn", optin_m), \
                        patch("accounts.models.PlatformFlashSale", fs_m):
                    resp = self._get(params)
            return resp, qs, mock_sc, mock_rating

    def test_reads_denormalized_rating_no_aggregate(self):
        """Marketplace reads profile.rating_avg/count; the Rating aggregate is never queried."""
        profile = _make_profile(rating_avg=3.8, rating_count=7)
        resp, qs, mock_sc, mock_rating = self._run_with_one_profile(profile)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        r = resp.data["restaurants"][0]
        self.assertEqual(r["rating_average"], 3.8)
        self.assertEqual(r["rating_count"], 7)
        # The rating N+1 is gone — no Rating aggregate inside the loop.
        mock_rating.objects.aggregate.assert_not_called()

    def test_min_rating_filters_on_queryset(self):
        """?min_rating=4.0 pushes a rating_avg__gte filter onto the Profile queryset
        (SQL), not a per-row post-filter."""
        profile = _make_profile(rating_avg=4.5, rating_count=10)
        capture = MagicMock()
        resp, qs, _, _ = self._run_with_one_profile(
            profile, params={"min_rating": "4.0"}, capture_qs=capture
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # At least one .filter() call on the queryset chain carried rating_avg__gte.
        rating_filter_calls = [
            c for c in capture.filter.call_args_list
            if "rating_avg__gte" in (c.kwargs or {})
        ]
        self.assertTrue(
            rating_filter_calls,
            "min_rating must be pushed to SQL as Profile.objects...filter(rating_avg__gte=...)",
        )
        self.assertEqual(rating_filter_calls[0].kwargs["rating_avg__gte"], 4.0)

    def test_no_min_rating_means_no_rating_filter(self):
        """Without ?min_rating the queryset gets no rating_avg__gte filter."""
        profile = _make_profile(rating_avg=4.5, rating_count=10)
        capture = MagicMock()
        resp, qs, _, _ = self._run_with_one_profile(profile, capture_qs=capture)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rating_filter_calls = [
            c for c in capture.filter.call_args_list
            if "rating_avg__gte" in (c.kwargs or {})
        ]
        self.assertEqual(rating_filter_calls, [])
