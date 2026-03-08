from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

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
