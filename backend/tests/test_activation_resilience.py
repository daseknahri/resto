from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from sales.services import issue_activation


class IssueActivationResilienceTests(SimpleTestCase):
    @patch("sales.services._log_provisioning_event")
    @patch("sales.services.logger")
    @patch("sales.services.send_activation_email", side_effect=RuntimeError("smtp down"))
    @patch("sales.services.send_activation_whatsapp", return_value="")
    @patch("sales.services.build_activation_message", return_value="activation-message")
    @patch("sales.services.build_activation_url", return_value="https://demo.menu.kepoli.com/activate?token=abc")
    @patch("sales.services.build_public_menu_url", return_value="https://demo.menu.kepoli.com/menu")
    @patch("sales.services.build_tenant_frontend_url", return_value="https://demo.menu.kepoli.com")
    @patch("sales.services.build_signin_url", return_value="https://demo.menu.kepoli.com/signin")
    @patch("sales.services.build_onboarding_url", return_value="https://demo.menu.kepoli.com/owner/onboarding")
    @patch("sales.services.build_workspace_url", return_value="https://demo.menu.kepoli.com/owner")
    @patch("sales.services.build_admin_url", return_value="https://demo.menu.kepoli.com/admin/")
    @patch("sales.services.ActivationToken.issue")
    def test_issue_activation_does_not_raise_when_email_fails(
        self,
        issue_token_mock,
        build_admin_url_mock,
        build_workspace_url_mock,
        build_onboarding_url_mock,
        build_signin_url_mock,
        build_tenant_frontend_url_mock,
        build_public_menu_url_mock,
        build_activation_url_mock,
        build_activation_message_mock,
        send_activation_whatsapp_mock,
        send_activation_email_mock,
        logger_mock,
        log_event_mock,
    ):
        tenant = SimpleNamespace(id=7, slug="demo")
        user = SimpleNamespace(id=11, email="owner@example.com")
        activation = SimpleNamespace(token="abc")
        issue_token_mock.return_value = activation

        result = issue_activation(tenant, user, phone="+212600000000")

        self.assertEqual(result[0], activation)
        self.assertEqual(result[1], "https://demo.menu.kepoli.com/admin/")
        self.assertEqual(result[2], "https://demo.menu.kepoli.com/owner")
        self.assertEqual(result[3], "https://demo.menu.kepoli.com/signin")
        self.assertEqual(result[4], "https://demo.menu.kepoli.com")
        self.assertEqual(result[5], "https://demo.menu.kepoli.com/activate?token=abc")
        self.assertEqual(result[6], "")
        self.assertEqual(result[7], "activation-message")
        send_activation_email_mock.assert_called_once()
        logger_mock.exception.assert_called_once()
        log_event_mock.assert_any_call(
            "activation_email_failed",
            tenant_id=7,
            tenant_slug="demo",
            user_id=11,
            error_type="RuntimeError",
            error="smtp down",
        )
