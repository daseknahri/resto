from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class CheckEmailDeliveryCommandTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_expect_smtp_rejects_non_smtp_backend(self):
        with self.assertRaises(CommandError):
            call_command("check_email_delivery", "--expect-smtp")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=True,
        EMAIL_FAIL_SILENTLY=False,
    )
    def test_rejects_tls_and_ssl_enabled_together(self):
        with self.assertRaises(CommandError):
            call_command("check_email_delivery")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
    )
    @patch("accounts.management.commands.check_email_delivery.send_mail", return_value=1)
    def test_send_test_email_success(self, mock_send_mail):
        stdout = StringIO()
        call_command(
            "check_email_delivery",
            "--expect-smtp",
            "--expect-no-fail-silently",
            "--send-test",
            "--to",
            "owner@example.com",
            stdout=stdout,
        )
        self.assertTrue(mock_send_mail.called)
        self.assertIn("Test email sent to: owner@example.com", stdout.getvalue())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=False,
    )
    @patch("accounts.management.commands.check_email_delivery.send_mail", return_value=0)
    def test_send_test_email_fails_when_zero_sent(self, mock_send_mail):
        with self.assertRaises(CommandError):
            call_command(
                "check_email_delivery",
                "--send-test",
                "--to",
                "owner@example.com",
            )
        self.assertTrue(mock_send_mail.called)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_USE_SSL=False,
        EMAIL_FAIL_SILENTLY=True,
    )
    def test_expect_no_fail_silently_rejects_true_setting(self):
        with self.assertRaises(CommandError):
            call_command("check_email_delivery", "--expect-no-fail-silently")
