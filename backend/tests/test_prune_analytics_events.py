from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from menu.management.commands.prune_analytics_events import Command


@contextmanager
def passthrough_context(_schema_name):
    yield


class PruneAnalyticsEventsCommandTests(SimpleTestCase):
    def test_rejects_invalid_days(self):
        cmd = Command()
        with self.assertRaises(CommandError):
            cmd.handle(days=0, tenant="", dry_run=False)

    @patch("menu.management.commands.prune_analytics_events.schema_context", side_effect=passthrough_context)
    @patch("menu.management.commands.prune_analytics_events.AnalyticsEvent")
    @patch("menu.management.commands.prune_analytics_events.Tenant")
    def test_dry_run_does_not_delete_rows(self, tenant_mock, analytics_event_mock, _schema_mock):
        tenant_mock.objects.filter.return_value = [SimpleNamespace(slug="demo", schema_name="demo")]
        stale_qs = Mock()
        stale_qs.count.return_value = 7
        analytics_event_mock.objects.filter.return_value = stale_qs

        cmd = Command()
        cmd.handle(days=30, tenant="demo", dry_run=True)

        stale_qs.count.assert_called_once()
        stale_qs.delete.assert_not_called()

    @patch("menu.management.commands.prune_analytics_events.schema_context", side_effect=passthrough_context)
    @patch("menu.management.commands.prune_analytics_events.AnalyticsEvent")
    @patch("menu.management.commands.prune_analytics_events.Tenant")
    def test_delete_mode_removes_rows(self, tenant_mock, analytics_event_mock, _schema_mock):
        tenant_mock.objects.all.return_value = [SimpleNamespace(slug="demo", schema_name="demo")]
        stale_qs = Mock()
        stale_qs.count.return_value = 3
        analytics_event_mock.objects.filter.return_value = stale_qs

        cmd = Command()
        cmd.handle(days=90, tenant="", dry_run=False)

        stale_qs.delete.assert_called_once()
