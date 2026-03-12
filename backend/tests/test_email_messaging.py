from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from accounts.messaging import send_password_reset_email
from sales.messaging import send_activation_email


class EmailMessagingTests(SimpleTestCase):
    @override_settings(EMAIL_FAIL_SILENTLY=False)
    @patch("accounts.messaging.send_mail", return_value=1)
    def test_password_reset_email_uses_email_fail_silently_setting(self, mock_send_mail):
        send_password_reset_email("owner@example.com", "https://demo.kepoli.com/reset?token=abc", "abc")
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(mock_send_mail.call_args.kwargs["fail_silently"], False)

    @override_settings(EMAIL_FAIL_SILENTLY=False)
    @patch("sales.messaging.send_mail", return_value=1)
    def test_activation_email_uses_email_fail_silently_setting(self, mock_send_mail):
        send_activation_email(
            "owner@example.com",
            "https://demo.kepoli.com/owner",
            "https://demo.kepoli.com/signin",
            "https://demo.kepoli.com/activate?token=abc",
            "https://demo.kepoli.com/owner/onboarding",
            "https://demo.kepoli.com/menu",
            "abc",
        )
        self.assertTrue(mock_send_mail.called)
        self.assertEqual(mock_send_mail.call_args.kwargs["fail_silently"], False)

    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("accounts.messaging.logger")
    @patch("accounts.messaging.send_mail", return_value=0)
    def test_password_reset_email_logs_when_not_sent(self, mock_send_mail, mock_logger):
        send_password_reset_email("owner@example.com", "https://demo.kepoli.com/reset?token=abc", "abc")
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(mock_logger.warning.called)

    @override_settings(EMAIL_FAIL_SILENTLY=True)
    @patch("sales.messaging.logger")
    @patch("sales.messaging.send_mail", return_value=0)
    def test_activation_email_logs_when_not_sent(self, mock_send_mail, mock_logger):
        send_activation_email(
            "owner@example.com",
            "https://demo.kepoli.com/owner",
            "https://demo.kepoli.com/signin",
            "https://demo.kepoli.com/activate?token=abc",
            "https://demo.kepoli.com/owner/onboarding",
            "https://demo.kepoli.com/menu",
            "abc",
        )
        self.assertTrue(mock_send_mail.called)
        self.assertTrue(mock_logger.warning.called)
