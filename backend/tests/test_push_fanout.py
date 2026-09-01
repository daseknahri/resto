"""Push fan-out: bounded-pool delivery + capped dispatch audience.

Covers the perf hardening of the Web-Push fan-out:
  - menu.push._fan_out — delivers to many subscriptions via a SMALL bounded thread
    pool, preserving the sequential loop's exact semantics (delivered tally + the ids
    of expired "gone" subscriptions for the caller to bulk-delete). The pool never
    exceeds its worker cap and actually parallelizes up to it.
  - accounts.push.notify_car_drivers_new_ride_sync — the package branch ("all online
    approved drivers, any vehicle type") must be HARD-CAPPED like the ride branch, even
    when pickup GPS is missing, so one trip can't fan out to the whole driver pool.
  - accounts.push.notify_online_drivers_new_job_sync — the pooled driver-dispatch path
    still tallies delivered pushes and bulk-deletes expired subscriptions (the DB cleanup
    runs on the caller's thread AFTER the pool joins — never inside a worker).

Unit-level (SimpleTestCase + mocks — no DB).
"""
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from menu.push import _PUSH_FANOUT_WORKERS, _fan_out


def _noop_ctx():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _ns(i):
    return SimpleNamespace(id=i)


def _sub(customer_id, sub_id):
    s = MagicMock()
    s.id = sub_id
    s.customer_id = customer_id
    s.endpoint = f"https://push.example/{sub_id}"
    s.p256dh = "p256dh-key"
    s.auth = "auth-key"
    return s


def _driver(i):
    d = MagicMock()
    d.id = i
    d.driver_lat = float(i)
    d.driver_lng = 0.0
    return d


# ══════════════════════════════════════════════════════════════════════════════
# _fan_out — the bounded-pool helper
# ══════════════════════════════════════════════════════════════════════════════

class FanOutHelperTests(SimpleTestCase):
    def test_empty_subs_never_calls_send_fn(self):
        calls = []
        sent, gone = _fan_out([], lambda s: calls.append(s) or "ok")
        self.assertEqual(sent, 0)
        self.assertEqual(gone, [])
        self.assertEqual(calls, [])

    def test_tallies_ok_and_collects_gone_ids(self):
        # Mixed outcomes: one delivered, two gone, one transient error.
        subs = [_ns(1), _ns(2), _ns(3), _ns(4)]
        outcomes = {1: "ok", 2: "gone", 3: "error", 4: "gone"}
        sent, gone = _fan_out(subs, lambda s: outcomes[s.id])
        self.assertEqual(sent, 1)          # only sub 1 delivered
        self.assertEqual(sorted(gone), [2, 4])   # expired ids collected for bulk delete

    def test_every_sub_is_processed_exactly_once(self):
        subs = [_ns(i) for i in range(1, 21)]
        seen = []
        lock = threading.Lock()

        def send_fn(s):
            with lock:
                seen.append(s.id)
            return "ok"

        sent, gone = _fan_out(subs, send_fn)
        self.assertEqual(sent, 20)
        self.assertEqual(gone, [])
        self.assertEqual(sorted(seen), list(range(1, 21)))

    def test_never_exceeds_worker_cap(self):
        # Upper bound is structural (a pool of N threads can never run > N tasks at once),
        # so this assertion can't be flaky. The brief hold makes overlap observable.
        subs = [_ns(i) for i in range(_PUSH_FANOUT_WORKERS * 3)]
        lock = threading.Lock()
        state = {"cur": 0, "peak": 0}

        def send_fn(s):
            with lock:
                state["cur"] += 1
                state["peak"] = max(state["peak"], state["cur"])
            time.sleep(0.01)
            with lock:
                state["cur"] -= 1
            return "ok"

        sent, gone = _fan_out(subs, send_fn)
        self.assertEqual(sent, len(subs))
        self.assertLessEqual(state["peak"], _PUSH_FANOUT_WORKERS)

    def test_parallelizes_up_to_the_worker_cap(self):
        # A barrier of exactly _PUSH_FANOUT_WORKERS parties: every send must arrive
        # together within the timeout, which only happens if the pool genuinely runs
        # that many concurrently. If it serialized, the barrier would break (timeout)
        # and _fan_out would raise — failing this test deterministically.
        n = _PUSH_FANOUT_WORKERS
        subs = [_ns(i) for i in range(n)]
        barrier = threading.Barrier(n, timeout=5)

        def send_fn(s):
            barrier.wait()
            return "ok"

        sent, gone = _fan_out(subs, send_fn)
        self.assertEqual(sent, n)
        self.assertEqual(gone, [])


# ══════════════════════════════════════════════════════════════════════════════
# notify_car_drivers_new_ride_sync — package-audience cap
# ══════════════════════════════════════════════════════════════════════════════

class PackageDriverAudienceCapTests(SimpleTestCase):
    """The package branch is 'all online approved drivers, any vehicle type'. Without a
    cap, one package request would fan out to the ENTIRE online driver pool. The audience
    must be bounded to the dispatch cap even when pickup GPS is absent (no distance sort)."""

    def _run_package_dispatch(self, *, driver_count, valid_gps, haversine=None):
        from accounts.push import notify_car_drivers_new_ride_sync

        # Drivers in reverse id order so a correct nearest-sort must actually reorder them.
        drivers = [_driver(i) for i in range(driver_count, 0, -1)]
        captured = {}

        patches = [
            patch("django_tenants.utils.schema_context", return_value=_noop_ctx()),
            patch("tenancy.delivery_pricing.valid_coord", return_value=valid_gps),
            patch("menu.push._send_one", return_value="ok"),
            patch("accounts.models.RideRequest"),
            patch("accounts.models.Customer"),
            patch("accounts.models.CustomerPushSubscription"),
            patch("accounts.notifications.record_notification"),
        ]
        with patches[0], patches[1], patches[2], patches[3] as ride_m, \
                patches[4] as cust_m, patches[5] as sub_m, patches[6]:
            if haversine is not None:
                hp = patch("tenancy.delivery_pricing.haversine_km", side_effect=haversine)
                hp.start()
                self.addCleanup(hp.stop)

            ride = MagicMock()
            ride.status = ride_m.Status.SEARCHING
            ride.kind = ride_m.Kind.PACKAGE          # is_package == True
            ride.pickup_lat = 0.0 if valid_gps else None
            ride.pickup_lng = 0.0 if valid_gps else None
            ride_m.objects.get.return_value = ride

            # First Customer.filter(...) -> candidate list; second -> (id, locale) rows.
            cust_m.objects.filter.side_effect = [
                drivers,
                MagicMock(**{"values_list.return_value": []}),
            ]

            def cap_capture(**kw):
                captured["ids"] = list(kw.get("customer_id__in", []))
                return []   # no subs -> return after the audience is resolved

            sub_m.objects.filter.side_effect = cap_capture
            notify_car_drivers_new_ride_sync(1)

        return captured["ids"]

    def test_package_audience_capped_without_gps(self):
        # 25 drivers, no pickup GPS -> the previously-uncapped path. Must cap to 10.
        ids = self._run_package_dispatch(driver_count=25, valid_gps=False)
        self.assertEqual(len(ids), 10)

    def test_package_audience_capped_and_nearest_with_gps(self):
        # With GPS the audience is the 10 NEAREST (haversine == driver_lat == id here),
        # proving the refactor kept sort-then-cap intact.
        ids = self._run_package_dispatch(
            driver_count=25, valid_gps=True,
            haversine=lambda plat, plng, dlat, dlng: dlat,
        )
        self.assertEqual(ids, list(range(1, 11)))


# ══════════════════════════════════════════════════════════════════════════════
# notify_online_drivers_new_job_sync — pooled path preserves cleanup + counts
# ══════════════════════════════════════════════════════════════════════════════

class PooledDriverDispatchCleanupTests(SimpleTestCase):
    @patch("accounts.notifications.record_notification")
    @patch("menu.push._send_one")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    def test_pooled_dispatch_tallies_and_bulk_deletes_gone(
        self, sc_m, cust_m, sub_m, job_m, send_m, rec_m
    ):
        sc_m.return_value = _noop_ctx()
        # 3 free online drivers; driver 2's subscription (id 20) is expired ("gone").
        cust_m.objects.filter.return_value.values_list.side_effect = [
            [1, 2, 3],                                  # online ids
            [(1, "en"), (2, "en"), (3, "en")],          # (id, locale) rows
        ]
        job_m.objects.filter.return_value.values_list.return_value = []   # nobody busy

        subs = [_sub(1, 10), _sub(2, 20), _sub(3, 30)]
        captured = {}

        def sub_filter(**kw):
            if "customer_id__in" in kw:
                return subs
            captured["gone"] = list(kw["id__in"])
            m = MagicMock()
            captured["delete"] = m.delete
            return m

        sub_m.objects.filter.side_effect = sub_filter
        send_m.side_effect = lambda endpoint, *a: "gone" if endpoint.endswith("/20") else "ok"

        from accounts.push import notify_online_drivers_new_job_sync
        sent = notify_online_drivers_new_job_sync("Demo Diner")

        # 2 delivered (drivers 1 & 3); the one expired sub is collected and bulk-deleted
        # AFTER the pool joins (single delete on the caller's thread).
        self.assertEqual(sent, 2)
        self.assertEqual(captured["gone"], [20])
        captured["delete"].assert_called_once()
        # Return-count shape preserved for the NotificationLog recipient string.
        self.assertEqual(rec_m.call_args.kwargs["recipient"], "2/3 drivers")
