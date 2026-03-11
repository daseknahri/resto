from django.test import SimpleTestCase
from django.urls import resolve


class PublicUrlconfTests(SimpleTestCase):
    def test_public_urlconf_exposes_session_endpoint(self):
        match = resolve("/api/session/", urlconf="config.public_urls")
        self.assertEqual(match.view_name, "session")

    def test_public_urlconf_exposes_lead_endpoint(self):
        match = resolve("/api/leads/", urlconf="config.public_urls")
        self.assertEqual(match.view_name, "lead-list")

    def test_public_urlconf_exposes_admin_tenants_endpoint(self):
        match = resolve("/api/admin-tenants/", urlconf="config.public_urls")
        self.assertEqual(match.view_name, "admin-tenants")
