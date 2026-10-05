"""Regression tests for the activation-token hardening.

  1. MFA bypass — ActivationView logged the user in directly, past a confirmed
     TOTP device (the MFA gate lives only in LoginView).
  2. Re-activation of an established account — "already activated" was decided
     by the existence of a USED ActivationToken row, which prune_auth_tokens
     deletes after 30 days (and invited staff never had) → the public resend
     endpoint mailed a fresh, password-setting token for any account.
  3. Sibling tokens not revoked — ActivationToken.issue left older links valid.
  4. Non-atomic consume — validate-then-mark_used (two concurrent requests both
     set the password) and is_active=True forced (revived deactivated accounts).
  + per-email cap on the public resend (the per-IP throttle is rotatable).

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from accounts.serializers import (
    ACTIVATION_ACCOUNT_DISABLED,
    ACTIVATION_ALREADY_DONE,
    ACTIVATION_TOKEN_EXPIRED_OR_USED,
    ActivationSerializer,
)
from accounts.views import ActivationView
from sales.models import ActivationToken, account_is_activated
from sales.services import (
    ACTIVATION_RESEND_PER_EMAIL_LIMIT,
    _activation_resend_cache_key,
    activation_resend_allowed,
    resend_activation_for_email,
)

STRONG_PASSWORD = "Zx9kLmop-42qR"


@contextmanager
def _noop_ctx(*args, **kwargs):
    yield


def _account(*, last_login=None, is_active=True):
    user = MagicMock()
    user.last_login = last_login
    user.is_active = is_active
    return user


def _activation(user, *, is_valid=True):
    activation = MagicMock()
    activation.user = user
    activation.user_id = 9
    activation.is_valid.return_value = is_valid
    return activation


def _patch_token_lookup(test, activation):
    patcher = patch("accounts.serializers.ActivationToken")
    token_cls = patcher.start()
    test.addCleanup(patcher.stop)
    token_cls.DoesNotExist = Exception
    token_cls.objects.select_related.return_value.get.return_value = activation
    return token_cls


def _patch_totp(test, *, confirmed):
    """Patch the TOTP model the REAL account_is_activated/user_has_confirmed_mfa query."""
    patcher = patch("accounts.models.UserTOTPDevice")
    device_cls = patcher.start()
    test.addCleanup(patcher.stop)
    device_cls.objects.filter.return_value.exists.return_value = confirmed
    return device_cls


# ── The "already activated" predicate (account state, not token rows) ─────────

class AccountIsActivatedTests(SimpleTestCase):
    def test_signed_in_before_is_activated_without_querying_mfa(self):
        device_cls = _patch_totp(self, confirmed=False)
        self.assertTrue(account_is_activated(_account(last_login=timezone.now())))
        device_cls.objects.filter.assert_not_called()

    def test_confirmed_mfa_device_is_activated(self):
        device_cls = _patch_totp(self, confirmed=True)
        user = _account(last_login=None)
        self.assertTrue(account_is_activated(user))
        device_cls.objects.filter.assert_called_once_with(user=user, confirmed=True)

    def test_freshly_provisioned_owner_is_not_activated(self):
        # Provisioning sets a random (usable) password and never logs in:
        # the genuinely never-activated owner must stay activatable.
        _patch_totp(self, confirmed=False)
        self.assertFalse(account_is_activated(_account(last_login=None)))


# ── 1. MFA bypass ─────────────────────────────────────────────────────────────

class ActivationViewMfaTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ActivationView.as_view()
        patcher = patch.object(ActivationView, "throttle_classes", [])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, user, *, has_mfa):
        request = self.factory.post("/api/activate/", {"token": "t", "password": STRONG_PASSWORD}, format="json")
        request.user = MagicMock(is_authenticated=False)
        with patch("accounts.views.ActivationSerializer") as serializer_cls, \
                patch("accounts.views.user_has_confirmed_mfa", return_value=has_mfa), \
                patch("accounts.views.login") as login_mock, \
                patch("accounts.views.serialize_user_session", return_value={"id": 1}):
            serializer_cls.return_value.save.return_value = user
            response = self.view(request)
        return response, login_mock

    def test_confirmed_mfa_device_is_never_logged_in_by_activation(self):
        response, login_mock = self._post(_account(), has_mfa=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        login_mock.assert_not_called()
        self.assertTrue(response.data["login_required"])
        self.assertIsNone(response.data["user"])

    def test_without_mfa_activation_still_logs_in(self):
        response, login_mock = self._post(_account(), has_mfa=False)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        login_mock.assert_called_once()
        self.assertEqual(response.data["user"], {"id": 1})


class ActivationSerializerMfaTests(SimpleTestCase):
    def test_account_with_confirmed_mfa_is_rejected(self):
        _patch_totp(self, confirmed=True)
        activation = _activation(_account(last_login=None))
        _patch_token_lookup(self, activation)
        with self.assertRaises(ValidationError) as cm:
            ActivationSerializer().validate({"token": "t", "password": STRONG_PASSWORD})
        self.assertIn(ACTIVATION_ALREADY_DONE, str(cm.exception))


# ── 2. Re-activation of an established account ────────────────────────────────

class ActivationSerializerAlreadyActivatedTests(SimpleTestCase):
    def setUp(self):
        _patch_totp(self, confirmed=False)

    def test_signed_in_account_with_valid_token_is_rejected(self):
        # A token freshly obtained via resend (e.g. after the used one was
        # pruned) must not become an MFA-less password reset.
        activation = _activation(_account(last_login=timezone.now()), is_valid=True)
        _patch_token_lookup(self, activation)
        with self.assertRaises(ValidationError) as cm:
            ActivationSerializer().validate({"token": "t", "password": STRONG_PASSWORD})
        self.assertIn(ACTIVATION_ALREADY_DONE, str(cm.exception))

    def test_already_activated_wins_over_token_expired_message(self):
        # The owner re-clicking their old link is told to sign in, not offered a resend.
        activation = _activation(_account(last_login=timezone.now()), is_valid=False)
        _patch_token_lookup(self, activation)
        with self.assertRaises(ValidationError) as cm:
            ActivationSerializer().validate({"token": "t", "password": STRONG_PASSWORD})
        self.assertIn(ACTIVATION_ALREADY_DONE, str(cm.exception))
        self.assertNotIn(ACTIVATION_TOKEN_EXPIRED_OR_USED, str(cm.exception))

    def test_never_activated_account_with_valid_token_passes(self):
        activation = _activation(_account(last_login=None), is_valid=True)
        _patch_token_lookup(self, activation)
        attrs = ActivationSerializer().validate({"token": "t", "password": STRONG_PASSWORD})
        self.assertIs(attrs["activation"], activation)


class ResendAfterPruneTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _user_model(self, user):
        User = MagicMock()
        qs = MagicMock()
        qs.select_related.return_value = qs
        qs.order_by.return_value = qs
        qs.first.return_value = user
        User.objects.filter.return_value = qs
        return User

    @patch("sales.services.issue_activation")
    @patch("sales.services.get_user_model")
    @patch("django_tenants.utils.schema_context", _noop_ctx)
    @patch("django.db.transaction.atomic", _noop_ctx)
    def test_signed_in_owner_with_pruned_tokens_gets_nothing(self, get_user_model_mock, issue_activation_mock):
        # No ActivationToken rows at all (pruned after 30 days) — the old
        # token-row predicate called this "not activated" and re-issued.
        user = SimpleNamespace(id=11, email="owner@example.com", last_login=timezone.now(),
                               tenant=SimpleNamespace(id=7, slug="demo"))
        get_user_model_mock.return_value = self._user_model(user)

        self.assertIsNone(resend_activation_for_email("owner@example.com"))
        issue_activation_mock.assert_not_called()

    @patch("sales.services.issue_activation")
    @patch("sales.services.get_user_model")
    @patch("django_tenants.utils.schema_context", _noop_ctx)
    @patch("django.db.transaction.atomic", _noop_ctx)
    def test_lookup_is_limited_to_active_tenant_owners(self, get_user_model_mock, issue_activation_mock):
        User = self._user_model(None)
        get_user_model_mock.return_value = User

        self.assertIsNone(resend_activation_for_email("staff@example.com"))
        _, kwargs = User.objects.filter.call_args
        self.assertEqual(kwargs["role"], User.Roles.TENANT_OWNER)
        self.assertIs(kwargs["is_active"], True)
        self.assertIs(kwargs["tenant__isnull"], False)
        issue_activation_mock.assert_not_called()


# ── 3. Sibling tokens revoked ─────────────────────────────────────────────────

class ActivationTokenSiblingRevocationTests(SimpleTestCase):
    def test_issue_revokes_outstanding_tokens_before_creating(self):
        user = SimpleNamespace(pk=9)
        tenant = SimpleNamespace(pk=7)
        with patch.object(ActivationToken, "objects") as objects:
            ActivationToken.issue(tenant=tenant, user=user)

        objects.filter.assert_called_once_with(user=user, used_at__isnull=True)
        update_kwargs = objects.filter.return_value.update.call_args.kwargs
        self.assertIsNotNone(update_kwargs["used_at"])
        objects.create.assert_called_once()
        call_names = [c[0] for c in objects.mock_calls]
        self.assertLess(call_names.index("filter().update"), call_names.index("create"))

    def test_successful_consume_revokes_remaining_siblings(self):
        tok = ActivationToken(id=5, user_id=9, used_at=None, expires_at=timezone.now() + timedelta(hours=1))
        with patch.object(ActivationToken, "objects") as objects:
            objects.filter.return_value.update.return_value = 1
            self.assertTrue(tok.consume())

        self.assertEqual(objects.filter.call_count, 2)
        sibling_filter = objects.filter.call_args_list[1].kwargs
        self.assertEqual(sibling_filter, {"user_id": 9, "used_at__isnull": True})


# ── 4. Atomic consume + no forced re-activation ───────────────────────────────

class ActivationTokenConsumeCasTests(SimpleTestCase):
    def test_consume_is_a_compare_and_set_on_unused_unexpired(self):
        tok = ActivationToken(id=5, user_id=9, used_at=None, expires_at=timezone.now() + timedelta(hours=1))
        with patch.object(ActivationToken, "objects") as objects:
            objects.filter.return_value.update.return_value = 1
            tok.consume()

        cas_filter = objects.filter.call_args_list[0].kwargs
        self.assertEqual(cas_filter["pk"], 5)
        self.assertIs(cas_filter["used_at__isnull"], True)
        self.assertIn("expires_at__gt", cas_filter)

    def test_losing_the_race_returns_false_and_revokes_nothing(self):
        tok = ActivationToken(id=5, user_id=9, used_at=None, expires_at=timezone.now() + timedelta(hours=1))
        with patch.object(ActivationToken, "objects") as objects:
            objects.filter.return_value.update.return_value = 0  # another request won
            self.assertFalse(tok.consume())

        self.assertEqual(objects.filter.call_count, 1)
        self.assertIsNone(tok.used_at)


class ActivationSerializerSaveRaceTests(SimpleTestCase):
    def setUp(self):
        self.locked_user = _account(last_login=None)
        user_patcher = patch("accounts.serializers.User")
        user_cls = user_patcher.start()
        self.addCleanup(user_patcher.stop)
        user_cls.objects.select_for_update.return_value.get.return_value = self.locked_user
        tx_patcher = patch("accounts.serializers.transaction")
        tx_patcher.start()
        self.addCleanup(tx_patcher.stop)
        _patch_totp(self, confirmed=False)

    def _save(self, activation):
        serializer = ActivationSerializer()
        serializer._validated_data = {"activation": activation, "password": STRONG_PASSWORD}
        serializer._errors = {}
        return serializer.save()

    def test_lost_consume_race_does_not_set_password(self):
        activation = _activation(self.locked_user)
        activation.consume.return_value = False
        with self.assertRaises(ValidationError) as cm:
            self._save(activation)
        self.assertIn(ACTIVATION_TOKEN_EXPIRED_OR_USED, str(cm.exception))
        self.locked_user.set_password.assert_not_called()
        self.locked_user.save.assert_not_called()

    def test_account_activated_meanwhile_is_rechecked_under_lock(self):
        self.locked_user.last_login = timezone.now()  # a concurrent activation already signed in
        activation = _activation(self.locked_user)
        with self.assertRaises(ValidationError) as cm:
            self._save(activation)
        self.assertIn(ACTIVATION_ALREADY_DONE, str(cm.exception))
        activation.consume.assert_not_called()
        self.locked_user.set_password.assert_not_called()

    def test_deactivated_account_is_not_revived(self):
        self.locked_user.is_active = False
        activation = _activation(self.locked_user)
        with self.assertRaises(ValidationError) as cm:
            self._save(activation)
        self.assertIn(ACTIVATION_ACCOUNT_DISABLED, str(cm.exception))
        activation.consume.assert_not_called()
        self.assertIs(self.locked_user.is_active, False)

    def test_winner_sets_only_the_password(self):
        activation = _activation(self.locked_user)
        activation.consume.return_value = True
        self.assertIs(self._save(activation), self.locked_user)
        self.locked_user.set_password.assert_called_once_with(STRONG_PASSWORD)
        self.locked_user.save.assert_called_once_with(update_fields=["password"])
        self.assertIs(self.locked_user.is_active, True)


class ActivationSerializerDeactivatedTests(SimpleTestCase):
    def test_deactivated_account_rejected_at_validate(self):
        _patch_totp(self, confirmed=False)
        activation = _activation(_account(last_login=None, is_active=False))
        _patch_token_lookup(self, activation)
        with self.assertRaises(ValidationError) as cm:
            ActivationSerializer().validate({"token": "t", "password": STRONG_PASSWORD})
        self.assertIn(ACTIVATION_ACCOUNT_DISABLED, str(cm.exception))


# ── Per-email resend cap ──────────────────────────────────────────────────────

class ActivationResendPerEmailLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_cap_is_per_normalized_email(self):
        variants = ["owner@example.com", "Owner@Example.com", "  OWNER@example.com "]
        allowed = [activation_resend_allowed(variants[i % len(variants)])
                   for i in range(ACTIVATION_RESEND_PER_EMAIL_LIMIT + 1)]
        self.assertEqual(allowed, [True] * ACTIVATION_RESEND_PER_EMAIL_LIMIT + [False])
        # A different mailbox has its own budget.
        self.assertTrue(activation_resend_allowed("other@example.com"))

    def test_cache_key_does_not_contain_the_raw_email(self):
        key = _activation_resend_cache_key("owner@example.com")
        self.assertNotIn("owner", key)
        self.assertNotIn("example.com", key)

    def test_cache_outage_fails_open(self):
        with patch("sales.services.cache") as cache_mock:
            cache_mock.add.side_effect = ConnectionError("redis down")
            self.assertTrue(activation_resend_allowed("owner@example.com"))
        with patch("sales.services.cache") as cache_mock:
            cache_mock.incr.return_value = None  # django-redis IGNORE_EXCEPTIONS
            self.assertTrue(activation_resend_allowed("owner@example.com"))

    @patch("sales.services._log_provisioning_event")
    @patch("sales.services.get_user_model")
    def test_resend_over_cap_sends_nothing_and_skips_lookup(self, get_user_model_mock, log_event_mock):
        with patch("sales.services.activation_resend_allowed", return_value=False):
            self.assertIsNone(resend_activation_for_email("owner@example.com"))
        get_user_model_mock.assert_not_called()
        log_event_mock.assert_called_once_with("self_service_activation_resend_rate_limited")
