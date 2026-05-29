"""
Additional unit tests for accounts.management.commands.check_email_delivery
covering _validate_config cases not covered by test_check_email_delivery_command.py:

  - SMTP backend with missing EMAIL_HOST → raises CommandError
  - SMTP backend with EMAIL_PORT <= 0 → raises CommandError
  - SMTP backend with missing credentials → warning (not error)
  - --expect-no-fail-silently passes when fail_silently=False
  - Non-SMTP backend passes without --expect-smtp
  - send-test without --to → raises CommandError

All tests use call_command + override_settings (no real network).
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


_SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
_CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"


class ValidateConfigSmtpEdgeCasesTests(SimpleTestCase):
    """SMTP-specific validation rules inside _validate_config."""

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="",        # ← missing
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_smtp_missing_email_host_raises(self):
        with self.assertRaises(CommandError) as cm:
            call_command("check_email_delivery")
        self.assertIn("EMAIL_HOST", str(cm.exception))

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=0,          # ← invalid
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_smtp_zero_port_raises(self):
        with self.assertRaises(CommandError) as cm:
            call_command("check_email_delivery")
        self.assertIn("EMAIL_PORT", str(cm.exception))

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=-1,         # ← negative
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_smtp_negative_port_raises(self):
        with self.assertRaises(CommandError):
            call_command("check_email_delivery")

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
        EMAIL_HOST_USER="",    # ← empty credentials
        EMAIL_HOST_PASSWORD="",
    )
    def test_smtp_empty_credentials_writes_warning_not_error(self):
        stdout = StringIO()
        # Should NOT raise — empty credentials are allowed for relay setups
        call_command("check_email_delivery", stdout=stdout)
        out = stdout.getvalue()
        self.assertIn("credentials", out.lower())

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
        EMAIL_HOST_USER="user@example.com",
        EMAIL_HOST_PASSWORD="secret",
    )
    def test_smtp_valid_config_writes_ok_message(self):
        stdout = StringIO()
        call_command("check_email_delivery", stdout=stdout)
        self.assertIn("OK", stdout.getvalue())

    @override_settings(
        EMAIL_BACKEND=_SMTP_BACKEND,
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
        EMAIL_HOST_USER="user",
        EMAIL_HOST_PASSWORD="pass",
    )
    def test_expect_smtp_passes_when_backend_is_smtp(self):
        stdout = StringIO()
        # Should NOT raise
        call_command("check_email_delivery", "--expect-smtp", stdout=stdout)
        self.assertIn("OK", stdout.getvalue())


class NonSmtpBackendTests(SimpleTestCase):
    """Non-SMTP backends pass without --expect-smtp flag."""

    @override_settings(
        EMAIL_BACKEND=_CONSOLE_BACKEND,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_console_backend_passes_without_expect_smtp(self):
        stdout = StringIO()
        call_command("check_email_delivery", stdout=stdout)
        self.assertIn("OK", stdout.getvalue())

    @override_settings(
        EMAIL_BACKEND=_CONSOLE_BACKEND,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_expect_no_fail_silently_passes_when_fail_silently_is_false(self):
        stdout = StringIO()
        call_command("check_email_delivery", "--expect-no-fail-silently", stdout=stdout)
        self.assertIn("OK", stdout.getvalue())


class SendTestEmailEdgeCasesTests(SimpleTestCase):
    """--send-test without --to raises CommandError."""

    @override_settings(
        EMAIL_BACKEND=_CONSOLE_BACKEND,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_send_test_without_to_raises(self):
        with self.assertRaises(CommandError) as cm:
            call_command("check_email_delivery", "--send-test")
        self.assertIn("--to", str(cm.exception))
