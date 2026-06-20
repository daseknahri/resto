"""
Unit tests for the three serializers in accounts/serializers.py whose
validate / save methods are never directly exercised (only mocked at
the view layer):

  ActivationSerializer
    - validate: invalid token / expired / valid
    - save: activates user, marks token used

  PasswordResetRequestSerializer
    - validate: empty identifier / user found / user not found
    - save: user=None or no email → None; valid user → issues token

  PasswordResetConfirmSerializer
    - validate: token not found / expired / valid
    - save: updates password, marks token used

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

    def _s_validated(self, activation):
        s = ActivationSerializer()
        s._validated_data = {"activation": activation, "password": "newpass123"}
        s._errors = {}
        return s

    def test_save_sets_password(self):
        activation = _activation()
        s = self._s_validated(activation)
        s.save()
        activation.user.set_password.assert_called_once_with("newpass123")

    def test_save_activates_user(self):
        activation = _activation()
        s = self._s_validated(activation)
        s.save()
        self.assertTrue(activation.user.is_active)

    def test_save_calls_user_save(self):
        activation = _activation()
        s = self._s_validated(activation)
        s.save()
        activation.user.save.assert_called_once()

    def test_save_marks_token_used(self):
        activation = _activation()
        s = self._s_validated(activation)
        s.save()
        activation.mark_used.assert_called_once()

    def test_save_returns_user(self):
        activation = _activation()
        s = self._s_validated(activation)
        result = s.save()
        self.assertIs(result, activation.user)


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

    def _s_validated(self, reset):
        s = PasswordResetConfirmSerializer()
        s._validated_data = {"reset": reset, "password": "newpass999"}
        s._errors = {}
        return s

    def test_save_sets_new_password(self):
        reset = _reset_token()
        s = self._s_validated(reset)
        s.save()
        reset.user.set_password.assert_called_once_with("newpass999")

    def test_save_updates_user(self):
        reset = _reset_token()
        s = self._s_validated(reset)
        s.save()
        reset.user.save.assert_called_once_with(update_fields=["password"])

    def test_save_marks_token_used(self):
        reset = _reset_token()
        s = self._s_validated(reset)
        s.save()
        reset.mark_used.assert_called_once()

    def test_save_returns_user(self):
        reset = _reset_token()
        s = self._s_validated(reset)
        result = s.save()
        self.assertIs(result, reset.user)
