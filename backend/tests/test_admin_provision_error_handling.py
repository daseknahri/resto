from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import LeadOnboardingPackageView, LeadResendActivationView, ProvisionLeadViewSet


def _admin_user():
    return SimpleNamespace(pk=1, is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True)


class AdminProvisionErrorHandlingTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("sales.views.log_admin_action")
    @patch("sales.views.provision_lead", side_effect=RuntimeError("boom-provision"))
    @patch("sales.views.ProvisionLeadViewSet.get_object")
    def test_provision_returns_json_500_on_unexpected_error(
        self,
        get_object_mock,
        provision_lead_mock,
        log_admin_action_mock,
    ):
        get_object_mock.return_value = SimpleNamespace(id=3)
        view = ProvisionLeadViewSet.as_view({"put": "update"})

        request = self.factory.put("/api/lead-provision/3/", {"domain_suffix": "menu.kepoli.com"}, format="json")
        force_authenticate(request, user=_admin_user())
        response = view(request, pk=3)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "Provisioning failed unexpectedly.")
        self.assertEqual(response.data["error"], "boom-provision")
        log_admin_action_mock.assert_called_once()
        provision_lead_mock.assert_called_once()

    @patch("sales.views.build_onboarding_url", side_effect=RuntimeError("boom-response"))
    @patch("sales.views.log_admin_action")
    @patch("sales.views.provision_lead")
    @patch("sales.views.ProvisionLeadViewSet.get_object")
    def test_provision_returns_json_500_when_response_build_fails(
        self,
        get_object_mock,
        provision_lead_mock,
        log_admin_action_mock,
        build_onboarding_url_mock,
    ):
        tenant = SimpleNamespace(slug="demo")
        get_object_mock.return_value = SimpleNamespace(id=6)
        provision_lead_mock.return_value = SimpleNamespace(
            tenant=tenant,
            tenant_url="https://demo.menu.kepoli.com",
            workspace_url="https://demo.menu.kepoli.com/owner",
            signin_url="https://demo.menu.kepoli.com/signin",
            admin_url="https://demo.menu.kepoli.com/admin/",
            activation_url="https://demo.menu.kepoli.com/activate?token=abc",
            activation_token=SimpleNamespace(token="abc"),
            job=SimpleNamespace(id=9),
            whatsapp_link="",
            whatsapp_message_template="msg",
        )
        view = ProvisionLeadViewSet.as_view({"put": "update"})

        request = self.factory.put("/api/lead-provision/6/", {"domain_suffix": "menu.kepoli.com"}, format="json")
        force_authenticate(request, user=_admin_user())
        response = view(request, pk=6)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "Provisioning failed unexpectedly.")
        self.assertEqual(response.data["error"], "boom-response")
        self.assertEqual(log_admin_action_mock.call_count, 2)
        provision_lead_mock.assert_called_once()
        build_onboarding_url_mock.assert_called_once()

    @patch("sales.views.onboarding_package_for_lead", side_effect=RuntimeError("boom-package"))
    @patch("sales.views.get_object_or_404")
    def test_onboarding_package_returns_json_500_on_unexpected_error(
        self,
        get_object_or_404_mock,
        onboarding_package_mock,
    ):
        get_object_or_404_mock.return_value = SimpleNamespace(id=3)
        view = LeadOnboardingPackageView.as_view()

        request = self.factory.get("/api/lead-onboarding-package/3/")
        force_authenticate(request, user=_admin_user())
        response = view(request, lead_id=3)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "Onboarding package failed unexpectedly.")
        self.assertEqual(response.data["error"], "boom-package")
        onboarding_package_mock.assert_called_once()

    @patch("sales.views.resend_activation_for_lead", side_effect=RuntimeError("boom-resend"))
    @patch("sales.views.get_object_or_404")
    def test_resend_activation_returns_json_500_on_unexpected_error(
        self,
        get_object_or_404_mock,
        resend_activation_mock,
    ):
        get_object_or_404_mock.return_value = SimpleNamespace(id=3)
        view = LeadResendActivationView.as_view()

        request = self.factory.post("/api/lead-resend-activation/3/")
        force_authenticate(request, user=_admin_user())
        response = view(request, lead_id=3)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["detail"], "Activation resend failed unexpectedly.")
        self.assertEqual(response.data["error"], "boom-resend")
        resend_activation_mock.assert_called_once()
