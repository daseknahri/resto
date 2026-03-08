from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class PruneAdminAuditLogsCommandTests(SimpleTestCase):
    def test_rejects_non_positive_days(self):
        with self.assertRaises(CommandError):
            call_command("prune_admin_audit_logs", "--days", "0")

    @patch("sales.management.commands.prune_admin_audit_logs.AdminAuditLog.objects")
    def test_dry_run_reports_count_without_deleting(self, objects):
        queryset = Mock()
        queryset.count.return_value = 12
        objects.filter.return_value = queryset

        stdout = StringIO()
        call_command("prune_admin_audit_logs", "--days", "90", "--dry-run", stdout=stdout)

        self.assertIn("admin_audit_logs older than 90 days: 12", stdout.getvalue())
        queryset.delete.assert_not_called()

    @patch("sales.management.commands.prune_admin_audit_logs.AdminAuditLog.objects")
    def test_deletes_rows_when_not_dry_run(self, objects):
        queryset = Mock()
        queryset.count.return_value = 4
        queryset.delete.return_value = (4, {"sales.AdminAuditLog": 4})
        objects.filter.return_value = queryset

        stdout = StringIO()
        call_command("prune_admin_audit_logs", "--days", "30", stdout=stdout)

        queryset.delete.assert_called_once()
        self.assertIn("Deleted 4 admin audit log row(s)", stdout.getvalue())
