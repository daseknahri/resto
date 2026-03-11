from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from sales.views import LeadOnboardingPackageView


def _admin_user():
    return SimpleNamespace(pk=1, is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True)


class LeadOnboardingPackageViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = LeadOnboardingPackageView.as_view()

    @patch("sales.views.log_admin_action")
    @patch("sales.views.build_owner_checklist")
    @patch("sales.views.build_public_menu_url")
    @patch("sales.views.build_onboarding_url")
    @patch("sales.views.onboarding_package_for_lead")
    @patch("sales.views.get_object_or_404")
    def test_response_includes_owner_journey_fields(
        self,
        get_object_or_404_mock,
        onboarding_package_mock,
        build_onboarding_url_mock,
        build_public_menu_url_mock,
        build_owner_checklist_mock,
        log_admin_action_mock,
    ):
        tenant = SimpleNamespace(slug="demo")
        lead = SimpleNamespace(id=1)
        get_object_or_404_mock.return_value = lead
        build_onboarding_url_mock.return_value = "https://demo.kepoli.com/owner/onboarding"
        build_public_menu_url_mock.return_value = "https://demo.kepoli.com/menu"
        build_owner_checklist_mock.return_value = ["step 1", "step 2"]
        onboarding_package_mock.return_value = SimpleNamespace(
            tenant=tenant,
            tenant_url="https://demo.kepoli.com",
            workspace_url="https://demo.kepoli.com/owner",
            signin_url="https://demo.kepoli.com/signin",
            admin_url="https://demo.kepoli.com/admin/",
            activation_url="https://demo.kepoli.com/activate?token=abc",
            activation_token=SimpleNamespace(token="abc"),
            whatsapp_link="https://wa.me/212600000000?text=...",
            whatsapp_message_template="message",
        )

        request = self.factory.get("/api/lead-onboarding-package/1/")
        force_authenticate(request, user=_admin_user())
        response = self.view(request, lead_id=1)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["onboarding_url"], "https://demo.kepoli.com/owner/onboarding")
        self.assertEqual(response.data["public_menu_url"], "https://demo.kepoli.com/menu")
        self.assertEqual(response.data["owner_next_steps"], ["step 1", "step 2"])
        log_admin_action_mock.assert_called_once()
