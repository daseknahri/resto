"""
Unit tests for the three serializers in accounts/serializers.py whose
validate / save methods are never directly exercised (only mocked at
the view layer):

  ActivationSerializer
    - validate: invalid token / expired / valid
    - save: locks the user, consumes the token (CAS), sets the password only

  PasswordResetRequestSerializer
    - validate: empty identifier / user found / user not found
    - save: user=None or no email → None; valid user → issues token

  PasswordResetConfirmSerializer
    - validate: token not found / expired / valid
    - save: locks the user, consumes the token (CAS), updates the password

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from accounts.serializers import (
    ActivationSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _activation(*, is_valid=True):
    a = MagicMock()
    a.is_valid.return_value = is_valid
    a.user = MagicMock()
    return a


def _reset_token(*, is_valid=True):
    r = MagicMock()
    r.is_valid.return_value = is_valid
    r.user = MagicMock()
    return r


# ══════════════════════════════════════════════════════════════════════════════
# ActivationSerializer.validate
# ══════════════════════════════════════════════════════════════════════════════

class ActivationSerializerValidateTests(SimpleTestCase):

    def setUp(self):
        # Account-state gate (already activated?) is covered in
        # test_activation_token_hardening.py; here the account is never-activated.
        patcher = patch("accounts.serializers.account_is_activated", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _s(self):
        return ActivationSerializer()

    def test_invalid_token_raises(self):
        with patch("accounts.serializers.ActivationToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.side_effect = mock_cls.DoesNotExist
            with self.assertRaises(ValidationError) as cm:
                self._s().validate({"token": "bad", "password": "secret123"})
        self.assertIn("Invalid token", str(cm.exception))

    def test_expired_token_raises(self):
        activation = _activation(is_valid=False)
        with patch("accounts.serializers.ActivationToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.return_value = activation
            with self.assertRaises(ValidationError) as cm:
                self._s().validate({"token": "expired", "password": "secret123"})
        self.assertIn("expired", str(cm.exception).lower())

    def test_valid_token_sets_activation_on_attrs(self):
        activation = _activation(is_valid=True)
        with patch("accounts.serializers.ActivationToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.return_value = activation
            result = self._s().validate({"token": "good-token", "password": "Zx9kLmop-42qR"})
        self.assertIs(result["activation"], activation)

    def test_valid_token_preserves_password(self):
        activation = _activation(is_valid=True)
        with patch("accounts.serializers.ActivationToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.return_value = activation
            result = self._s().validate({"token": "good-token", "password": "Zx9kLmop-42qR"})
        self.assertEqual(result["password"], "Zx9kLmop-42qR")


# ══════════════════════════════════════════════════════════════════════════════
# ActivationSerializer.save
# ══════════════════════════════════════════════════════════════════════════════

class ActivationSerializerSaveTests(SimpleTestCase):
    """save() locks the account row, re-checks it, consumes the token with a
    compare-and-set and only then sets the password (see
    test_activation_token_hardening.py for the rejection paths)."""

    def setUp(self):
        self.locked_user = MagicMock()
        self.locked_user.is_active = True
        user_patcher = patch("accounts.serializers.User")
        self.user_cls = user_patcher.start()
        self.addCleanup(user_patcher.stop)
        self.user_cls.objects.select_for_update.return_value.get.return_value = self.locked_user
        tx_patcher = patch("accounts.serializers.transaction")
        tx_patcher.start()
        self.addCleanup(tx_patcher.stop)
        activated_patcher = patch("accounts.serializers.account_is_activated", return_value=False)
        activated_patcher.start()
        self.addCleanup(activated_patcher.stop)

    def _s_validated(self, activation):
        s = ActivationSerializer()
        s._validated_data = {"activation": activation, "password": "newpass123"}
        s._errors = {}
        return s

    def _activation(self):
        activation = _activation()
        activation.consume.return_value = True
        return activation

    def test_save_sets_password_on_locked_user(self):
        activation = self._activation()
        self._s_validated(activation).save()
        self.user_cls.objects.select_for_update.return_value.get.assert_called_once_with(pk=activation.user_id)
        self.locked_user.set_password.assert_called_once_with("newpass123")

    def test_save_does_not_touch_is_active(self):
        # Old behaviour forced is_active=True (reviving a deactivated account);
        # only the password is persisted now.
        activation = self._activation()
        self._s_validated(activation).save()
        self.locked_user.save.assert_called_once_with(update_fields=["password"])

    def test_save_consumes_token_atomically(self):
        activation = self._activation()
        self._s_validated(activation).save()
        activation.consume.assert_called_once()
        activation.mark_used.assert_not_called()

    def test_save_returns_locked_user(self):
        activation = self._activation()
        result = self._s_validated(activation).save()
        self.assertIs(result, self.locked_user)


# ══════════════════════════════════════════════════════════════════════════════
# PasswordResetRequestSerializer.validate
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetRequestValidateTests(SimpleTestCase):

    def _s(self):
        return PasswordResetRequestSerializer()

    def test_empty_identifier_raises(self):
        with self.assertRaises(ValidationError) as cm:
            self._s().validate({"identifier": ""})
        self.assertIn("required", str(cm.exception).lower())

    def test_whitespace_only_identifier_raises(self):
        with self.assertRaises(ValidationError):
            self._s().validate({"identifier": "   "})

    def test_user_found_set_on_attrs(self):
        user = MagicMock()
        with patch("accounts.serializers.User") as mock_user_cls:
            mock_user_cls.objects.filter.return_value.order_by.return_value.first.return_value = user
            result = self._s().validate({"identifier": "john@example.com"})
        self.assertIs(result["user"], user)

    def test_user_not_found_sets_none(self):
        with patch("accounts.serializers.User") as mock_user_cls:
            mock_user_cls.objects.filter.return_value.order_by.return_value.first.return_value = None
            result = self._s().validate({"identifier": "nobody@example.com"})
        self.assertIsNone(result["user"])

    def test_identifier_stripped_on_attrs(self):
        with patch("accounts.serializers.User") as mock_user_cls:
            mock_user_cls.objects.filter.return_value.order_by.return_value.first.return_value = None
            result = self._s().validate({"identifier": "  john@example.com  "})
        self.assertEqual(result["identifier"], "john@example.com")


# ══════════════════════════════════════════════════════════════════════════════
# PasswordResetRequestSerializer.save
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetRequestSaveTests(SimpleTestCase):

    def _s_validated(self, user):
        s = PasswordResetRequestSerializer()
        s._validated_data = {"identifier": "test@example.com", "user": user}
        s._errors = {}
        return s

    def test_none_user_returns_none(self):
        s = self._s_validated(user=None)
        result = s.save()
        self.assertIsNone(result)

    def test_user_without_email_returns_none(self):
        user = MagicMock()
        user.email = ""
        s = self._s_validated(user=user)
        result = s.save()
        self.assertIsNone(result)

    def test_valid_user_issues_token(self):
        user = MagicMock()
        user.email = "john@example.com"
        token = MagicMock()
        s = self._s_validated(user=user)
        with patch("accounts.serializers.PasswordResetToken") as mock_tok:
            mock_tok.issue.return_value = token
            result = s.save()
        mock_tok.issue.assert_called_once_with(user=user, hours_valid=2)
        self.assertIs(result, token)


# ══════════════════════════════════════════════════════════════════════════════
# PasswordResetConfirmSerializer.validate
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetConfirmValidateTests(SimpleTestCase):

    def _s(self):
        return PasswordResetConfirmSerializer()

    def test_token_not_found_raises_invalid(self):
        with patch("accounts.serializers.PasswordResetToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.side_effect = mock_cls.DoesNotExist
            with self.assertRaises(ValidationError) as cm:
                self._s().validate({"token": "bad", "password": "newpass123"})
        self.assertIn("Invalid token", str(cm.exception))

    def test_expired_token_raises(self):
        reset = _reset_token(is_valid=False)
        with patch("accounts.serializers.PasswordResetToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.return_value = reset
            with self.assertRaises(ValidationError) as cm:
                self._s().validate({"token": "expired", "password": "newpass123"})
        self.assertIn("expired", str(cm.exception).lower())

    def test_valid_token_sets_reset_on_attrs(self):
        reset = _reset_token(is_valid=True)
        with patch("accounts.serializers.PasswordResetToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.return_value = reset
            result = self._s().validate({"token": "good", "password": "newpass123"})
        self.assertIs(result["reset"], reset)

    def test_empty_token_stripped_before_lookup(self):
        """Token string is stripped before .get(); whitespace-only → DoesNotExist."""
        with patch("accounts.serializers.PasswordResetToken") as mock_cls:
            mock_cls.DoesNotExist = Exception
            mock_cls.objects.select_related.return_value.get.side_effect = mock_cls.DoesNotExist
            with self.assertRaises(ValidationError):
                self._s().validate({"token": "   ", "password": "newpass123"})


# ══════════════════════════════════════════════════════════════════════════════
# PasswordResetConfirmSerializer.save
# ══════════════════════════════════════════════════════════════════════════════

class PasswordResetConfirmSaveTests(SimpleTestCase):
    """save() locks the account row, consumes the token with a compare-and-set and
    only then sets the password (race regressions: test_activation_token_secrecy.py)."""

    def setUp(self):
        self.locked_user = MagicMock()
        user_patcher = patch("accounts.serializers.User")
        self.user_cls = user_patcher.start()
        self.addCleanup(user_patcher.stop)
        self.user_cls.objects.select_for_update.return_value.get.return_value = self.locked_user
        tx_patcher = patch("accounts.serializers.transaction")
        tx_patcher.start()
        self.addCleanup(tx_patcher.stop)
        sessions_patcher = patch("accounts.serializers._invalidate_user_sessions")
        sessions_patcher.start()
        self.addCleanup(sessions_patcher.stop)

    def _s_validated(self, reset):
        s = PasswordResetConfirmSerializer()
        s._validated_data = {"reset": reset, "password": "newpass999"}
        s._errors = {}
        return s

    def _reset(self):
        reset = _reset_token()
        reset.consume.return_value = True
        return reset

    def test_save_sets_new_password_on_locked_user(self):
        reset = self._reset()
        self._s_validated(reset).save()
        self.user_cls.objects.select_for_update.return_value.get.assert_called_once_with(pk=reset.user_id)
        self.locked_user.set_password.assert_called_once_with("newpass999")

    def test_save_updates_user(self):
        reset = self._reset()
        self._s_validated(reset).save()
        self.locked_user.save.assert_called_once_with(update_fields=["password"])

    def test_save_consumes_token_atomically(self):
        reset = self._reset()
        self._s_validated(reset).save()
        reset.consume.assert_called_once()
        reset.mark_used.assert_not_called()

    def test_save_returns_locked_user(self):
        reset = self._reset()
        result = self._s_validated(reset).save()
        self.assertIs(result, self.locked_user)
