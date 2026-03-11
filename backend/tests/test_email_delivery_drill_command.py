from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class EmailDeliveryDrillCommandTests(SimpleTestCase):
    @override_settings(PUBLIC_MENU_BASE_URL="https://menu.kepoli.com")
    @patch("accounts.management.commands.email_delivery_drill.send_password_reset_email", return_value=1)
    @patch("accounts.management.commands.email_delivery_drill.send_activation_email", return_value=1)
    def test_drill_sends_both_messages(self, mock_activation, mock_reset):
        stdout = StringIO()
        call_command("email_delivery_drill", "--to", "owner@example.com", stdout=stdout)

        self.assertTrue(mock_activation.called)
        self.assertTrue(mock_reset.called)
        self.assertIn("Email drill OK", stdout.getvalue())

    @patch("accounts.management.commands.email_delivery_drill.send_password_reset_email", return_value=1)
    @patch("accounts.management.commands.email_delivery_drill.send_activation_email", return_value=1)
    def test_accepts_host_without_scheme(self, mock_activation, mock_reset):
        call_command(
            "email_delivery_drill",
            "--to",
            "owner@example.com",
            "--base-url",
            "menu.kepoli.com",
        )
        activation_args = mock_activation.call_args.args
        self.assertIn("https://menu.kepoli.com/activate?token=", activation_args[3])

    @patch("accounts.management.commands.email_delivery_drill.send_password_reset_email", return_value=1)
    @patch("accounts.management.commands.email_delivery_drill.send_activation_email", return_value=0)
    def test_fails_when_any_message_not_sent(self, mock_activation, mock_reset):
        with self.assertRaises(CommandError):
            call_command(
                "email_delivery_drill",
                "--to",
                "owner@example.com",
                "--base-url",
                "https://menu.kepoli.com",
            )

    def test_rejects_invalid_base_url(self):
        with self.assertRaises(CommandError):
            call_command(
                "email_delivery_drill",
                "--to",
                "owner@example.com",
                "--base-url",
                "://bad",
            )
