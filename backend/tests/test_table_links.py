from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase

from menu.models import TableLink
from menu.serializers import TableLinkSerializer
from menu.views import TableLinkViewSet
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory


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

    def test_update_changes_label_but_keeps_slug(self):
        """POS-UX-41: a rename changes the label; a slug in the payload is ignored."""
        # Real (unsaved) instance: DRF update() walks _meta via
        # get_field_info(); a bare Mock loops forever there (every attr
        # is a new truthy Mock). save() is mocked - no DB touched.
        instance = TableLink(label="Table 1", slug="table-1", position=0)
        instance.save = Mock()
        serializer = TableLinkSerializer()
        serializer.update(instance, {"label": "Renamed", "slug": "hijacked", "position": 0})
        self.assertEqual(instance.label, "Renamed")
        self.assertEqual(instance.slug, "table-1")
        instance.save.assert_called_once()
class DummyTableLinkViewSet(TableLinkViewSet):
    """ViewSet under test with auth off and a stubbed object lookup."""

    permission_classes = [AllowAny]
    test_object = None

    def get_queryset(self):
        return []

    def get_object(self):
        obj = self.__class__.test_object
        if obj is None:
            raise Http404
        return obj


class TableLinkRenameViewSetTests(SimpleTestCase):
    """POS-UX-41: PUT /tables/<id>/ renames the table; the slug (and therefore
    the printed QR URL) never changes; a missing table 404s."""

    def setUp(self):
        self.factory = APIRequestFactory()
        DummyTableLinkViewSet.test_object = None

    def _table(self):
        # Real (unsaved) instance - see note in the serializer test:
        # a bare Mock makes DRF update() loop forever in get_field_info.
        table = TableLink(
            id=5, label="Table 1", slug="table-1", position=0, is_active=True
        )
        table.save = Mock()
        return table

    @patch("menu.serializers.TableLink.objects")
    @patch("menu.serializers.TableLink._meta.default_manager")
    def test_put_rename_changes_label_keeps_slug(self, default_manager, table_objects):
        table_objects.filter.return_value.exclude.return_value.exists.return_value = False
        # DRF builds the slug UniqueValidator from _default_manager, not
        # .objects - without this the validator queries the real DB.
        # (_default_manager itself is a read-only ModelBase property,
        # so patch the Options attribute it reads.)
        default_manager.filter.return_value.exclude.return_value.exists.return_value = False
        table = self._table()
        DummyTableLinkViewSet.test_object = table
        req = self.factory.put(
            "/api/tables/5/",
            {"label": "Table Renamed", "slug": "hijacked", "position": 0, "is_active": True},
            format="json",
        )
        resp = DummyTableLinkViewSet.as_view({"put": "update"})(req, pk=5)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["label"], "Table Renamed")
        self.assertEqual(resp.data["slug"], "table-1")
        self.assertEqual(table.slug, "table-1")
        table.save.assert_called_once()

    def test_rename_of_nonexistent_table_404s(self):
        DummyTableLinkViewSet.test_object = None
        req = self.factory.put(
            "/api/tables/999/",
            {"label": "Ghost", "position": 0, "is_active": True},
            format="json",
        )
        resp = DummyTableLinkViewSet.as_view({"put": "update"})(req, pk=999)
        self.assertEqual(resp.status_code, 404)
