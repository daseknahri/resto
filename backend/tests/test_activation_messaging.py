from types import SimpleNamespace

from django.test import SimpleTestCase

from sales.messaging import (
    build_activation_message,
    build_activation_url,
    build_admin_url,
    build_onboarding_url,
    build_owner_checklist,
    build_public_menu_url,
    build_signin_url,
    build_tenant_frontend_url,
    build_workspace_url,
)


def _tenant(domain):
    primary = SimpleNamespace(domain=domain)
    domains = SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(first=lambda: primary))
    return SimpleNamespace(slug="demo", domains=domains)


class ActivationMessagingTests(SimpleTestCase):
    def test_builds_owner_workspace_urls_for_production_domain(self):
        tenant = _tenant("demo.kepoli.com")
        self.assertEqual(build_tenant_frontend_url(tenant), "https://demo.kepoli.com")
        self.assertEqual(build_workspace_url(tenant), "https://demo.kepoli.com/owner")
        self.assertEqual(build_onboarding_url(tenant), "https://demo.kepoli.com/owner/onboarding")
        self.assertEqual(build_signin_url(tenant), "https://demo.kepoli.com/signin")
        self.assertEqual(build_public_menu_url(tenant), "https://demo.kepoli.com/menu")
        self.assertEqual(build_admin_url(tenant), "https://demo.kepoli.com/admin/")
        self.assertEqual(build_activation_url(tenant, "abc123"), "https://demo.kepoli.com/activate?token=abc123")

    def test_activation_message_points_owner_to_workspace_not_django_admin(self):
        message = build_activation_message(
            "https://demo.kepoli.com/owner",
            "https://demo.kepoli.com/signin",
            "https://demo.kepoli.com/activate?token=abc123",
            "https://demo.kepoli.com/owner/onboarding",
            "https://demo.kepoli.com/menu",
            "abc123",
        )
        self.assertIn("Onboarding: https://demo.kepoli.com/owner/onboarding", message)
        self.assertIn("Sign in: https://demo.kepoli.com/signin", message)
        self.assertIn("Live menu: https://demo.kepoli.com/menu", message)
        self.assertNotIn("/admin/", message)

    def test_owner_checklist_returns_expected_sequence(self):
        steps = build_owner_checklist(
            "https://demo.kepoli.com/owner",
            "https://demo.kepoli.com/signin",
            "https://demo.kepoli.com/activate?token=abc123",
            "https://demo.kepoli.com/owner/onboarding",
            "https://demo.kepoli.com/menu",
        )
        self.assertEqual(len(steps), 6)
        self.assertIn("set password", steps[0])
        self.assertIn("/owner/onboarding", steps[2])
        self.assertIn("/menu", steps[4])
