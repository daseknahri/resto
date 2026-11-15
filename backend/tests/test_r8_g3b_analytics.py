"""
Tests for Run 8 G3b W2 — AdminPlatformAnalytics period scoping (A-15) and
server generated_at (A-16).

Mock-based SimpleTestCase (no DB), following tests/test_admin_wallet_views.py:
  - scope parsing is exercised directly on _parse_analytics_scope;
  - get() is exercised with get_or_build_single_flight mocked to call the
    builder through, and the model layer replaced by fake managers whose
    aggregate()/count() return canned figures and record filter kwargs, so the
    real _build_analytics runs and its scoping + generated_at are asserted.

Default behaviour pinned: a request with no params uses the exact historic
cache key and returns the all-time payload (period "all", from/to None).
"""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.views import AdminPlatformAnalyticsView, _parse_analytics_scope


# ── Fake QuerySet layer ───────────────────────────────────────────────────────

class _FakeValues:
    def __init__(self, spec):
        self.spec = spec

    def annotate(self, **kwargs):
        return list(self.spec.get("values_rows", []))


class _FakeQS:
    """Minimal QuerySet stand-in: filter/exclude return a narrowed copy;
    count()/aggregate() dispatch on the narrowed kwargs; every call is
    recorded on the spec so tests can assert what was (not) scoped."""

    def __init__(self, spec, kwargs=None):
        self.spec = spec
        self.kwargs = dict(kwargs or {})

    def _narrow(self, extra):
        merged = dict(self.kwargs)
        merged.update(extra)
        return _FakeQS(self.spec, merged)

    def all(self):
        return self

    def filter(self, *args, **kwargs):
        self.spec.setdefault("filter_calls", []).append(dict(kwargs))
        return self._narrow(kwargs)

    def exclude(self, *args, **kwargs):
        self.spec.setdefault("exclude_calls", []).append(dict(kwargs))
        return self._narrow(kwargs)

    def count(self):
        fn = self.spec.get("count")
        return fn(self.kwargs) if fn else 0

    def aggregate(self, **kwargs):
        self.spec.setdefault("aggregate_calls", []).append(
            (dict(self.kwargs), dict(kwargs))
        )
        fn = self.spec.get("aggregate")
        return fn(self.kwargs, kwargs) if fn else {}

    def values(self, *fields):
        return _FakeValues(self.spec)


def _manager(spec):
    m = MagicMock()
    root = _FakeQS(spec)
    m.all.return_value = root
    m.filter.side_effect = lambda *a, **kw: root.filter(*a, **kw)
    m.exclude.side_effect = lambda *a, **kw: root.exclude(*a, **kw)
    m.count.side_effect = lambda: root.count()
    m.aggregate.side_effect = lambda **kw: root.aggregate(**kw)
    m.values.side_effect = lambda *f: root.values(*f)
    return m


# ── Canned model specs ────────────────────────────────────────────────────────

def _tenant_spec():
    def count(kw):
        return {"active": 7, "suspended": 2, "canceled": 1}.get(
            kw.get("lifecycle_status"), 10
        )

    return {
        "count": count,
        "aggregate": lambda kw, agg: {"s": Decimal("100.00")},
    }


def _customer_spec():
    def aggregate(kw, agg):
        if "total" in agg:
            return {"total": 5}  # registered drivers (scoped qs)
        if "online" in agg:
            return {"online": 2}  # drivers online (unscoped by design)
        if "total_balance" in agg:
            return {"total_balance": Decimal("1000.00")}
        if set(agg) == {"s"}:
            return {"s": Decimal("20.00")}  # driver_owed (unscoped by design)
        return {}

    return {"count": lambda kw: 50, "aggregate": aggregate}


def _job_spec():
    def aggregate(kw, agg):
        if "avg_rating" in agg:
            return {
                "total": 100,
                "delivered": 80,
                "failed": 5,
                "searching": 3,
                "avg_rating": 4.72,
                "total_fees": Decimal("500.00"),
                "total_payouts": Decimal("300.00"),
            }
        if set(agg) == {"s"}:
            return {"s": Decimal("300.00")}  # driver_earned (scoped qs)
        return {}

    return {"aggregate": aggregate, "count": lambda kw: 12}


def _zone_spec():
    return {
        "aggregate": lambda kw, agg: {"total": 4, "active": 3},
        "count": lambda kw: 4,
    }


def _flash_sale_spec():
    def aggregate(kw, agg):
        if "active" in agg:
            return {"active": 1}  # live now (unscoped by design)
        return {"total": 6, "total_redemptions": 9}

    return {"aggregate": aggregate, "count": lambda kw: 6}


def _ride_spec():
    def aggregate(kw, agg):
        return {
            "total": 30,
            "completed": 28,
            "cancelled": 1,
            "wallet_paid": 20,
            "fare_gmv": Decimal("150.00"),
        }

    return {"aggregate": aggregate, "count": lambda kw: 2}


def _txn_spec():
    def aggregate(kw, agg):
        if "total" in agg and "total_bonus" in agg:
            return {
                "total": 40,
                "total_bonus": Decimal("50.00"),
                "total_payments": Decimal("200.00"),
            }
        if set(agg) == {"s"}:
            return {"s": Decimal("40.00")}  # driver_paid (scoped qs)
        return {}

    return {
        "aggregate": aggregate,
        "count": lambda kw: 40,
        "values_rows": [
            {"vertical": "food", "total": Decimal("100.00"), "count": 3},
        ],
    }


@contextmanager
def _mocked_models():
    """Replace the models _build_analytics imports with fake managers.

    Yields the specs dict (each spec records filter/aggregate calls)."""
    specs = {
        "Tenant": _tenant_spec(),
        "Customer": _customer_spec(),
        "DeliveryJob": _job_spec(),
        "DeliveryZone": _zone_spec(),
        "PlatformFlashSale": _flash_sale_spec(),
        "RideRequest": _ride_spec(),
        "WalletTransaction": _txn_spec(),
    }
    mocks = {}
    for name, spec in specs.items():
        mock = MagicMock()
        mock.objects = _manager(spec)
        mocks[name] = mock
    targets = [
        ("tenancy.models.Tenant", mocks["Tenant"]),
        ("accounts.models.Customer", mocks["Customer"]),
        ("accounts.models.DeliveryJob", mocks["DeliveryJob"]),
        ("accounts.models.DeliveryZone", mocks["DeliveryZone"]),
        ("accounts.models.PlatformFlashSale", mocks["PlatformFlashSale"]),
        ("accounts.models.RideRequest", mocks["RideRequest"]),
        ("accounts.models.WalletTransaction", mocks["WalletTransaction"]),
    ]
    with ExitStack() as stack:
        for target, mock in targets:
            stack.enter_context(patch(target, mock))
        yield specs


def _admin():
    u = MagicMock()
    u.is_authenticated = True
    u.is_superuser = True
    u.is_staff = True
    u.is_platform_admin = True
    return u


NOW = datetime(2026, 11, 15, 12, 0, 0, tzinfo=dt_timezone.utc)


# ── Scope parsing (pure, no DB) ───────────────────────────────────────────────

class ParseAnalyticsScopeTests(SimpleTestCase):
    def test_default_no_params_is_all_time(self):
        self.assertEqual(
            _parse_analytics_scope(SimpleNamespace(query_params={}), NOW),
            ("all", None, None),
        )

    def test_period_all_explicit(self):
        self.assertEqual(
            _parse_analytics_scope(
                SimpleNamespace(query_params={"period": "all"}), NOW
            ),
            ("all", None, None),
        )

    def test_period_7d_window(self):
        self.assertEqual(
            _parse_analytics_scope(
                SimpleNamespace(query_params={"period": "7d"}), NOW
            ),
            ("7d", NOW - timedelta(days=7), NOW),
        )

    def test_period_30d_window(self):
        self.assertEqual(
            _parse_analytics_scope(
                SimpleNamespace(query_params={"period": "30d"}), NOW
            ),
            ("30d", NOW - timedelta(days=30), NOW),
        )

    def test_from_to_custom_covers_whole_days(self):
        period, start, end = _parse_analytics_scope(
            SimpleNamespace(
                query_params={"from": "2026-11-01", "to": "2026-11-07"}
            ),
            NOW,
        )
        self.assertEqual(period, "custom")
        self.assertEqual(str(start), "2026-11-01 00:00:00+00:00")
        self.assertEqual(str(end), "2026-11-07 23:59:59.999999+00:00")

    def test_from_to_iso_datetimes_kept(self):
        period, start, end = _parse_analytics_scope(
            SimpleNamespace(
                query_params={
                    "from": "2026-11-01T10:00:00Z",
                    "to": "2026-11-02T11:00:00+02:00",
                }
            ),
            NOW,
        )
        self.assertEqual(period, "custom")
        self.assertEqual(str(start), "2026-11-01 10:00:00+00:00")
        self.assertEqual(str(end), "2026-11-02 11:00:00+02:00")

    def test_invalid_period_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(query_params={"period": "90d"}), NOW
            )

    def test_lone_from_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(query_params={"from": "2026-11-01"}), NOW
            )

    def test_lone_to_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(query_params={"to": "2026-11-07"}), NOW
            )

    def test_period_and_range_conflict_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(
                    query_params={
                        "period": "7d",
                        "from": "2026-11-01",
                        "to": "2026-11-07",
                    }
                ),
                NOW,
            )

    def test_from_after_to_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(
                    query_params={"from": "2026-11-07", "to": "2026-11-01"}
                ),
                NOW,
            )

    def test_invalid_date_raises(self):
        with self.assertRaises(ValueError):
            _parse_analytics_scope(
                SimpleNamespace(
                    query_params={"from": "not-a-date", "to": "2026-11-07"}
                ),
                NOW,
            )


# ── get() end-to-end with the real builder (mocked model layer) ─────────────

class AdminPlatformAnalyticsScopeTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AdminPlatformAnalyticsView.as_view()

    def _get(self, url):
        """GET through the view with single-flight mocked to call through."""
        calls = {}

        def _through(key, builder, ttl=None):
            calls["key"] = key
            calls["ttl"] = ttl
            return builder()

        with _mocked_models() as specs:
            with patch(
                "accounts.views.get_or_build_single_flight",
                side_effect=_through,
            ) as single_flight:
                req = self.factory.get(url)
                req.user = _admin()
                resp = self.view(req)
        return resp, calls, specs, single_flight

    def test_get_default_uses_base_cache_key_and_all_time_payload(self):
        resp, calls, specs, _ = self._get("/api/admin/platform-analytics/")
        self.assertEqual(resp.status_code, 200)
        # Default cache key is the exact historic key (no scope suffix).
        self.assertEqual(calls["key"], "admin_platform_analytics:v1")
        data = resp.data
        self.assertEqual(data["period"], "all")
        self.assertIsNone(data["from"])
        self.assertIsNone(data["to"])
        # Canned all-time figures flow through unchanged.
        self.assertEqual(
            data["tenants"],
            {"total": 10, "active": 7, "suspended": 2, "canceled": 1},
        )
        self.assertEqual(data["customers"]["total"], 50)
        self.assertEqual(data["deliveries"]["total_jobs"], 100)
        self.assertEqual(data["deliveries"]["avg_driver_rating"], 4.7)
        self.assertEqual(data["rides"]["fare_gmv"], "150.00")
        self.assertEqual(data["rides"]["cash_paid"], 8)
        self.assertEqual(
            data["revenue_by_vertical"][0],
            {"vertical": "food", "total": 100.0, "count": 3},
        )

    def test_get_7d_uses_scoped_cache_key_and_scopes_flows(self):
        resp, calls, specs, _ = self._get(
            "/api/admin/platform-analytics/?period=7d"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(calls["key"], "admin_platform_analytics:v1:7d")
        self.assertEqual(resp.data["period"], "7d")
        self.assertIsNotNone(resp.data["from"])
        self.assertIsNotNone(resp.data["to"])
        # Flow queries were bounded by created_at …
        job_filters = specs["DeliveryJob"].get("filter_calls", [])
        self.assertTrue(
            any("created_at__gte" in c for c in job_filters),
            f"DeliveryJob never scoped by created_at: {job_filters}",
        )
        self.assertTrue(
            any("created_at__lte" in c for c in job_filters),
        )

    def test_get_30d_uses_scoped_cache_key(self):
        _, calls, _, _ = self._get("/api/admin/platform-analytics/?period=30d")
        self.assertEqual(calls["key"], "admin_platform_analytics:v1:30d")

    def test_get_custom_range_uses_scoped_cache_key_and_window(self):
        resp, calls, _, _ = self._get(
            "/api/admin/platform-analytics/?from=2026-11-01&to=2026-11-07"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(calls["key"].startswith("admin_platform_analytics:v1:custom:"))
        self.assertEqual(resp.data["period"], "custom")
        self.assertTrue(resp.data["from"].startswith("2026-11-01T00:00:00"))
        self.assertTrue(resp.data["to"].startswith("2026-11-07T23:59:59"))

    def test_get_invalid_period_returns_400_without_building(self):
        resp, calls, _, single_flight = self._get(
            "/api/admin/platform-analytics/?period=90d"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(single_flight.called)
        self.assertEqual(calls, {})

    def test_scoped_build_keeps_point_in_time_figures_unscoped(self):
        _, _, specs, _ = self._get("/api/admin/platform-analytics/?period=7d")
        # Tenant lifecycle counts: no created_at filter anywhere.
        tenant_filters = specs["Tenant"].get("filter_calls", [])
        self.assertTrue(tenant_filters)  # lifecycle filters did run
        self.assertFalse(
            any("created_at__gte" in c for c in tenant_filters),
            f"tenant counts must stay all-time: {tenant_filters}",
        )
        # Drivers-online + driver-owed aggregates ran on unscoped querysets.
        cust_aggs = specs["Customer"].get("aggregate_calls", [])
        for qs_kwargs, agg_kwargs in cust_aggs:
            if "online" in agg_kwargs or set(agg_kwargs) == {"s"}:
                self.assertNotIn("created_at__gte", qs_kwargs)
        # Zones aggregate + flash-sale "live" aggregate ran unscoped …
        zone_aggs = specs["DeliveryZone"].get("aggregate_calls", [])
        self.assertTrue(all(qs == {} for qs, _ in zone_aggs))
        fs_aggs = specs["PlatformFlashSale"].get("aggregate_calls", [])
        live = [qs for qs, agg in fs_aggs if "active" in agg]
        self.assertEqual(live, [{}])
        # … while the flash-sale totals aggregate ran scoped.
        totals = [qs for qs, agg in fs_aggs if "active" not in agg]
        self.assertTrue(all("created_at__gte" in qs for qs in totals))

    def test_generated_at_is_present_and_recent(self):
        resp, _, _, _ = self._get("/api/admin/platform-analytics/")
        generated = resp.data.get("generated_at")
        self.assertIsNotNone(generated)
        parsed = datetime.fromisoformat(generated)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertLess(
            abs((datetime.now(dt_timezone.utc) - parsed).total_seconds()), 60
        )
