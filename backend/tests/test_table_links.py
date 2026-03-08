from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from menu.serializers import TableLinkSerializer


class TableLinkSerializerTests(SimpleTestCase):
    def test_validate_label(self):
        serializer = TableLinkSerializer()
        self.assertEqual(serializer.validate_label(" Table 4 "), "Table 4")

    def test_validate_slug_normalizes(self):
        serializer = TableLinkSerializer()
        self.assertEqual(serializer.validate_slug("VIP Corner"), "vip-corner")

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_adds_suffix_on_collision(self, table_objects):
        exists_first = Mock()
        exists_first.exists.return_value = True
        exists_second = Mock()
        exists_second.exists.return_value = False
        table_objects.filter.side_effect = [exists_first, exists_second]

        serializer = TableLinkSerializer()
        resolved = serializer._resolve_unique_slug("table-1")
        self.assertEqual(resolved, "table-1-2")

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_returns_first_candidate(self, table_objects):
        exists = Mock()
        exists.exists.return_value = False
        table_objects.filter.return_value = exists

        serializer = TableLinkSerializer()
        resolved = serializer._resolve_unique_slug("table-4")
        self.assertEqual(resolved, "table-4")
