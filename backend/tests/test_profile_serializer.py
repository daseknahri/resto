from django.test import SimpleTestCase

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
