from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import ValidationError

from tenancy.models import Plan, Profile, Tenant
from tenancy.serializers import ProfileSerializer


class ProfileSerializerTests(SimpleTestCase):
    def test_reservation_url_field_is_exposed(self):
        serializer = ProfileSerializer()
        self.assertIn("reservation_url", serializer.fields)

    def test_reservation_url_accepts_valid_url(self):
        serializer = ProfileSerializer(data={"reservation_url": "https://reserve.example.com/book"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_reservation_url_rejects_invalid_url(self):
        serializer = ProfileSerializer(data={"reservation_url": "invalid-url"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("reservation_url", serializer.errors)

    def test_language_accepts_supported_codes(self):
        serializer = ProfileSerializer(data={"language": "fr"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_language_rejects_unsupported_codes(self):
        serializer = ProfileSerializer(data={"language": "es"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("language", serializer.errors)

    def test_logo_url_is_normalized_to_https_for_same_host_media(self):
        request = RequestFactory().get("/", secure=True, HTTP_HOST="badr.menu.kepoli.com")
        tenant = Tenant(name="Badr", slug="badr", plan=Plan(code="basic", name="Basic"))
        profile = Profile(tenant=tenant, logo_url="http://badr.menu.kepoli.com/media/uploads/badr/logo.webp")

        serializer = ProfileSerializer(instance=profile, context={"request": request})

        self.assertEqual(
            serializer.data["logo_url"],
            "https://badr.menu.kepoli.com/media/uploads/badr/logo.webp",
        )

    def test_partial_update_does_not_fail_on_existing_disabled_without_note(self):
        tenant = Tenant(name="Demo", slug="demo", plan=Plan(code="basic", name="Basic"))
        profile = Profile(
            tenant=tenant,
            is_menu_temporarily_disabled=True,
            menu_disabled_note="",
            tagline="Old",
        )
        serializer = ProfileSerializer(instance=profile, data={"tagline": "New"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_disabling_menu_requires_note_when_disable_flag_provided(self):
        serializer = ProfileSerializer(data={"is_menu_temporarily_disabled": True, "menu_disabled_note": ""}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("menu_disabled_note", serializer.errors)

    def test_profile_i18n_localizes_for_public_requests(self):
        request = RequestFactory().get("/api/meta/?lang=fr", HTTP_HOST="demo.menu.kepoli.com")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            tagline="Fast menu",
            tagline_i18n={"fr": "Menu rapide", "ar": "قائمة سريعة"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["tagline"], "Menu rapide")

    def test_profile_i18n_keeps_base_fields_for_authenticated_owner(self):
        request = RequestFactory().get("/api/profile/?lang=fr", HTTP_HOST="demo.menu.kepoli.com")
        request.user = SimpleNamespace(is_authenticated=True)
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            tagline="Fast menu",
            tagline_i18n={"fr": "Menu rapide"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["tagline"], "Fast menu")

    def test_profile_i18n_enforces_plan_limit(self):
        request = RequestFactory().get("/api/profile/", HTTP_HOST="demo.menu.kepoli.com")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        serializer = ProfileSerializer(context={"request": request})
        cleaned = serializer.validate_tagline_i18n({"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu"})
        self.assertEqual(cleaned, {"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu"})
        with self.assertRaisesMessage(
            ValidationError, "Current plan supports up to 3 translated language entries for Tagline."
        ):
            serializer.validate_tagline_i18n(
                {"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu", "en-us": "Fast menu US"}
            )
