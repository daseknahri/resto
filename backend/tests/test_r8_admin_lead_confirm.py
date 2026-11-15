"""Run 8 G2 — A-47: Lead bulk provision gets an intermediate confirmation page."""
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase, override_settings

from sales.admin import LeadAdmin
from sales.models import Lead


class LeadConfirmSaleTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = LeadAdmin(Lead, django_admin.site)
        self.leads = [
            SimpleNamespace(
                id=1,
                pk=1,
                name="Cafe One",
                email="one@example.com",
                plan="Basic",
                status="new",
                get_status_display=lambda: "New",
            ),
            SimpleNamespace(
                id=2,
                pk=2,
                name="Cafe Two",
                email="two@example.com",
                plan="Pro",
                status="new",
                get_status_display=lambda: "New",
            ),
        ]

    def _request(self, data):
        request = RequestFactory().post("/admin/sales/lead/", data)
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            is_staff=True,
            pk=1,
            username="admin",
            has_module_perms=lambda app_label: True,
            has_perm=lambda perm: True,
            get_short_name=lambda: "admin",
            get_username=lambda: "admin",
        )
        return request

    # Admin templates reference admin CSS via {% static %}; the project uses
    # a manifest static storage with no collected manifest in the test env,
    # so render with plain static storage for this template test.
    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_first_click_renders_confirmation_instead_of_provisioning(self):
        request = self._request({"action": "confirm_sale", "_selected_action": ["1", "2"]})
        with patch("sales.admin.provision_lead") as provision_lead:
            response = self.model_admin.confirm_sale(request, self.leads)
        provision_lead.assert_not_called()
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Cafe One", content)
        self.assertIn("Cafe Two", content)
        self.assertIn('name="confirm" value="yes"', content)

    def test_confirmed_post_provisions_each_lead(self):
        request = self._request(
            {"action": "confirm_sale", "_selected_action": ["1", "2"], "confirm": "yes"},
        )
        with (
            patch("sales.admin.provision_lead") as provision_lead,
            patch.object(self.model_admin, "message_user") as message_user,
        ):
            response = self.model_admin.confirm_sale(request, self.leads)
        self.assertEqual(provision_lead.call_count, 2)
        self.assertIsNone(response)
        message_user.assert_called_once()
        self.assertIn("Provisioned 2 tenant(s)", message_user.call_args.args[1])

    def test_confirmed_post_reports_provisioning_failures(self):
        request = self._request(
            {"action": "confirm_sale", "_selected_action": ["1"], "confirm": "yes"},
        )
        with (
            patch("sales.admin.provision_lead", side_effect=ValueError("no plan")),
            patch.object(self.model_admin, "message_user") as message_user,
        ):
            self.model_admin.confirm_sale(request, self.leads[:1])
        message_user.assert_called_once()
        self.assertEqual(message_user.call_args.kwargs["level"], messages.WARNING)
        self.assertIn("no plan", message_user.call_args.args[1])
