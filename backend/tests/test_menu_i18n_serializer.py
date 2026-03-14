from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from menu.serializers import CategorySerializer


class MenuI18nSerializerTests(SimpleTestCase):
    def _request(self, path="/api/categories/?lang=fr", *, accept_language="", max_languages=2):
        request = APIRequestFactory().get(path, HTTP_ACCEPT_LANGUAGE=accept_language)
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=max_languages))
        return request

    def test_localized_text_prefers_query_locale(self):
        serializer = CategorySerializer(context={"request": self._request("/api/categories/?lang=fr")})
        value = serializer._localized_text("Salad", {"fr": "Salade", "ar": "سلطة"})
        self.assertEqual(value, "Salade")

    def test_localized_text_uses_accept_language_when_query_missing(self):
        serializer = CategorySerializer(
            context={"request": self._request("/api/categories/", accept_language="fr-CA,fr;q=0.9,en;q=0.7")}
        )
        value = serializer._localized_text("Soup", {"fr": "Soupe"})
        self.assertEqual(value, "Soupe")

    def test_localized_text_falls_back_to_base_text(self):
        serializer = CategorySerializer(context={"request": self._request("/api/categories/?lang=ar")})
        value = serializer._localized_text("Burger", {"fr": "Burger FR"})
        self.assertEqual(value, "Burger")

    def test_localized_text_disabled_for_authenticated_editor_context(self):
        request = self._request("/api/categories/?lang=fr")
        request.user = SimpleNamespace(is_authenticated=True)
        serializer = CategorySerializer(context={"request": request})
        value = serializer._localized_text("Salad", {"fr": "Salade"})
        self.assertEqual(value, "Salad")

    def test_localized_text_can_be_forced_for_authenticated_context(self):
        request = self._request("/api/categories/?lang=fr&force_locale=1")
        request.user = SimpleNamespace(is_authenticated=True)
        serializer = CategorySerializer(context={"request": request})
        value = serializer._localized_text("Salad", {"fr": "Salade"})
        self.assertEqual(value, "Salade")

    def test_validate_name_i18n_rejects_invalid_locale(self):
        serializer = CategorySerializer(context={"request": self._request()})
        with self.assertRaisesMessage(ValidationError, "Category name translation locale must be like 'en', 'fr', or 'ar'."):
            serializer.validate_name_i18n({"french": "Boissons"})

    def test_validate_name_i18n_enforces_plan_limit(self):
        serializer = CategorySerializer(context={"request": self._request(max_languages=1)})
        with self.assertRaisesMessage(ValidationError, "Current plan supports up to 1 translated language entries for Category name."):
            serializer.validate_name_i18n({"fr": "Desserts", "ar": "حلويات"})
