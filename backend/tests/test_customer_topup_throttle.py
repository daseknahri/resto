"""Wave H — P2-2: PSP top-up intent endpoint is throttled.

All tests run without a database (SimpleTestCase), mirroring
tests/test_psp_topup.py. Stripe is mocked (no stripe install needed).

Covered invariants:
  • The throttle class exists, scope "customer_topup_intent", rate 20/hour.
  • The view wires it: 20 intent calls succeed for one customer, the 21st
    is 429 — an uncapped caller can no longer mint Stripe Checkout Sessions.
  • Keying is per-customer: a second customer is unaffected by the first
    customer's cap.
  • The anonymous flag probe still answers {"enabled": False} (the throttle
    must not break the view's "safe to call always" contract).
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Customer


_PSP_ON = dict(
    PSP_TOPUP_ENABLED=True,
    PSP_STRIPE_SECRET_KEY="sk_test_dummy",
    PSP_STRIPE_WEBHOOK_SECRET="",
    PSP_SITE_URL="https://example.com",
    DEBUG=True,
)

_PSP_OFF = dict(
    PSP_TOPUP_ENABLED=False,
    PSP_STRIPE_SECRET_KEY="",
    PSP_STRIPE_WEBHOOK_SECRET="",
    PSP_SITE_URL="",
)


class TopUpIntentThrottleTests(SimpleTestCase):
    """Throttle class: scope, rate, and view wiring."""

    def setUp(self):
        cache.clear()

    def test_scope_and_rate(self):
        from accounts.throttles import CustomerTopUpIntentThrottle

        throttle = CustomerTopUpIntentThrottle()
        self.assertEqual(throttle.scope, "customer_topup_intent")
        self.assertEqual(throttle.get_rate(), "20/hour")

    def _stripe_mock(self):
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/cs_test"
        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.checkout.Session.create.return_value = mock_session
        return mock_stripe

    def _post_intent(self, view, customer_id):
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "100"}, format="json")
        req.session = {}
        force_authenticate(req, user=Customer(id=customer_id))
        return view(req)

    @override_settings(**_PSP_ON)
    def test_twenty_calls_ok_twenty_first_is_429(self):
        """P2-2: one customer gets 20 intents/hour, then 429."""
        from accounts.views import CustomerTopUpIntentView

        view = CustomerTopUpIntentView.as_view()
        with patch.dict("sys.modules", {"stripe": self._stripe_mock()}):
            for i in range(20):
                resp = self._post_intent(view, 91001)
                self.assertEqual(resp.status_code, 200, f"call {i + 1} should succeed")
                self.assertTrue(resp.data.get("enabled"))
            resp = self._post_intent(view, 91001)
            self.assertEqual(resp.status_code, 429)

    @override_settings(**_PSP_ON)
    def test_other_customer_unaffected_by_first_customers_cap(self):
        """Keying is per-customer, not global: a second customer still gets 200."""
        from accounts.views import CustomerTopUpIntentView

        view = CustomerTopUpIntentView.as_view()
        with patch.dict("sys.modules", {"stripe": self._stripe_mock()}):
            for _ in range(20):
                resp = self._post_intent(view, 91002)
                self.assertEqual(resp.status_code, 200)
            resp = self._post_intent(view, 91002)
            self.assertEqual(resp.status_code, 429)
            # A different customer is on a fresh bucket.
            resp = self._post_intent(view, 91003)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.data.get("enabled"))

    @override_settings(**_PSP_OFF)
    def test_anonymous_flag_probe_still_answers(self):
        """The {"enabled": False} probe must keep working with the throttle on."""
        from accounts.views import CustomerTopUpIntentView

        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "100"}, format="json")
        req.session = {}
        resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {"enabled": False})
