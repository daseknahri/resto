from django.test import RequestFactory, SimpleTestCase

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
