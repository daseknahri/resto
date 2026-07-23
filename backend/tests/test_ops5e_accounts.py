"""OPS-5e accounts-app IDOR / info-disclosure / consistency — contract tests.

Covers the surgical fixes in accounts/views.py + accounts/og_views.py:

  A. MarketplaceOrderStatusView IDOR (accounts/views.py)
       - this endpoint is AllowAny and order numbers are enumerable
         (ORD-+token_hex(3) ≈ 24 bits), so the financial body (items, totals,
         payment_status, wallet/loyalty/promo, schedule) is gated on session
         ownership. A non-owner gets a minimal status (no financial fields);
         the session-customer owner gets the full body.

  B. CustomerPushSubscribeView endpoint hijack (accounts/views.py)
       - the upsert lookup is scoped on (customer_id, endpoint) so a customer
         can never reassign another customer's subscription row to themselves.

  C. AdminFundTenantView idempotency-key namespacing (accounts/views.py)
       - a caller-supplied idempotency_key is server-namespaced
         (adminfund:<tenant_id>:<raw>) so a chosen value can't collide across
         tenants.

  D. is_staff dropped from capability flags (accounts/views.py)
       - a staff-only user (not superuser, not platform-admin) is NOT shown an
         admin console that the actual admin endpoints would 403 on.

  E. OGView host source (accounts/og_views.py)
       - the canonical / og:image host is derived from the resolved tenant's
         authoritative primary domain, not the inbound (spoofable) Host header.

House style: SimpleTestCase + mocks, no real DB.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate


@contextmanager
def _fake_schema_context(_schema_name):
    """Stand in for django_tenants.utils.schema_context (a no-op context manager)."""
    yield


def _order_mock(customer_id=5):
    """A fully-populated marketplace order so the financial-body serialiser runs."""
    order = MagicMock()
    order.order_number = "ORD-ABC123"
    order.status = "preparing"
    order.customer_id = customer_id
    order.fulfillment_type = "delivery"
    order.payment_status = "paid"
    order.total = "120.00"
    order.delivery_fee = "10.00"
    order.wallet_amount_paid = "120.00"
    order.loyalty_discount = "0.00"
    order.redeemed_loyalty_points = 0
    order.points_earned = 12
    order.promotion_discount = "0.00"
    order.applied_promotion_name = "SUMMER"
    order.currency = "MAD"
    order.estimated_ready_minutes = 20
    order.scheduled_for = None
    order.delivery_code = "9999"
    item = MagicMock()
    item.dish_slug = "pizza"
    item.dish_name = "Pizza"
    item.qty = 1
    item.unit_price = "120.00"
    item.subtotal = "120.00"
    item.options = {}
    item.note = ""
    item.is_voided = False
    item.combo_components = []
    order.items.all.return_value = [item]
    return order


# ══════════════════════════════════════════════════════════════════════════════
# A. MarketplaceOrderStatusView IDOR
# ══════════════════════════════════════════════════════════════════════════════

class MarketplaceOrderStatusIDORTests(SimpleTestCase):
    # Financial / sensitive keys that must NOT leak to a non-owner.
    SENSITIVE = (
        "items", "total", "delivery_fee", "wallet_amount_paid", "payment_status",
        "loyalty_discount", "redeemed_loyalty_points", "points_earned",
        "promotion_discount", "applied_promotion_name", "scheduled_for",
        "delivery_code", "can_cancel",
    )

    def setUp(self):
        self.factory = APIRequestFactory()
        from accounts.views import MarketplaceOrderStatusView
        self.view = MarketplaceOrderStatusView.as_view()

    def _call(self, *, session_customer_id, order_customer_id=5):
        from accounts.models import Customer
        req = self.factory.get("/api/marketplace/order/ORD-ABC123/?restaurant=demo")
        # RISK IDENTITY-1: ownership is now the shared IsOrderOwner predicate off
        # request.user (hydrated by CustomerSessionAuthentication). force_authenticate a
        # real Customer principal instead of hand-setting the session id.
        req.session = {}
        if session_customer_id:
            force_authenticate(req, user=Customer(id=session_customer_id))
        order = _order_mock(customer_id=order_customer_id)

        tenant = SimpleNamespace(schema_name="demo", name="Demo Resto", slug="demo")

        with patch("tenancy.models.Tenant") as MockTenant, \
             patch("django_tenants.utils.schema_context", _fake_schema_context), \
             patch("menu.models.Order") as MockOrder, \
             patch("menu.views._customer_can_cancel", return_value=True):
            MockTenant.objects.get.return_value = tenant
            (MockOrder.objects.filter.return_value
                .prefetch_related.return_value.first.return_value) = order
            resp = self.view(req, order_number="ORD-ABC123")
        return resp

    def test_non_owner_gets_no_financial_body(self):
        """A caller who is not the session owner gets a minimal status only."""
        resp = self._call(session_customer_id=999, order_customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # The basic, non-sensitive status is still present...
        self.assertEqual(resp.data["order_number"], "ORD-ABC123")
        self.assertEqual(resp.data["status"], "preparing")
        # ...but no financial / sensitive field leaks.
        for key in self.SENSITIVE:
            self.assertNotIn(key, resp.data, f"non-owner leaked sensitive field {key!r}")

    def test_anonymous_gets_no_financial_body(self):
        """No session customer at all → still minimal status, no financial body."""
        resp = self._call(session_customer_id=None, order_customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for key in self.SENSITIVE:
            self.assertNotIn(key, resp.data, f"anon leaked sensitive field {key!r}")

    def test_owner_gets_full_financial_body(self):
        """The session-customer owner receives the full financial detail."""
        resp = self._call(session_customer_id=5, order_customer_id=5)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["total"], "120.00")
        self.assertEqual(resp.data["payment_status"], "paid")
        self.assertEqual(resp.data["wallet_amount_paid"], "120.00")
        self.assertEqual(len(resp.data["items"]), 1)
        self.assertEqual(resp.data["items"][0]["dish_slug"], "pizza")
        # Owner-only affordances present.
        self.assertTrue(resp.data["can_cancel"])
        self.assertEqual(resp.data["delivery_code"], "9999")


# ══════════════════════════════════════════════════════════════════════════════
# B. CustomerPushSubscribeView — endpoint hijack prevention
# ══════════════════════════════════════════════════════════════════════════════

class CustomerPushSubscribeHijackTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        from accounts.views import CustomerPushSubscribeView
        self.view = CustomerPushSubscribeView.as_view()

    @patch("accounts.models.CustomerPushSubscription.objects")
    def test_upsert_lookup_is_scoped_to_session_customer(self, mock_objs):
        """The upsert lookup includes customer_id, so a row owned by another
        customer can never be matched and silently reassigned."""
        req = self.factory.post(
            "/api/customer/push-subscribe/",
            {"endpoint": "https://push/shared", "p256dh": "key", "auth": "secret"},
            format="json",
        )
        req.session = {}
        from accounts.models import Customer
        force_authenticate(req, user=Customer(id=7))
        resp = self.view(req)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_objs.update_or_create.assert_called_once()
        _, kwargs = mock_objs.update_or_create.call_args
        # customer_id is part of the LOOKUP (not just defaults) → scoping.
        self.assertEqual(kwargs["customer_id"], 7)
        self.assertEqual(kwargs["endpoint"], "https://push/shared")


# ══════════════════════════════════════════════════════════════════════════════
# C. AdminFundTenantView — idempotency-key namespacing
# ══════════════════════════════════════════════════════════════════════════════

class AdminFundTenantIdempotencyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        from accounts.views import AdminFundTenantView
        self.view = AdminFundTenantView.as_view()

    def _admin_user(self):
        from accounts.models import User
        u = MagicMock(spec=User)
        u.pk = u.id = 1
        u.is_authenticated = True
        u.is_active = True
        u.is_superuser = True
        u.is_platform_admin = True
        return u

    def _call(self, body):
        req = self.factory.post("/api/admin/wallet/fund-tenant/", body, format="json")
        force_authenticate(req, user=self._admin_user())
        tx = MagicMock()
        tx.amount = "500.00"
        tx.balance_after = "500.00"
        with patch("accounts.wallet_service.credit_tenant_float", return_value=tx) as mock_credit, \
             patch("accounts.views.log_admin_action"):
            resp = self.view(req)
        return resp, mock_credit

    def test_caller_key_is_server_namespaced(self):
        """A body-supplied idempotency_key is prefixed with adminfund:<tenant_id>:."""
        resp, mock_credit = self._call(
            {"tenant_id": 3, "amount": "500.00", "idempotency_key": "abc"}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_credit.assert_called_once()
        _, kwargs = mock_credit.call_args
        self.assertEqual(kwargs["idempotency_key"], "adminfund:3:abc")

    def test_no_key_stays_none(self):
        """No idempotency_key supplied → None passed through (no spurious prefix)."""
        _, mock_credit = self._call({"tenant_id": 3, "amount": "500.00"})
        _, kwargs = mock_credit.call_args
        self.assertIsNone(kwargs["idempotency_key"])


# ══════════════════════════════════════════════════════════════════════════════
# D. is_staff dropped from capability flags
# ══════════════════════════════════════════════════════════════════════════════

class CapabilityFlagsTests(SimpleTestCase):
    def _user(self, *, staff=False, superuser=False, platform_admin=False):
        from accounts.models import User
        u = MagicMock(spec=User)
        u.id = 1
        u.username = "u"
        u.email = "u@example.com"
        u.role = "tenant_staff"
        u.is_staff = staff
        u.is_superuser = superuser
        u.is_platform_admin = platform_admin
        u.is_tenant_owner = False
        u.perm_manage_orders = False
        u.perm_view_revenue = False
        u.perm_edit_menu = False
        u.tenant = None
        return u

    def test_staff_only_user_cannot_access_admin_console(self):
        """A Django /admin/ is_staff flag alone must NOT show the admin console
        (the admin endpoints are is_staff-free, so it would only 403)."""
        from accounts.views import serialize_user_session
        data = serialize_user_session(self._user(staff=True))
        self.assertFalse(data["can_access_admin_console"])

    def test_platform_admin_can_access_admin_console(self):
        from accounts.views import serialize_user_session
        data = serialize_user_session(self._user(platform_admin=True))
        self.assertTrue(data["can_access_admin_console"])

    def test_staff_only_user_not_granted_all_access_permissions(self):
        """is_staff dropped from all_access too — a staff-only user with no per-flag
        grants gets no waiter-app permissions from the UI-hint dict."""
        from accounts.views import serialize_user_session
        data = serialize_user_session(self._user(staff=True))
        self.assertFalse(data["permissions"]["manage_orders"])
        self.assertFalse(data["permissions"]["view_revenue"])
        self.assertFalse(data["permissions"]["edit_menu"])


# ══════════════════════════════════════════════════════════════════════════════
# E. OGView — canonical host from tenant domain, not spoofed Host
# ══════════════════════════════════════════════════════════════════════════════

class OGCanonicalHostTests(SimpleTestCase):
    def test_canonical_uses_tenant_domain_not_spoofed_host(self):
        """The og:url + og:image host come from the tenant's authoritative primary
        domain, not the inbound (spoofable) Host header."""
        tenant = MagicMock()
        tenant.name = "Tacos House"
        tenant.is_active = True
        tenant.slug = "tacos-house"
        # Authoritative primary domain — a REAL string (so the isinstance gate fires).
        primary = SimpleNamespace(domain="tacos.kepoli.app")
        tenant.domains.filter.return_value.first.return_value = primary

        domain_obj = MagicMock()
        domain_obj.tenant = tenant

        profile = MagicMock()
        profile.tagline = "Best tacos"
        profile.hero_url = ""   # force the icon fallback so og:image host is checked
        profile.logo_url = ""

        from accounts.og_views import OGView
        factory = RequestFactory()
        # The inbound Host is attacker-controlled.
        req = factory.get("/api/og/", {"path": "/"}, HTTP_HOST="evil.attacker.example")

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain, \
             patch("accounts.og_views.Profile") as MockProfile:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            MockDomain.objects.select_related.return_value.get.return_value = domain_obj
            MockProfile.objects.filter.return_value.first.return_value = profile
            resp = OGView.as_view()(req)

        html = resp.content.decode()
        # Canonical + image use the tenant domain...
        self.assertIn("https://tacos.kepoli.app/", html)
        self.assertIn("https://tacos.kepoli.app/icon-512.png", html)
        # ...and the spoofed Host never appears in any baked URL.
        self.assertNotIn("evil.attacker.example", html)

    def test_cache_key_excludes_spoofable_host(self):
        """OPS-5g: the cache key no longer contains the inbound Host at all — it is
        keyed on the RESOLVED tenant (here: none → the platform namespace) plus the
        path. This is strictly stronger than the old host-normalisation defence: a
        spoofed Host can't fan out distinct cache rows because it never reaches the key."""
        from accounts.og_views import OGView
        factory = RequestFactory()
        req = factory.get("/api/og/", {"path": "/menu"}, HTTP_HOST="Kepoli.App:8000")

        with patch("accounts.og_views.cache") as mock_cache, \
             patch("accounts.og_views.Domain") as MockDomain:
            MockDomain.objects.select_related.return_value.get.side_effect = Exception("no domain")
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            OGView.as_view()(req)

        set_key = mock_cache.set.call_args[0][0]
        self.assertEqual(set_key, "ogpage:platform:/menu")
        self.assertNotIn("kepoli.app", set_key.lower())
