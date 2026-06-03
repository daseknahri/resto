"""Tests for the check_schema_health management command.

Unit-level (SimpleTestCase + a mocked DB cursor -- no real DB). The "expected"
columns come from the real models; the mock controls what the DB "actually" has,
so we can simulate a recorded-but-not-applied migration (a missing column).
"""
from unittest.mock import MagicMock, patch

from django.apps import apps as django_apps
from django.core.management import call_command
from django.test import SimpleTestCase

from accounts.management.commands import check_schema_health as cmd


def _healthy_columns():
    """Map db_table -> set(columns) that exactly matches every critical model."""
    out = {}
    for app_label, model_name in cmd.CRITICAL_MODELS:
        model = django_apps.get_model(app_label, model_name)
        out[model._meta.db_table] = {f.column for f in model._meta.local_concrete_fields}
    return out


def _mock_cursor_cm(columns_by_table):
    """A context-manager mock whose cursor answers information_schema queries
    from `columns_by_table`, keyed on the table name passed as a query param."""
    cur = MagicMock()
    state = {"table": None}

    def _execute(sql, params=None):
        state["table"] = params[0] if params else None

    def _fetchall():
        return [(c,) for c in columns_by_table.get(state["table"], set())]

    cur.execute.side_effect = _execute
    cur.fetchall.side_effect = _fetchall

    cm = MagicMock()
    cm.__enter__.return_value = cur
    cm.__exit__.return_value = False
    return cm


def _fake_connection(columns_by_table):
    """A stand-in for django.db.connection whose .cursor() yields the mock."""
    conn = MagicMock()
    conn.cursor.return_value = _mock_cursor_cm(columns_by_table)
    return conn


class CheckSchemaHealthTests(SimpleTestCase):
    def test_healthy_schema_succeeds(self):
        cols = _healthy_columns()
        with patch.object(cmd, "connection", _fake_connection(cols)):
            # Should not raise.
            call_command("check_schema_health")

    def test_missing_column_exits_nonzero(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[wt] = cols[wt] - {"idempotency_key"}  # simulate the prod bug
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit) as ctx:
                call_command("check_schema_health")
            self.assertEqual(ctx.exception.code, 1)

    def test_missing_table_exits_nonzero(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[wt] = set()  # table entirely absent
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit):
                call_command("check_schema_health")

    def test_warn_only_does_not_exit(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[wt] = cols[wt] - {"idempotency_key"}
        with patch.object(cmd, "connection", _fake_connection(cols)):
            # Drift present, but --warn-only must not raise.
            call_command("check_schema_health", "--warn-only")
