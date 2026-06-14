"""
B1 — email as a second delivery channel for proactive retention.

Win-back nudges and owner campaigns were PUSH-ONLY, reaching only the small
minority of customers with an active CustomerPushSubscription (push is
unsupported on iOS Safari). B1 adds EMAIL as a second channel, broadening the
audience to every opted-in customer with a Customer.email on file.

Coverage (SimpleTestCase + MagicMock, no real DB):

  Win-back audience (_build_audience):
   1. email-only lapsed customer (email set, NO push sub) is now IN the audience
   2. customer with BOTH push + email is in the audience, in both channel maps
   3. customer with NEITHER email nor push is excluded
   4. notify_promotions=False is excluded

  Win-back send loop (Command.handle):
   5. email-only customer receives an email (push helper NOT called)
   6. customer with both gets BOTH push and email
   7. dedup row is KEPT when only email succeeds (push suppressed)
   8. dedup row is RECLAIMED only when BOTH channels fail/suppress
   9. record_notification is written per channel (channel="push" / "email")

  Marketing email helper (accounts.messaging.send_marketing_email):
  10. calls send_mail and returns its count
  11. body carries an opt-out line naming the tenant

  Campaign dispatch (OwnerCampaignView.post):
  12. a campaign emails its opted-in audience (email enqueue per customer)
  13. an email-only audience (no push subs) still dispatches + is not no_audience
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone as _tz
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from menu.views import OwnerCampaignView


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_tenant(*, tid=1, slug="test", name="Test Restaurant"):
    t = MagicMock()
    t.id = tid
    t.slug = slug
    t.name = name
    t.schema_name = f"tenant_{slug}"
    p = MagicMock()
    p.winback_enabled = True
    p.winback_inactive_weeks = 4
    p.winback_message = ""
    p.timezone = "UTC"
    t.profile = p
    return t


def _make_command():
    from menu.management.commands.send_winback_nudges import Command
    cmd = Command()
    cmd.stdout = io.StringIO()
    cmd.style = MagicMock()
    cmd.style.MIGRATE_HEADING.side_effect = lambda x: x
    cmd.style.SUCCESS.side_effect = lambda x: x
    return cmd


def _ctx_mock(mock_ctx):
    mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
    mock_ctx.return_value.__exit__ = MagicMock(return_value=False)


def _build_audience_with(
    *, opted_in, subscribed, emails, recently_nudged=(), cap=50
):
    """Run the real _build_audience with mocked querysets.

    opted_in      → list of customer_ids returned by the opted-in Customer query
    subscribed    → list of customer_ids with a push subscription
    emails        → list of (id, email) tuples returned by the email Customer query
    recently_nudged → list of customer_ids in the 90-day WinbackNudge set
    """
    from menu.management.commands.send_winback_nudges import _build_audience

    cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
    last_order = cutoff - timedelta(days=1)
    rows = [{"customer_id": cid, "last_order": last_order} for cid in opted_in] or [
        {"customer_id": 1, "last_order": last_order}
    ]

    mock_order_qs = MagicMock()
    mock_order_qs.values.return_value.annotate.return_value.filter.return_value = rows

    mock_customer_qs = MagicMock()
    # opted-in lookup: Customer.objects.filter(...).values_list("id", flat=True)
    mock_customer_qs.filter.return_value.values_list.return_value = list(opted_in)
    # email lookup: Customer.objects.filter(...).exclude(email="").values_list("id","email")
    mock_customer_qs.filter.return_value.exclude.return_value.values_list.return_value = list(emails)

    mock_sub_qs = MagicMock()
    mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = list(subscribed)

    mock_winback_qs = MagicMock()
    mock_winback_qs.filter.return_value.values_list.return_value = list(recently_nudged)

    with patch("menu.models.Order.objects", mock_order_qs), \
         patch("accounts.models.Customer.objects", mock_customer_qs), \
         patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs), \
         patch("accounts.models.WinbackNudge.objects", mock_winback_qs), \
         patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
        _ctx_mock(mock_ctx)
        return _build_audience(tenant_id=1, inactive_weeks=4, cap=cap)


# ─────────────────────────────────────────────────────────────────────────────
# 1–4. Win-back audience broadening
# ─────────────────────────────────────────────────────────────────────────────

class WinbackEmailAudienceTests(SimpleTestCase):

    def test_email_only_customer_is_now_in_audience(self):
        """A lapsed, opted-in customer with an email but NO push sub used to be
        excluded; under B1 they are IN the audience and email-reachable."""
        eligible, email_by_id, subscribed = _build_audience_with(
            opted_in=[99],
            subscribed=[],                       # no push sub
            emails=[(99, "lapsed@example.com")],  # has email
        )
        self.assertIn(99, eligible)
        self.assertEqual(email_by_id.get(99), "lapsed@example.com")
        self.assertNotIn(99, subscribed)

    def test_customer_with_both_channels_in_both_maps(self):
        eligible, email_by_id, subscribed = _build_audience_with(
            opted_in=[7],
            subscribed=[7],
            emails=[(7, "both@example.com")],
        )
        self.assertIn(7, eligible)
        self.assertEqual(email_by_id.get(7), "both@example.com")
        self.assertIn(7, subscribed)

    def test_customer_with_neither_channel_excluded(self):
        eligible, email_by_id, subscribed = _build_audience_with(
            opted_in=[5],
            subscribed=[],   # no push
            emails=[],       # no email
        )
        self.assertEqual(eligible, [])
        self.assertEqual(email_by_id, {})
        self.assertEqual(subscribed, set())

    def test_opted_out_customer_excluded_even_with_email(self):
        """notify_promotions=False → opted-in lookup returns [] → empty audience,
        even if the customer technically has an email."""
        eligible, email_by_id, subscribed = _build_audience_with(
            opted_in=[],                          # opted out → not in opted_in set
            subscribed=[8],
            emails=[(8, "optedout@example.com")],
        )
        self.assertEqual(eligible, [])


# ─────────────────────────────────────────────────────────────────────────────
# 5–9. Win-back send loop — dual channel
# ─────────────────────────────────────────────────────────────────────────────

class WinbackDualSendTests(SimpleTestCase):
    """Drive Command.handle with _build_audience patched to return the channel
    maps, asserting which channel(s) fire and how the dedup row is handled."""

    def _run_handle(
        self, *, audience, email_by_id, subscribed,
        push_return=1, email_return=1,
    ):
        tenant = _make_tenant()
        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        calls = {"push": [], "email": []}

        def fake_push(cid, tname, slug, url, title, body):
            calls["push"].append(cid)
            return push_return

        def fake_email(email, tname, slug, title, body):
            calls["email"].append(email)
            return email_return

        # WinbackNudge reclaim chain (filter → order_by → first → row.delete()).
        mock_winback_qs = MagicMock()
        filter_result = MagicMock()
        order_result = MagicMock()
        row = MagicMock()
        mock_winback_qs.filter.return_value = filter_result
        filter_result.order_by.return_value = order_result
        order_result.first.return_value = row

        recorded = []

        def fake_record(**kw):
            recorded.append(kw)

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience",
                   return_value=(audience, email_by_id, subscribed)), \
             patch("menu.management.commands.send_winback_nudges._record_nudge"), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", side_effect=fake_push), \
             patch("menu.management.commands.send_winback_nudges._send_nudge_email", side_effect=fake_email), \
             patch("accounts.models.WinbackNudge.objects", mock_winback_qs), \
             patch("accounts.notifications.record_notification", side_effect=fake_record):
            mock_cache.add.return_value = True
            _ctx_mock(mock_ctx)
            cmd.handle(dry_run=False)

        return calls, row, recorded

    def test_email_only_customer_receives_email_not_push(self):
        calls, row, recorded = self._run_handle(
            audience=[99], email_by_id={99: "a@b.com"}, subscribed=set(),
        )
        self.assertEqual(calls["email"], ["a@b.com"])
        self.assertEqual(calls["push"], [])          # push helper not called
        row.delete.assert_not_called()               # delivered → row kept
        channels = {r["channel"] for r in recorded}
        self.assertIn("email", channels)
        self.assertNotIn("push", channels)

    def test_customer_with_both_gets_push_and_email(self):
        calls, row, recorded = self._run_handle(
            audience=[7], email_by_id={7: "both@b.com"}, subscribed={7},
        )
        self.assertEqual(calls["push"], [7])
        self.assertEqual(calls["email"], ["both@b.com"])
        row.delete.assert_not_called()
        channels = {r["channel"] for r in recorded}
        self.assertIn("push", channels)
        self.assertIn("email", channels)

    def test_dedup_row_kept_when_only_email_succeeds(self):
        """Push suppressed (returns 0) but email delivered (1) → DELIVERED, row kept."""
        calls, row, recorded = self._run_handle(
            audience=[7], email_by_id={7: "both@b.com"}, subscribed={7},
            push_return=0, email_return=1,
        )
        self.assertEqual(calls["push"], [7])
        self.assertEqual(calls["email"], ["both@b.com"])
        row.delete.assert_not_called()               # email succeeded → row kept
        channels = {r["channel"] for r in recorded}
        self.assertIn("email", channels)
        self.assertNotIn("push", channels)           # push did not deliver

    def test_dedup_row_reclaimed_only_when_both_fail(self):
        """Both channels suppressed/failed → row is reclaimed (deleted)."""
        calls, row, recorded = self._run_handle(
            audience=[7], email_by_id={7: "both@b.com"}, subscribed={7},
            push_return=0, email_return=0,
        )
        self.assertEqual(calls["push"], [7])
        self.assertEqual(calls["email"], ["both@b.com"])
        row.delete.assert_called_once()              # nothing delivered → reclaim
        self.assertEqual(recorded, [])               # no per-channel sent rows


# ─────────────────────────────────────────────────────────────────────────────
# 10–11. Marketing email helper
# ─────────────────────────────────────────────────────────────────────────────

class MarketingEmailHelperTests(SimpleTestCase):

    @patch("accounts.messaging.send_mail", return_value=1)
    def test_calls_send_mail_and_returns_count(self, mock_send):
        from accounts.messaging import send_marketing_email
        sent = send_marketing_email("x@y.com", "Subject", "Body", "Acme")
        self.assertEqual(sent, 1)
        self.assertEqual(mock_send.call_count, 1)
        args, kwargs = mock_send.call_args
        # send_mail(subject, body, None, [email], ...) — positional like send_otp_email
        self.assertEqual(args[0], "Subject")
        self.assertIn("Body", args[1])
        self.assertEqual(args[3], ["x@y.com"])

    @patch("accounts.messaging.send_mail", return_value=1)
    def test_body_has_opt_out_line_naming_tenant(self, mock_send):
        from accounts.messaging import send_marketing_email
        send_marketing_email("x@y.com", "Subj", "Come back!", "Mama's Kitchen")
        body = mock_send.call_args[0][1]
        self.assertIn("opted into promotions", body)
        self.assertIn("Mama's Kitchen", body)
        self.assertIn("Kepoli account", body)

    @patch("accounts.messaging.send_mail", return_value=0)
    def test_returns_zero_when_send_fails(self, mock_send):
        from accounts.messaging import send_marketing_email
        self.assertEqual(send_marketing_email("x@y.com", "S", "B", "Acme"), 0)


# ─────────────────────────────────────────────────────────────────────────────
# send_campaign_email_sync — opt-out + empty-email suppression
# ─────────────────────────────────────────────────────────────────────────────

class CampaignEmailSyncTests(SimpleTestCase):

    def _run(self, *, cust):
        from accounts import push as push_mod
        mock_customer = MagicMock()
        mock_customer.objects.filter.return_value.first.return_value = cust
        with patch("accounts.models.Customer", mock_customer), \
             patch("django_tenants.utils.schema_context") as mock_ctx, \
             patch("accounts.messaging.send_marketing_email", return_value=1) as mock_email, \
             patch("accounts.notifications.record_notification"):
            _ctx_mock(mock_ctx)
            sent = push_mod.send_campaign_email_sync(
                1, "Acme", "Title", "Msg", tenant_id=1
            )
        return sent, mock_email

    def test_opted_in_with_email_sends(self):
        cust = MagicMock(notify_promotions=True, email="c@d.com")
        sent, mock_email = self._run(cust=cust)
        self.assertEqual(sent, 1)
        mock_email.assert_called_once()

    def test_opted_out_suppressed(self):
        cust = MagicMock(notify_promotions=False, email="c@d.com")
        sent, mock_email = self._run(cust=cust)
        self.assertEqual(sent, 0)
        mock_email.assert_not_called()

    def test_no_email_suppressed(self):
        cust = MagicMock(notify_promotions=True, email="")
        sent, mock_email = self._run(cust=cust)
        self.assertEqual(sent, 0)
        mock_email.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 12–13. Campaign dispatch emails the opted-in audience
# ─────────────────────────────────────────────────────────────────────────────

def _owner_user(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_active = True
    u.pk = 42
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    return u


def _campaign_post_request(tenant_id=1):
    factory = APIRequestFactory()
    user = _owner_user(tenant_id)
    req = factory.post(
        "/api/owner/campaigns/",
        {"title": "Flash sale!", "message": "20% off today."},
        format="json",
    )
    force_authenticate(req, user=user)
    req.user = user
    t = MagicMock()
    t.id = tenant_id
    t.slug = "acme"
    t.name = "Acme"
    t.profile = MagicMock(timezone="UTC")
    req.tenant = t
    return req


class CampaignEmailDispatchTests(SimpleTestCase):

    def _post(self, *, push_ids, email_audience):
        mock_cache = MagicMock()
        mock_cache.add.return_value = True
        mock_cache.delete = MagicMock()

        with (
            patch("menu.views._is_tenant_owner", return_value=True),
            patch("menu.views._campaign_day_window", return_value=(MagicMock(), MagicMock())),
            patch("menu.views.Campaign") as mock_campaign,
            patch("menu.views.cache", mock_cache),
            patch.object(OwnerCampaignView, "_audience_ids", return_value=push_ids),
            patch.object(OwnerCampaignView, "_email_audience", return_value=email_audience),
            patch("accounts.push.push_campaign_to_customer") as mock_push,
            patch("accounts.push.email_campaign_to_customer") as mock_email,
            patch("accounts.notifications.record_notification"),
        ):
            mock_campaign.objects.filter.return_value.count.return_value = 0
            created = MagicMock()
            created.id = 1
            created.title = "Flash sale!"
            created.message = "20% off today."
            created.created_by_user_id = 42
            mock_campaign.objects.create.return_value = created

            req = _campaign_post_request()
            resp = OwnerCampaignView.as_view()(req)
            return resp, mock_push, mock_email, mock_campaign

    def test_campaign_emails_opted_in_audience(self):
        """An audience customer with an email gets a campaign email enqueued."""
        resp, mock_push, mock_email, mock_campaign = self._post(
            push_ids=[1, 2],
            email_audience={2: "two@x.com", 3: "three@x.com"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Push enqueued for the two subscribed ids.
        self.assertEqual(mock_push.call_count, 2)
        # Email enqueued for the two email-bearing ids.
        self.assertEqual(mock_email.call_count, 2)
        emailed_ids = {c.args[0] for c in mock_email.call_args_list}
        self.assertEqual(emailed_ids, {2, 3})
        # Count reflects the union (1,2,3) — counted once each.
        _, create_kwargs = mock_campaign.objects.create.call_args
        self.assertEqual(create_kwargs["audience_count"], 3)

    def test_email_only_audience_still_dispatches(self):
        """No push subscribers but email-only customers → still a valid audience
        (not no_audience) and emails are enqueued."""
        resp, mock_push, mock_email, mock_campaign = self._post(
            push_ids=[],
            email_audience={10: "ten@x.com"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mock_push.call_count, 0)
        self.assertEqual(mock_email.call_count, 1)
