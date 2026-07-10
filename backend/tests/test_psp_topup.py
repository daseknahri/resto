"""A3: PSP top-up seam — unit tests.

All tests run without a database (SimpleTestCase) and without stripe installed,
which mirrors production state before PSP_TOPUP_ENABLED=1 is set.

Covered invariants:
  • Intent endpoint returns {"enabled": False} when flag is off.
  • Intent endpoint returns 401 when flag is on but no session.
  • Webhook endpoint returns {"ok": False} when flag is off (no side-effects).
  • Webhook handler credits the wallet idempotently on a valid event.
  • Webhook handler rejects events with missing metadata.
  • Idempotency key is namespaced as "stripe:<event_id>" (never a raw DB id).
"""

import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory


_PSP_ON = dict(
    PSP_TOPUP_ENABLED=True,
    PSP_STRIPE_SECRET_KEY="sk_test_dummy",
    PSP_STRIPE_WEBHOOK_SECRET="",
    PSP_SITE_URL="https://example.com",
)

_PSP_OFF = dict(
    PSP_TOPUP_ENABLED=False,
    PSP_STRIPE_SECRET_KEY="",
    PSP_STRIPE_WEBHOOK_SECRET="",
    PSP_SITE_URL="",
)


# ── Intent view ───────────────────────────────────────────────────────────────

class IntentDisabledTests(SimpleTestCase):
    """Intent endpoint returns {enabled: False} when the feature flag is off."""

    @override_settings(**_PSP_OFF)
    def test_returns_disabled(self):
        from accounts.views import CustomerTopUpIntentView
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "100"}, format="json")
        req.session = {}
        resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {"enabled": False})


class IntentUnauthenticatedTests(SimpleTestCase):
    """Intent endpoint returns 401 when flag is on but no customer session."""

    @override_settings(**_PSP_ON)
    def test_returns_401_without_session(self):
        from accounts.views import CustomerTopUpIntentView
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "100"}, format="json")
        req.session = {}  # no customer_id
        resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    @override_settings(**_PSP_ON)
    def test_returns_400_for_invalid_amount(self):
        from accounts.views import CustomerTopUpIntentView
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "abc"}, format="json")
        req.session = {"customer_id": 1}
        mock_customer = MagicMock()
        mock_customer.pk = 1
        with patch("accounts.views.Customer.objects.get", return_value=mock_customer):
            resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 400)

    @override_settings(**_PSP_ON)
    def test_returns_400_for_out_of_range_amount(self):
        from accounts.views import CustomerTopUpIntentView
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/intent/", {"amount": "5"}, format="json")
        req.session = {"customer_id": 1}
        mock_customer = MagicMock()
        mock_customer.pk = 1
        with patch("accounts.views.Customer.objects.get", return_value=mock_customer):
            resp = CustomerTopUpIntentView.as_view()(req)
        self.assertEqual(resp.status_code, 400)


# ── Webhook view ──────────────────────────────────────────────────────────────

class WebhookDisabledTests(SimpleTestCase):
    """Webhook endpoint is a safe no-op when the feature flag is off."""

    @override_settings(**_PSP_OFF)
    def test_returns_disabled(self):
        from accounts.views import CustomerTopUpWebhookView
        factory = APIRequestFactory()
        payload = json.dumps({"type": "checkout.session.completed"}).encode()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")
        resp = CustomerTopUpWebhookView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data.get("ok"))


class WebhookEventHandlingTests(SimpleTestCase):
    """Webhook credits wallet on checkout.session.completed; idempotency key is schema-namespaced."""

    def _make_stripe_event(self, event_id="evt_test123", customer_id="42",
                           amount_total=15000, meta_amount="150.00"):
        return {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_abc",
                    "payment_status": "paid",
                    "amount_total": amount_total,   # settled amount, minor units (cents)
                    "metadata": {"customer_id": customer_id, "amount": meta_amount},
                }
            },
        }

    @override_settings(**_PSP_ON)
    def test_credits_wallet_on_completed_event(self):
        from accounts.views import CustomerTopUpWebhookView
        event = self._make_stripe_event()
        payload = json.dumps(event).encode()

        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")

        mock_tx = MagicMock()
        with patch("accounts.views.CustomerTopUpWebhookView.__module__"):
            pass
        # Patch credit_wallet inside the wallet_service import used by the view.
        with patch("accounts.wallet_service.credit_wallet") as mock_credit:
            mock_credit.return_value = mock_tx
            # Also patch the stripe import to succeed (stripe may not be installed in test env)
            mock_stripe = MagicMock()
            mock_stripe.api_key = ""
            mock_stripe.error.SignatureVerificationError = Exception
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                resp = CustomerTopUpWebhookView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("ok"))
        mock_credit.assert_called_once()
        call_kwargs = mock_credit.call_args.kwargs
        # Idempotency key must be namespaced with stripe: prefix (security invariant).
        self.assertEqual(call_kwargs["idempotency_key"], "stripe:evt_test123")
        self.assertEqual(call_kwargs["customer_id"], "42")
        # Amount is the SETTLED amount_total (15000 cents → 150.00), not metadata.
        self.assertEqual(str(call_kwargs["amount"]), "150.00")

    @override_settings(**_PSP_ON)
    def test_credits_settled_amount_total_over_metadata(self):
        """MONEY-3: the settled amount_total wins over the client-echoed metadata amount."""
        from accounts.views import CustomerTopUpWebhookView
        event = self._make_stripe_event(amount_total=5000, meta_amount="999.00")
        payload = json.dumps(event).encode()
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")
        with patch("accounts.wallet_service.credit_wallet") as mock_credit:
            mock_credit.return_value = MagicMock()
            mock_stripe = MagicMock()
            mock_stripe.api_key = ""
            mock_stripe.error.SignatureVerificationError = Exception
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                resp = CustomerTopUpWebhookView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(mock_credit.call_args.kwargs["amount"]), "50.00")  # 5000 cents

    @override_settings(**_PSP_ON)
    def test_unpaid_session_does_not_credit(self):
        """A session that didn't clear (payment_status != paid) must not credit."""
        from accounts.views import CustomerTopUpWebhookView
        event = self._make_stripe_event()
        event["data"]["object"]["payment_status"] = "unpaid"
        payload = json.dumps(event).encode()
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")
        with patch("accounts.wallet_service.credit_wallet") as mock_credit:
            mock_stripe = MagicMock()
            mock_stripe.api_key = ""
            mock_stripe.error.SignatureVerificationError = Exception
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                resp = CustomerTopUpWebhookView.as_view()(req)
        self.assertTrue(resp.data.get("ok"))
        mock_credit.assert_not_called()

    @override_settings(**_PSP_ON)
    def test_ignores_non_completed_event(self):
        from accounts.views import CustomerTopUpWebhookView
        payload = json.dumps({"id": "evt_xyz", "type": "payment_intent.created", "data": {}}).encode()
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")

        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.error.SignatureVerificationError = Exception
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            with patch("accounts.wallet_service.credit_wallet") as mock_credit:
                resp = CustomerTopUpWebhookView.as_view()(req)

        self.assertTrue(resp.data.get("ok"))
        mock_credit.assert_not_called()

    @override_settings(**_PSP_ON)
    def test_returns_400_for_missing_metadata(self):
        from accounts.views import CustomerTopUpWebhookView
        event = {
            "id": "evt_bad",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_bad", "metadata": {}}},
        }
        payload = json.dumps(event).encode()
        factory = APIRequestFactory()
        req = factory.post("/api/customer/topup/webhook/", data=payload, content_type="application/json")

        mock_stripe = MagicMock()
        mock_stripe.api_key = ""
        mock_stripe.error.SignatureVerificationError = Exception
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            resp = CustomerTopUpWebhookView.as_view()(req)

        self.assertEqual(resp.status_code, 400)
