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
    """Map (schema, db_table) -> set(columns) matching every critical model.

    Public tables under "public"; tenant tables under the fake tenant schema
    "resto1" (Wave M M-20)."""
    out = {}
    for app_label, model_name in cmd.CRITICAL_MODELS:
        model = django_apps.get_model(app_label, model_name)
        out[("public", model._meta.db_table)] = {f.column for f in model._meta.local_concrete_fields}
    for app_label, model_name in cmd.TENANT_CRITICAL_MODELS:
        model = django_apps.get_model(app_label, model_name)
        out[("resto1", model._meta.db_table)] = {f.column for f in model._meta.local_concrete_fields}
    return out


def _mock_cursor_cm(columns_by_table):
    """A context-manager mock whose cursor answers information_schema queries
    from `columns_by_table`, keyed on the (schema, table) query params."""
    cur = MagicMock()
    state = {"key": None}

    def _execute(sql, params=None):
        state["key"] = tuple(params) if params else None

    def _fetchall():
        return [(c,) for c in columns_by_table.get(state["key"], set())]

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
    def setUp(self):
        # The command enumerates active tenant schemas from the DB — stub it
        # to one fake schema in these unit tests (Wave M M-20).
        self._schemas = patch.object(
            cmd, "_active_tenant_schemas", return_value=["resto1"])
        self._schemas.start()
        self.addCleanup(self._schemas.stop)

    def test_healthy_schema_succeeds(self):
        cols = _healthy_columns()
        with patch.object(cmd, "connection", _fake_connection(cols)):
            # Should not raise.
            call_command("check_schema_health")

    def test_delivery_job_and_topup_attempt_are_checked(self):
        """Wave M M-20: the two new public models are in CRITICAL_MODELS, so a
        missing column on either fails the deploy."""
        self.assertIn(("accounts", "DeliveryJob"), cmd.CRITICAL_MODELS)
        self.assertIn(("accounts", "CustomerTopUpAttempt"), cmd.CRITICAL_MODELS)
        cols = _healthy_columns()
        dj = django_apps.get_model("accounts", "DeliveryJob")._meta.db_table
        cols[("public", dj)] = cols[("public", dj)] - {"food_ready_at"}
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit) as ctx:
                call_command("check_schema_health")
            self.assertEqual(ctx.exception.code, 1)

    def test_tenant_schema_missing_column_exits_nonzero(self):
        """Wave M M-20: a missing column on menu_order in ONE tenant schema
        fails the deploy (the old public-only check stayed green for this)."""
        cols = _healthy_columns()
        order_table = django_apps.get_model("menu", "Order")._meta.db_table
        cols[("resto1", order_table)] = cols[("resto1", order_table)] - {"delivery_code"}
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit) as ctx:
                call_command("check_schema_health")
            self.assertEqual(ctx.exception.code, 1)

    def test_tenant_schema_missing_table_exits_nonzero(self):
        cols = _healthy_columns()
        dish_table = django_apps.get_model("menu", "Dish")._meta.db_table
        cols[("resto1", dish_table)] = set()
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit):
                call_command("check_schema_health")

    def test_missing_column_exits_nonzero(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[("public", wt)] = cols[("public", wt)] - {"idempotency_key"}  # simulate the prod bug
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit) as ctx:
                call_command("check_schema_health")
            self.assertEqual(ctx.exception.code, 1)

    def test_missing_table_exits_nonzero(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[("public", wt)] = set()  # table entirely absent
        with patch.object(cmd, "connection", _fake_connection(cols)):
            with self.assertRaises(SystemExit):
                call_command("check_schema_health")

    def test_warn_only_does_not_exit(self):
        cols = _healthy_columns()
        wt = django_apps.get_model("accounts", "WalletTransaction")._meta.db_table
        cols[("public", wt)] = cols[("public", wt)] - {"idempotency_key"}
        with patch.object(cmd, "connection", _fake_connection(cols)):
            # Drift present, but --warn-only must not raise.
            call_command("check_schema_health", "--warn-only")
