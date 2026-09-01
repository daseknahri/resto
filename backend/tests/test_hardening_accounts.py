"""Accounts-views hardening regression tests.

Covers five fixes applied to backend/accounts/views.py, all mock-based
(SimpleTestCase — no DB), matching the house style:

  1. MarketplaceOrderCancelView concurrency: the cancel now re-loads the order UNDER
     select_for_update and gates the NON-idempotent loyalty claw-back + restock on the
     transition THIS call performed (newly_cancelled), keeping the idempotent wallet
     refund unconditional, and stands the assigned driver down. Mirrors the hardened
     refund_and_cancel_delivery_order (menu/views.py). Proves a racing peer-cancel
     replays the refund but does NOT double-claw loyalty or double-restock.

  2. DriverJobStatusUpdateView DELIVERED branch: a client-supplied proof_photo_url no
     longer bypasses the proof-of-delivery code gate. Only a server-saved, Pillow-
     validated FILE sets _has_photo. Proves {status:delivered, proof_photo_url:...} with
     no code is rejected (400 bad_delivery_code) and the payout is NOT banked, while a
     legitimate FILE upload still completes.

  3/4. AdminPlatformAnalyticsView: cancelled delivery jobs are excluded from the "active"
     KPI, and the Total Fees / Total Payouts money cards sum only DELIVERED (realized)
     jobs so they reconcile with the financials block.

  5. MarketplaceOrderStatusView: the owner payload now ships created_at so the marketplace
     tracking page's ETA countdown can compute readyAt (was permanently "Ready any moment
     now"). Mirrors the direct page (menu/views.py).
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q, Sum
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer
from accounts.views import (
    AdminPlatformAnalyticsView,
    DriverJobStatusUpdateView,
    MarketplaceOrderCancelView,
    MarketplaceOrderStatusView,
)
from menu.models import Order


def _noop_cm():
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _sc_mock():
    """schema_context(...) returns a context manager."""
    return MagicMock(return_value=_noop_cm())


# ── Finding 1: marketplace-cancel concurrency guard ───────────────────────────

class MarketplaceCancelConcurrencyTests(SimpleTestCase):
    """The cancel must re-read the row under a lock and run the non-idempotent helpers
    (loyalty reversal + restock) ONLY on the call that actually flipped it to CANCELLED,
    while the idempotent wallet refund always replays and the driver is stood down."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # MarketplaceOrderStatusThrottle counts per-actor
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderCancelView.as_view()

    def _run_cancel(self, *, pre_status, locked_status):
        customer = Customer(id=42)
        order = MagicMock()
        order.customer_id = 42  # == customer.id → IsOrderOwner passes
        order.status = pre_status  # what THIS caller read before the lock
        order.order_number = "ORD-1"

        locked = MagicMock()
        locked.status = locked_status  # what the row reports UNDER select_for_update
        locked.order_number = "ORD-1"

        req = self.factory.post(
            "/api/marketplace/order/ORD-1/cancel/", {"restaurant": "tacos"}, format="json"
        )
        req.session = {"customer_id": 42}
        force_authenticate(req, user=customer)

        tenant = SimpleNamespace(id=7, schema_name="tacos", slug="tacos")
        Tenant = MagicMock()
        Tenant.objects.get.return_value = tenant

        OrderObjs = MagicMock()
        OrderObjs.filter.return_value.first.return_value = order  # pre-lock read
        (OrderObjs.select_for_update.return_value
            .filter.return_value.first.return_value) = locked     # under-lock re-read

        with patch("tenancy.models.Tenant", Tenant), \
             patch("menu.models.Order.objects", OrderObjs), \
             patch("django_tenants.utils.schema_context", return_value=_noop_cm()), \
             patch("django.db.transaction.atomic", return_value=_noop_cm()), \
             patch("menu.views._customer_can_cancel", return_value=True), \
             patch("menu.views._refund_wallet_for_cancelled_order") as refund_m, \
             patch("menu.views._reverse_loyalty_for_cancelled_order") as revloy_m, \
             patch("menu.views._restock_cancelled_order") as restock_m, \
             patch("menu.views._broadcast_order_change"), \
             patch("accounts.delivery_service.cancel_delivery_job_for_order") as cancel_job_m:
            resp = self.view(req, order_number="ORD-1")

        return SimpleNamespace(
            resp=resp, refund=refund_m, revloy=revloy_m, restock=restock_m,
            cancel_job=cancel_job_m, order=order, locked=locked,
        )

    def test_live_row_runs_full_reversal_once_and_stands_driver_down(self):
        """First/only cancel of a live PENDING order: flips it to CANCELLED, refunds,
        claws loyalty + restocks exactly once, and stands the assigned driver down."""
        r = self._run_cancel(pre_status=Order.Status.PENDING, locked_status=Order.Status.PENDING)

        self.assertEqual(r.resp.status_code, status.HTTP_200_OK)
        self.assertEqual(r.locked.status, Order.Status.CANCELLED)  # THIS call flipped it
        r.refund.assert_called_once()
        self.assertEqual(r.refund.call_args.kwargs.get("tenant_id"), 7)
        r.revloy.assert_called_once()
        r.restock.assert_called_once()
        r.cancel_job.assert_called_once()  # driver stood down (was previously never called)

    def test_peer_cancelled_under_lock_replays_refund_only(self):
        """Regression (the #220-class bug): this caller loaded the order PENDING, but a racing
        peer (a second cancel tap, or the stuck-job auto-refund sweep) already flipped it to
        CANCELLED, so the row read UNDER the lock is CANCELLED. The idempotent wallet refund
        still replays, but the NON-idempotent loyalty claw-back and restock must NOT run a
        second time — otherwise loyalty is double-clawed and stock double-restocked."""
        r = self._run_cancel(pre_status=Order.Status.PENDING, locked_status=Order.Status.CANCELLED)

        self.assertEqual(r.resp.status_code, status.HTTP_200_OK)
        r.refund.assert_called_once()          # keyed → safe to replay
        r.revloy.assert_not_called()           # NOT double-clawed
        r.restock.assert_not_called()          # NOT double-restocked
        r.cancel_job.assert_called_once()       # driver stand-down is best-effort either way


# ── Finding 2: proof_photo_url no longer bypasses the delivery-code gate ───────

def _make_driver_customer(pk=1):
    c = Customer(id=pk, is_driver=True, driver_approved=True, is_driver_online=True, driver_vehicle="")
    c.save = MagicMock()
    return c


def _make_job(pk=1, status_val="picked_up", driver=None, tenant_id=1, order_number="ORD-001"):
    j = MagicMock()
    j.pk = pk
    j.id = pk
    j.status = status_val
    j.driver = driver
    j.tenant_id = tenant_id
    j.order_number = order_number
    j.code_attempts = 0
    j.code_locked_until = None
    j.created_at = MagicMock()
    j.created_at.isoformat.return_value = "2026-05-01T10:00:00+00:00"
    return j


class DriverProofPhotoBypassTests(SimpleTestCase):
    """A client-supplied proof_photo_url must NOT satisfy proof-of-delivery: only a
    server-saved FILE does. Otherwise a driver banks the payout + marks the order
    COMPLETED/PAID with no code and no real photo."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = DriverJobStatusUpdateView.as_view()
        self._atomic = patch("django.db.transaction.atomic", return_value=_noop_cm())
        self._atomic.start()

    def tearDown(self):
        self._atomic.stop()

    @staticmethod
    def _wire_status(mock_dj):
        mock_dj.Status.PICKED_UP = "picked_up"
        mock_dj.Status.DELIVERED = "delivered"
        mock_dj.Status.FAILED = "failed"
        mock_dj.Status.AT_RESTAURANT = "at_restaurant"

    def _authed(self, req, customer):
        req.session = {}
        force_authenticate(req, user=customer)
        return req

    @patch("accounts.views._complete_delivered_order")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_client_url_with_no_code_is_rejected(self, mock_cust_objs, mock_dj, mock_complete):
        """PATCH {status:delivered, proof_photo_url:"https://evil/x.jpg"} with no code and
        no FILE is rejected 400 bad_delivery_code — the payout is NOT banked."""
        customer = _make_driver_customer()
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        # DELIVERED branch re-reads driver_approved from the DB.
        mock_cust_objs.filter.return_value.exists.return_value = True

        req = self.factory.patch(
            "/api/driver/jobs/1/status/",
            {"status": "delivered", "proof_photo_url": "https://evil.example/x.jpg"},
            format="json",
        )
        with patch("accounts.views._order_delivery_code", return_value="1234"), \
             patch("django.utils.timezone.now", return_value=MagicMock()):
            resp = self.view(self._authed(req, customer), job_id=1)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data.get("code"), "bad_delivery_code")
        mock_complete.assert_not_called()  # order NOT completed, payout NOT banked

    @patch("accounts.views._complete_delivered_order")
    @patch("accounts.models.DeliveryJob")
    @patch("accounts.models.Customer.objects")
    def test_valid_file_photo_still_completes(self, mock_cust_objs, mock_dj, mock_complete):
        """The legitimate FILE path is unchanged: a server-validated proof_photo FILE sets
        _has_photo and completes the delivery (leave-at-door) without a code."""
        customer = _make_driver_customer()
        job = _make_job(status_val="picked_up", driver=customer)
        mock_dj.objects.select_for_update.return_value.get.return_value = job
        self._wire_status(mock_dj)
        mock_cust_objs.filter.return_value.exists.return_value = True

        photo = SimpleUploadedFile("proof.jpg", b"\xff\xd8\xff\xe0fakejpeg", content_type="image/jpeg")
        req = self.factory.patch(
            "/api/driver/jobs/1/status/",
            {"status": "delivered", "proof_photo": photo},
            format="multipart",
        )
        with patch("accounts.ride_views._save_driver_doc_image", return_value="https://app/media/proof.jpg"), \
             patch("accounts.views._order_delivery_code", return_value="1234"), \
             patch("accounts.views._serialize_delivery_job", return_value={"id": 1, "status": "delivered"}), \
             patch("accounts.views._batch_business_types", return_value={}), \
             patch("django.utils.timezone.now", return_value=MagicMock()):
            resp = self.view(self._authed(req, customer), job_id=1)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_complete.assert_called_once()
        # The server-saved URL (not any client value) is what gets recorded.
        self.assertEqual(mock_complete.call_args.kwargs.get("proof_photo_url"), "https://app/media/proof.jpg")


# ── Findings 3 & 4: platform analytics realized basis ─────────────────────────

class PlatformAnalyticsRealizedBasisTests(SimpleTestCase):
    """Cancelled jobs are excluded from 'active', and the fee/payout money cards sum only
    DELIVERED jobs so they reconcile with the financials block."""

    def setUp(self):
        # AdminPlatformAnalyticsView now caches its payload under a single global key. Both test
        # methods here run the real build and assert on the ORM call_args; clear the cache so the
        # second method isn't served the first's cached payload (which would skip the ORM calls).
        from django.core.cache import cache
        cache.clear()

    def _run(self):
        Tenant = MagicMock()
        Tenant.objects.all.return_value.count.return_value = 2
        Tenant.objects.all.return_value.filter.return_value.count.return_value = 1
        Tenant.objects.aggregate.return_value = {"s": Decimal("0")}

        Cust = MagicMock()
        Cust.objects.count.return_value = 5
        # .filter(is_driver=True).aggregate(...) is called twice on the same mock: once for the
        # driver-count stats (total/online) and once for driver_owed (Sum wallet_balance -> "s").
        # One dict carries the keys for both reads.
        Cust.objects.filter.return_value.aggregate.return_value = {
            "total": 3, "online": 1, "s": Decimal("0"),
        }
        Cust.objects.aggregate.return_value = {"total_balance": Decimal("0")}

        DJ = MagicMock()
        DJ.objects.aggregate.return_value = {
            "total": 10, "delivered": 6, "failed": 1, "searching": 1,
            "avg_rating": None, "total_fees": Decimal("0"), "total_payouts": Decimal("0"),
        }
        DJ.objects.exclude.return_value.count.return_value = 2
        DJ.objects.filter.return_value.aggregate.return_value = {"s": Decimal("0")}

        DZone = MagicMock()
        DZone.objects.aggregate.return_value = {"total": 0, "active": 0}

        FS = MagicMock()
        FS.objects.aggregate.return_value = {"total": 0, "active": 0, "total_redemptions": 0}

        Ride = MagicMock()
        Ride.objects.aggregate.return_value = {
            "total": 0, "completed": 0, "cancelled": 0, "wallet_paid": 0, "fare_gmv": Decimal("0"),
        }
        Ride.objects.exclude.return_value.count.return_value = 0

        WT = MagicMock()
        WT.objects.aggregate.return_value = {
            "total": 0, "total_bonus": Decimal("0"), "total_payments": Decimal("0"),
        }
        WT.objects.filter.return_value.values.return_value.annotate.return_value = []
        # driver_paid now reads WalletTransaction CASHOUT rows (Sum amount -> "s").
        WT.objects.filter.return_value.aggregate.return_value = {"s": Decimal("0")}

        DP = MagicMock()
        DP.objects.aggregate.return_value = {"s": Decimal("0")}

        with patch("tenancy.models.Tenant", Tenant), \
             patch("accounts.models.Customer", Cust), \
             patch("accounts.models.DeliveryJob", DJ), \
             patch("accounts.models.DeliveryZone", DZone), \
             patch("accounts.models.PlatformFlashSale", FS), \
             patch("accounts.models.RideRequest", Ride), \
             patch("accounts.models.WalletTransaction", WT), \
             patch("accounts.models.DriverPayout", DP):
            resp = AdminPlatformAnalyticsView().get(MagicMock())
        return resp, DJ

    def test_cancelled_jobs_excluded_from_active(self):
        resp, DJ = self._run()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The active-jobs query must exclude the third terminal status too.
        DJ.objects.exclude.assert_any_call(status__in=["delivered", "failed", "cancelled"])

    def test_fee_and_payout_sums_filtered_to_delivered(self):
        resp, DJ = self._run()
        agg_kwargs = DJ.objects.aggregate.call_args.kwargs
        for key in ("total_fees", "total_payouts"):
            expr = agg_kwargs[key]
            self.assertIsInstance(expr, Sum)
            self.assertEqual(expr.filter, Q(status="delivered"))


# ── Finding 5: marketplace order-status ETA payload ───────────────────────────

class MarketplaceOrderStatusEtaTests(SimpleTestCase):
    """The owner payload must include created_at so the marketplace ETA countdown works."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = MarketplaceOrderStatusView.as_view()

    def test_owner_body_includes_created_at(self):
        tenant = MagicMock()
        tenant.slug = "bistro"
        tenant.name = "Bistro"
        tenant.schema_name = "bistro"
        order = MagicMock()
        order.order_number = "ORD-001"
        order.status = "confirmed"
        order.fulfillment_type = "pickup"
        order.customer_id = 7
        order.total = "25.00"
        order.delivery_fee = "0.00"
        order.wallet_amount_paid = "0.00"
        order.currency = "EUR"
        order.estimated_ready_minutes = 40
        order.scheduled_for = None
        order.created_at.isoformat.return_value = "2026-08-16T10:00:00+00:00"
        order.items.all.return_value = []

        req = self.factory.get("/api/marketplace/order/ORD-001/", {"restaurant": "bistro"})
        req.session = {}
        force_authenticate(req, user=Customer(id=7))  # owner

        with patch("tenancy.models.Tenant") as mock_tenant:
            mock_tenant.objects.get.return_value = tenant
            with patch("django_tenants.utils.schema_context", _sc_mock()):
                with patch("menu.models.Order") as mock_order:
                    (mock_order.objects.filter.return_value
                        .prefetch_related.return_value.select_related.return_value.first.return_value) = order
                    resp = self.view(req, order_number="ORD-001")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("created_at", resp.data)
        self.assertEqual(resp.data["created_at"], "2026-08-16T10:00:00+00:00")
