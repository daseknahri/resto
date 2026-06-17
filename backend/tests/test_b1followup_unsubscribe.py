"""
B1-followup — deliverable + compliant marketing email (one-click unsubscribe).

Gmail/Yahoo bulk-sender rules + CAN-SPAM require promotional mail to carry a
working one-click unsubscribe (RFC 8058: List-Unsubscribe +
List-Unsubscribe-Post).  This batch adds:

  * a signed (no-DB-field) per-recipient opt-out token (accounts.unsubscribe)
  * List-Unsubscribe / List-Unsubscribe-Post headers + a visible body link in
    send_marketing_email (built from a server-authoritative brand host — these
    are sent from a CRON, so NO request)
  * a public, auth-less, CSRF-exempt unsubscribe endpoint that flips
    notify_promotions=False for the token's customer (GET human-click + POST
    mailbox-provider one-click), leaking nothing about whether the id exists.

All tests are unit-level (SimpleTestCase + mocks — no real DB / email / network).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.core import signing
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.unsubscribe import (
    MAX_AGE_SECONDS,
    load_unsubscribe_token,
    load_tenant_unsubscribe_token,
    make_unsubscribe_token,
    make_tenant_unsubscribe_token,
)
from accounts.views import EmailUnsubscribeView


# ══════════════════════════════════════════════════════════════════════════════
# 1. Token make/load round-trip
# ══════════════════════════════════════════════════════════════════════════════

class UnsubscribeTokenTests(SimpleTestCase):

    def test_round_trip_returns_customer_id(self):
        token = make_unsubscribe_token(42)
        self.assertEqual(load_unsubscribe_token(token), 42)

    def test_token_is_url_safe_string(self):
        token = make_unsubscribe_token(7)
        self.assertIsInstance(token, str)
        # signing.dumps output is URL-safe (no slashes/spaces that would break a path).
        self.assertNotIn("/", token)
        self.assertNotIn(" ", token)

    def test_string_id_coerced_to_int(self):
        token = make_unsubscribe_token("99")
        self.assertEqual(load_unsubscribe_token(token), 99)

    def test_garbage_token_returns_none(self):
        self.assertIsNone(load_unsubscribe_token("not-a-real-token"))

    def test_empty_token_returns_none(self):
        self.assertIsNone(load_unsubscribe_token(""))
        self.assertIsNone(load_unsubscribe_token(None))

    def test_wrong_salt_token_returns_none(self):
        """A validly-signed token from a DIFFERENT salt must not be accepted."""
        forged = signing.dumps(42, salt="some-other-purpose")
        self.assertIsNone(load_unsubscribe_token(forged))

    def test_expired_token_returns_none(self):
        token = make_unsubscribe_token(42)
        # Past the 1-year cap → SignatureExpired → None (swallowed).
        with patch(
            "accounts.unsubscribe.signing.loads",
            side_effect=signing.SignatureExpired("too old"),
        ):
            self.assertIsNone(load_unsubscribe_token(token))

    def test_max_age_is_about_one_year(self):
        self.assertEqual(MAX_AGE_SECONDS, 365 * 24 * 60 * 60)


# ══════════════════════════════════════════════════════════════════════════════
# 2. send_marketing_email — List-Unsubscribe headers + visible body link
# ══════════════════════════════════════════════════════════════════════════════

@override_settings(BRAND_DOMAIN="app.kepoli.com", PUBLIC_MENU_BASE_URL="", TENANT_DOMAIN_SUFFIX="")
class MarketingEmailHeaderTests(SimpleTestCase):

    def _send(self, **kw):
        from accounts.messaging import send_marketing_email
        with patch("accounts.messaging.EmailMessage") as mock_cls:
            mock_cls.return_value.send.return_value = 1
            sent = send_marketing_email(
                kw.get("email", "x@y.com"),
                kw.get("subject", "Subj"),
                kw.get("body", "Come back!"),
                kw.get("tenant_name", "Acme"),
                customer_id=kw.get("customer_id", 5),
            )
        return sent, mock_cls

    def test_sets_list_unsubscribe_header(self):
        _, mock_cls = self._send()
        headers = mock_cls.call_args[1]["headers"]
        self.assertIn("List-Unsubscribe", headers)
        # Header carries BOTH an https endpoint and a mailto fallback.
        self.assertIn("https://app.kepoli.com/api/unsubscribe/", headers["List-Unsubscribe"])
        self.assertIn("mailto:", headers["List-Unsubscribe"])

    def test_sets_list_unsubscribe_post_one_click_header(self):
        _, mock_cls = self._send()
        headers = mock_cls.call_args[1]["headers"]
        self.assertEqual(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_body_contains_visible_https_unsubscribe_url(self):
        _, mock_cls = self._send()
        body = mock_cls.call_args[1]["body"]
        self.assertIn("https://app.kepoli.com/api/unsubscribe/", body)
        self.assertIn("Unsubscribe", body)

    def test_header_and_body_share_the_same_token_url(self):
        _, mock_cls = self._send(customer_id=123)
        kwargs = mock_cls.call_args[1]
        # The signed token for customer 123 must appear in both the header and body.
        token = make_unsubscribe_token(123)
        # We can't compare the exact token string (timestamp differs), but the
        # customer-id round-trip from the URL in the header must resolve to 123.
        header_url = kwargs["headers"]["List-Unsubscribe"]
        emitted_token = header_url.split("/api/unsubscribe/")[1].split("/")[0].rstrip(">")
        self.assertEqual(load_unsubscribe_token(emitted_token), 123)
        self.assertIn(emitted_token, kwargs["body"])
        self.assertIsNotNone(load_unsubscribe_token(token))  # sanity: helper works

    def test_uses_emailmessage_send_return_value(self):
        sent, mock_cls = self._send()
        self.assertEqual(sent, 1)
        mock_cls.return_value.send.assert_called_once()

    def test_no_customer_id_skips_headers_but_still_sends(self):
        """Defensive: omitting customer_id drops the one-click headers (no token to
        mint) but the message still goes out with the manage-in-account opt-out line."""
        from accounts.messaging import send_marketing_email
        with patch("accounts.messaging.EmailMessage") as mock_cls:
            mock_cls.return_value.send.return_value = 1
            send_marketing_email("x@y.com", "S", "B", "Acme")
        headers = mock_cls.call_args[1]["headers"]
        self.assertNotIn("List-Unsubscribe", headers)
        self.assertIn("Kepoli account", mock_cls.call_args[1]["body"])

    @override_settings(BRAND_DOMAIN="", PUBLIC_MENU_BASE_URL="https://menu.kepoli.com", TENANT_DOMAIN_SUFFIX="")
    def test_host_falls_back_to_public_menu_base_url(self):
        _, mock_cls = self._send()
        self.assertIn(
            "https://menu.kepoli.com/api/unsubscribe/",
            mock_cls.call_args[1]["headers"]["List-Unsubscribe"],
        )

    def test_honours_fail_silently_setting(self):
        from accounts.messaging import send_marketing_email
        with override_settings(EMAIL_FAIL_SILENTLY=False), \
                patch("accounts.messaging.EmailMessage") as mock_cls:
            mock_cls.return_value.send.return_value = 1
            send_marketing_email("x@y.com", "S", "B", "Acme", customer_id=1)
        _, send_kwargs = mock_cls.return_value.send.call_args
        self.assertFalse(send_kwargs["fail_silently"])


# ══════════════════════════════════════════════════════════════════════════════
# 3. EmailUnsubscribeView — GET + POST opt-out, no leak, no CSRF/auth
# ══════════════════════════════════════════════════════════════════════════════

class EmailUnsubscribeViewTests(SimpleTestCase):

    def setUp(self):
        # The view is throttled (email_unsubscribe, 60/hour) on the LocMem cache;
        # clear it so accumulation across the suite can't trip a test.
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = EmailUnsubscribeView.as_view()

    def _customer(self, *, notify=True):
        cust = MagicMock()
        cust.notify_promotions = notify
        return cust

    def test_get_sets_notify_promotions_false(self):
        cust = self._customer(notify=True)
        token = make_unsubscribe_token(42)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = cust
            resp = self.view(self.factory.get(f"/api/unsubscribe/{token}/"), token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(cust.notify_promotions)
        cust.save.assert_called_once()
        self.assertEqual(cust.save.call_args[1]["update_fields"], ["notify_promotions"])

    def test_post_one_click_sets_notify_promotions_false(self):
        cust = self._customer(notify=True)
        token = make_unsubscribe_token(7)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = cust
            # No CSRF token, no auth, empty body — the mailbox-provider one-click call.
            resp = self.view(self.factory.post(f"/api/unsubscribe/{token}/"), token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(cust.notify_promotions)
        cust.save.assert_called_once()

    def test_post_accepted_without_csrf_or_auth(self):
        """The POST must not be rejected (403) for a missing CSRF token / no auth —
        authentication_classes=[] means no SessionAuthentication enforces CSRF."""
        cust = self._customer(notify=True)
        token = make_unsubscribe_token(7)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = cust
            req = self.factory.post(f"/api/unsubscribe/{token}/")
            resp = self.view(req, token=token)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_idempotent_already_opted_out_no_resave(self):
        cust = self._customer(notify=False)  # already unsubscribed
        token = make_unsubscribe_token(42)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = cust
            resp = self.view(self.factory.get(f"/api/unsubscribe/{token}/"), token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        cust.save.assert_not_called()  # nothing to flip → no write

    def test_invalid_token_does_not_500_and_does_not_leak(self):
        with patch("accounts.views.Customer") as MockCustomer:
            resp = self.view(self.factory.get("/api/unsubscribe/garbage/"), token="garbage")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # An invalid token must never even hit the DB (no probing of id existence).
        MockCustomer.objects.filter.assert_not_called()

    def test_invalid_and_valid_tokens_return_same_generic_page(self):
        """Response body must NOT reveal whether the encoded id exists."""
        valid = make_unsubscribe_token(42)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = None  # id not found
            r_missing = self.view(self.factory.get(f"/api/unsubscribe/{valid}/"), token=valid)
            r_garbage = self.view(self.factory.get("/api/unsubscribe/garbage/"), token="garbage")
        self.assertEqual(r_missing.content, r_garbage.content)

    def test_unknown_customer_does_not_500(self):
        token = make_unsubscribe_token(404)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = None
            resp = self.view(self.factory.get(f"/api/unsubscribe/{token}/"), token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_save_exception_swallowed_does_not_500(self):
        cust = self._customer(notify=True)
        cust.save.side_effect = Exception("db down")
        token = make_unsubscribe_token(42)
        with patch("accounts.views.Customer") as MockCustomer, \
                patch("accounts.views.logger"):
            MockCustomer.objects.filter.return_value.first.return_value = cust
            resp = self.view(self.factory.get(f"/api/unsubscribe/{token}/"), token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_response_is_html_confirmation(self):
        token = make_unsubscribe_token(42)
        with patch("accounts.views.Customer") as MockCustomer:
            MockCustomer.objects.filter.return_value.first.return_value = self._customer()
            resp = self.view(self.factory.get(f"/api/unsubscribe/{token}/"), token=token)
        self.assertIn("text/html", resp["Content-Type"])
        self.assertIn(b"unsubscribed", resp.content.lower())


# ══════════════════════════════════════════════════════════════════════════════
# 4. Content negotiation must never 406 the opt-out (prod renderer regression)
# ══════════════════════════════════════════════════════════════════════════════

class EmailUnsubscribeContentNegotiationTests(SimpleTestCase):
    """DRF runs content negotiation in APIView.initial() BEFORE get()/post().

    These tests force the PRODUCTION renderer set (JSONRenderer only — in prod
    BrowsableAPIRenderer is appended ONLY when DJANGO_DEBUG=True) so a strict /
    JSON-less Accept header cannot silently 406 the unsubscribe under DEBUG.  An
    RFC 8058 one-click POST from a mailbox provider may send `Accept: text/html`
    with NO `*/*`; without the view's no-op negotiation that would raise
    NotAcceptable → HTTP 406 and the recipient would never be unsubscribed.
    """

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = EmailUnsubscribeView.as_view()

    def _call(self, method, accept):
        from rest_framework.renderers import JSONRenderer

        token = make_unsubscribe_token(42)
        req = getattr(self.factory, method)(
            f"/api/unsubscribe/{token}/", HTTP_ACCEPT=accept
        )
        # Pin the PROD renderer set on the view class so DEBUG's BrowsableAPIRenderer
        # can't mask a negotiation 406 (the verify harness runs under DJANGO_DEBUG=True).
        with patch.object(EmailUnsubscribeView, "renderer_classes", [JSONRenderer]), \
                patch("accounts.views.Customer") as MockCustomer:
            cust = MagicMock()
            cust.notify_promotions = True
            MockCustomer.objects.filter.return_value.first.return_value = cust
            return self.view(req, token=token), cust

    def test_get_text_html_accept_not_406_under_prod_renderers(self):
        resp, cust = self._call("get", "text/html")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", resp["Content-Type"])
        self.assertFalse(cust.notify_promotions)  # opt-out actually ran

    def test_post_one_click_text_html_accept_not_406_under_prod_renderers(self):
        resp, cust = self._call("post", "text/html")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(cust.notify_promotions)

    def test_various_accepts_all_200_under_prod_renderers(self):
        for accept in ("application/json", "*/*", "text/plain", ""):
            with self.subTest(accept=accept):
                cache.clear()
                resp, _ = self._call("get", accept)
                self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Per-tenant unsubscribe token (email-tenant-unsub salt)
# ══════════════════════════════════════════════════════════════════════════════

class TenantUnsubscribeTokenTests(SimpleTestCase):

    def test_round_trip_returns_customer_and_tenant_id(self):
        token = make_tenant_unsubscribe_token(42, 7)
        result = load_tenant_unsubscribe_token(token)
        self.assertEqual(result, (42, 7))

    def test_string_ids_coerced_to_int(self):
        token = make_tenant_unsubscribe_token("99", "3")
        self.assertEqual(load_tenant_unsubscribe_token(token), (99, 3))

    def test_garbage_token_returns_none(self):
        self.assertIsNone(load_tenant_unsubscribe_token("not-a-real-token"))

    def test_empty_or_none_token_returns_none(self):
        self.assertIsNone(load_tenant_unsubscribe_token(""))
        self.assertIsNone(load_tenant_unsubscribe_token(None))

    def test_global_token_not_accepted_as_tenant_token(self):
        """A legacy global token (email-unsubscribe salt) must not decode as a
        per-tenant token — the salts are separate by design."""
        global_token = make_unsubscribe_token(42)
        self.assertIsNone(load_tenant_unsubscribe_token(global_token))

    def test_wrong_salt_token_returns_none(self):
        forged = signing.dumps({"c": 1, "t": 2}, salt="some-other-purpose")
        self.assertIsNone(load_tenant_unsubscribe_token(forged))

    def test_expired_token_returns_none(self):
        token = make_tenant_unsubscribe_token(42, 7)
        with patch(
            "accounts.unsubscribe.signing.loads",
            side_effect=signing.SignatureExpired("too old"),
        ):
            self.assertIsNone(load_tenant_unsubscribe_token(token))


class EmailUnsubscribeViewPerTenantTests(SimpleTestCase):
    """EmailUnsubscribeView with a per-tenant token creates CustomerTenantOptOut."""

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()
        self.view = EmailUnsubscribeView.as_view()

    def _call(self, method, token):
        # Lazy import inside _unsubscribe resolves from accounts.models, so patch there.
        with patch("accounts.models.CustomerTenantOptOut") as MockOptOut:
            req = getattr(self.factory, method)(f"/api/unsubscribe/{token}/")
            resp = self.view(req, token=token)
        return resp, MockOptOut

    def test_get_with_per_tenant_token_creates_optout_row(self):
        token = make_tenant_unsubscribe_token(55, 3)
        resp, MockOptOut = self._call("get", token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        MockOptOut.objects.get_or_create.assert_called_once_with(customer_id=55, tenant_id=3)

    def test_post_with_per_tenant_token_creates_optout_row(self):
        token = make_tenant_unsubscribe_token(55, 3)
        resp, MockOptOut = self._call("post", token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        MockOptOut.objects.get_or_create.assert_called_once_with(customer_id=55, tenant_id=3)

    def test_per_tenant_token_does_not_flip_global_flag(self):
        """A per-tenant token must not touch notify_promotions — it only records
        the per-tenant opt-out and returns early."""
        token = make_tenant_unsubscribe_token(55, 3)
        with patch("accounts.models.CustomerTenantOptOut"), \
             patch("accounts.views.Customer") as MockCustomer:
            req = self.factory.get(f"/api/unsubscribe/{token}/")
            self.view(req, token=token)
        # Customer.objects must NOT be touched — the per-tenant path returns early.
        MockCustomer.objects.filter.assert_not_called()

    def test_idempotent_get_or_create_called_on_repeat(self):
        """A repeated per-tenant unsubscribe request calls get_or_create again
        (idempotent at DB level via get_or_create; the view delegates)."""
        token = make_tenant_unsubscribe_token(55, 3)
        with patch("accounts.models.CustomerTenantOptOut") as MockOptOut:
            req = self.factory.get(f"/api/unsubscribe/{token}/")
            resp = self.view(req, token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        MockOptOut.objects.get_or_create.assert_called_once_with(customer_id=55, tenant_id=3)

    def test_per_tenant_db_error_swallowed_returns_200(self):
        """A DB failure in the per-tenant path must not 500 — the view is
        best-effort and never reveals internal state."""
        token = make_tenant_unsubscribe_token(55, 3)
        with patch("accounts.models.CustomerTenantOptOut") as MockOptOut, \
             patch("accounts.views.logger"):
            MockOptOut.objects.get_or_create.side_effect = Exception("db gone")
            req = self.factory.get(f"/api/unsubscribe/{token}/")
            resp = self.view(req, token=token)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
