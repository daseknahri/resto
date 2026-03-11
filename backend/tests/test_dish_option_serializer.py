from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from menu.serializers import DishOptionSerializer


class DishOptionSerializerTests(SimpleTestCase):
    def test_serializer_exposes_dish_field_as_write_only(self):
        serializer = DishOptionSerializer()
        self.assertIn("dish", serializer.fields)
        self.assertTrue(serializer.fields["dish"].write_only)

    def test_validate_price_delta_rejects_negative_values(self):
        serializer = DishOptionSerializer()
        with self.assertRaisesMessage(ValidationError, "Price delta must be zero or greater."):
            serializer.validate_price_delta(-1)

    def test_validate_max_select_rejects_zero(self):
        serializer = DishOptionSerializer()
        with self.assertRaisesMessage(ValidationError, "Max select must be at least 1."):
            serializer.validate_max_select(0)

    def test_validate_name_i18n_enforces_plan_max_languages(self):
        request = APIRequestFactory().get("/api/options/")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=1))
        serializer = DishOptionSerializer(context={"request": request})
        with self.assertRaisesMessage(ValidationError, "Current plan supports up to 1 translated language entries for Option name."):
            serializer.validate_name_i18n({"fr": "Fromage", "ar": "جبن"})

    def test_validate_name_i18n_accepts_valid_locale_map(self):
        request = APIRequestFactory().get("/api/options/")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=2))
        serializer = DishOptionSerializer(context={"request": request})
        cleaned = serializer.validate_name_i18n({"fr": "Fromage", "en": "Cheese"})
        self.assertEqual(cleaned, {"fr": "Fromage", "en": "Cheese"})
