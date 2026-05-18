from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from menu.serializers import TableLinkSerializer


def _qs_mock(slugs):
    """Return a mock queryset whose .values_list('slug', flat=True) returns `slugs`."""
    qs = Mock()
    qs.values_list.return_value = list(slugs)
    # Support the .exclude(pk=...) chain used when instance_id is provided
    qs.exclude.return_value = qs
    return qs


class TableLinkSerializerTests(SimpleTestCase):
    def test_validate_label(self):
        serializer = TableLinkSerializer()
        self.assertEqual(serializer.validate_label(" Table 4 "), "Table 4")

    def test_validate_slug_normalizes(self):
        serializer = TableLinkSerializer()
        self.assertEqual(serializer.validate_slug("VIP Corner"), "vip-corner")

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_returns_first_candidate_when_no_collision(self, table_objects):
        """When the base slug is free, return it as-is (no suffix)."""
        table_objects.filter.return_value = _qs_mock([])

        serializer = TableLinkSerializer()
        resolved = serializer._resolve_unique_slug("table-4")
        self.assertEqual(resolved, "table-4")
        # Single DB round-trip — filter called exactly once
        table_objects.filter.assert_called_once()

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_adds_suffix_on_collision(self, table_objects):
        """When base slug already exists, return base-2."""
        table_objects.filter.return_value = _qs_mock(["table-1"])

        serializer = TableLinkSerializer()
        resolved = serializer._resolve_unique_slug("table-1")
        self.assertEqual(resolved, "table-1-2")
        # Still only one DB round-trip
        table_objects.filter.assert_called_once()

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_skips_multiple_collisions(self, table_objects):
        """When base and base-2 both exist, return base-3."""
        table_objects.filter.return_value = _qs_mock(["table-3", "table-3-2"])

        serializer = TableLinkSerializer()
        resolved = serializer._resolve_unique_slug("table-3")
        self.assertEqual(resolved, "table-3-3")

    @patch("menu.serializers.TableLink.objects")
    def test_resolve_unique_slug_excludes_own_pk_on_update(self, table_objects):
        """When instance_id is given, the query excludes that pk."""
        qs = _qs_mock([])
        table_objects.filter.return_value = qs

        serializer = TableLinkSerializer()
        serializer._resolve_unique_slug("my-table", instance_id=42)

        qs.exclude.assert_called_once_with(pk=42)
