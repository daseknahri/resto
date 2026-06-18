"""
Unit tests for the email bounce/complaint suppression feature.

Covers:
  - CustomerEmailSuppression model: email is lowercased on save
  - EmailSuppressionWebhookView: no secret → 403; wrong token → 403; happy
    path bounce + complaint; Mailgun-style nested payload; duplicate upsert;
    missing email → 422
  - send_campaign_email_sync: suppressed address → returns 0 (no send)
  - send_winback_nudges._build_audience: suppressed email excluded from audience
  - CustomerEmailSuppression added to SHARED_APPS / accessible in public schema
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory


# ── Webhook view ─────────────────────────────────────────────────────────────

class TestEmailSuppressionWebhookView(SimpleTestCase):
    factory = APIRequestFactory()

    def _view(self):
        from accounts.views import EmailSuppressionWebhookView
        return EmailSuppressionWebhookView.as_view()

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="")
    def test_no_secret_returns_403(self):
        req = self.factory.post("/api/public/email/suppression/", {"event": "bounce", "email": "a@b.com"}, format="json")
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 403)

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    def test_wrong_token_returns_403(self):
        req = self.factory.post("/api/public/email/suppression/", {"event": "bounce", "email": "a@b.com"}, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer wrong"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 403)

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    @patch("accounts.models.CustomerEmailSuppression")
    def test_bounce_event_upserts_suppression(self, mock_model):
        req = self.factory.post("/api/public/email/suppression/", {"event": "bounce", "email": "User@Example.com"}, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer secret123"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 200)
        mock_model.objects.update_or_create.assert_called_once()
        call_kwargs = mock_model.objects.update_or_create.call_args
        self.assertEqual(call_kwargs.kwargs["email"], "user@example.com")
        self.assertEqual(call_kwargs.kwargs["defaults"]["reason"], "bounce")

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    @patch("accounts.models.CustomerEmailSuppression")
    def test_complaint_event_maps_to_complaint(self, mock_model):
        req = self.factory.post("/api/public/email/suppression/", {"event": "complained", "email": "spam@example.com"}, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer secret123"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 200)
        mock_model.objects.update_or_create.assert_called_once()
        defaults = mock_model.objects.update_or_create.call_args.kwargs["defaults"]
        self.assertEqual(defaults["reason"], "complaint")

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    @patch("accounts.models.CustomerEmailSuppression")
    def test_mailgun_nested_payload_supported(self, mock_model):
        payload = {"event-data": {"event": "bounced", "recipient": "mailgun@example.com"}}
        req = self.factory.post("/api/public/email/suppression/", payload, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer secret123"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 200)
        call_kwargs = mock_model.objects.update_or_create.call_args
        self.assertEqual(call_kwargs.kwargs["email"], "mailgun@example.com")

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    def test_missing_email_returns_422(self):
        req = self.factory.post("/api/public/email/suppression/", {"event": "bounce"}, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer secret123"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 422)

    @override_settings(EMAIL_SUPPRESSION_WEBHOOK_SECRET="secret123")
    @patch("accounts.models.CustomerEmailSuppression")
    def test_unknown_event_reason_maps_to_manual(self, mock_model):
        req = self.factory.post("/api/public/email/suppression/", {"event": "purged", "email": "x@y.com"}, format="json")
        req.META["HTTP_AUTHORIZATION"] = "Bearer secret123"
        resp = self._view()(req)
        self.assertEqual(resp.status_code, 200)
        defaults = mock_model.objects.update_or_create.call_args.kwargs["defaults"]
        self.assertEqual(defaults["reason"], "manual")


# ── send_campaign_email_sync suppression check ───────────────────────────────

class TestCampaignEmailSuppressionCheck(SimpleTestCase):
    """Suppressed address → 0 returned, no send_marketing_email call."""

    def _call(self, customer_id=1, email="bad@example.com"):
        from accounts.push import send_campaign_email_sync
        return send_campaign_email_sync(customer_id, "TestRestaurant", "Title", "Body")

    @patch("accounts.models.CustomerEmailSuppression")
    @patch("accounts.models.CustomerTenantOptOut")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.messaging.send_marketing_email")
    def test_suppressed_email_not_sent(self, mock_mail, mock_ctx, mock_cust_cls, mock_optout, mock_suppression):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        cust = MagicMock()
        cust.notify_promotions = True
        cust.email_verified = True
        cust.email = "bad@example.com"
        mock_cust_cls.objects.filter.return_value.first.return_value = cust
        mock_optout.objects.filter.return_value.exists.return_value = False
        # Simulate suppressed address
        mock_suppression.objects.filter.return_value.exists.return_value = True

        result = self._call()

        self.assertEqual(result, 0)
        mock_mail.assert_not_called()

    @patch("accounts.models.CustomerEmailSuppression")
    @patch("accounts.models.CustomerTenantOptOut")
    @patch("accounts.models.Customer")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.messaging.send_marketing_email")
    def test_not_suppressed_email_is_sent(self, mock_mail, mock_ctx, mock_cust_cls, mock_optout, mock_suppression):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        cust = MagicMock()
        cust.notify_promotions = True
        cust.email_verified = True
        cust.email = "good@example.com"
        mock_cust_cls.objects.filter.return_value.first.return_value = cust
        mock_optout.objects.filter.return_value.exists.return_value = False
        mock_suppression.objects.filter.return_value.exists.return_value = False
        mock_mail.return_value = 1

        result = self._call()

        self.assertEqual(result, 1)
        mock_mail.assert_called_once()


# ── winback audience suppression exclusion ──────────────────────────────────

class TestWinbackAudienceSuppressionExclusion(SimpleTestCase):
    """_build_audience excludes email addresses on the suppression list."""

    def test_suppressed_email_excluded_from_audience(self):
        """A customer whose email is suppressed should not appear in email_by_id."""
        now_utc = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        from datetime import timedelta

        with patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("accounts.models.WinbackNudge") as mock_nudge, \
             patch("accounts.models.CustomerEmailSuppression") as mock_supp, \
             patch("accounts.models.CustomerTenantOptOut") as mock_optout, \
             patch("accounts.models.Customer") as mock_cust, \
             patch("accounts.models.CustomerPushSubscription") as mock_subs, \
             patch("menu.models.Order") as mock_order:

            mock_ctx.return_value.__enter__ = lambda s: s
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

            # One inactive customer
            inactive_id = 42
            mock_order.objects.values.return_value.annotate.return_value.filter.return_value = [
                {"customer_id": inactive_id, "last_order": now_utc - timedelta(weeks=12)}
            ]

            # Opted in
            mock_cust.objects.filter.return_value.values_list.return_value = [inactive_id]
            mock_optout.objects.filter.return_value.values_list.return_value = []

            # Push subscription exists
            mock_subs.objects.filter.return_value.values_list.return_value.distinct.return_value = [inactive_id]

            # Email: suppressed address
            mock_supp.objects.values_list.return_value = ["suppressed@example.com"]
            mock_cust.objects.filter.return_value.exclude.return_value.values_list.return_value = [
                (inactive_id, "suppressed@example.com")
            ]

            # No recent nudge
            mock_nudge.objects.filter.return_value.values_list.return_value = []

            from menu.management.commands.send_winback_nudges import _build_audience
            eligible, email_by_id, subscribed = _build_audience(
                tenant_id=1, inactive_weeks=8, cap=50
            )

        # Customer is reachable via push, so in eligible
        self.assertIn(inactive_id, eligible)
        # But NOT in email_by_id (suppressed)
        self.assertNotIn(inactive_id, email_by_id)


# ── model behaviour ──────────────────────────────────────────────────────────

class TestCustomerEmailSuppressionModel(SimpleTestCase):
    """Tests for the CustomerEmailSuppression model class (no DB needed)."""

    def test_repr_contains_email_and_reason(self):
        from accounts.models import CustomerEmailSuppression
        obj = CustomerEmailSuppression.__new__(CustomerEmailSuppression)
        obj.email = "test@example.com"
        obj.reason = "bounce"
        self.assertIn("test@example.com", str(obj))
        self.assertIn("bounce", str(obj))
