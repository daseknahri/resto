"""R6-28: migration 0080's backwards() reverses only what forwards did.

The old backwards() nulled branch on EVERY order and section, then deleted
the default branch — destroying branch attribution the migration never
created. The fixed version nulls only FKs pointing at the backfilled
default branch (slug "main", is_default) and deletes that branch; rows on
any other branch keep theirs.
"""
import importlib
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


def _load_migration():
    return importlib.import_module("menu.migrations.0080_default_branch_backfill")


class Migration0080BackwardsTests(SimpleTestCase):
    def _run_backwards(self, default_branch, schema_name="tenant1"):
        mod = _load_migration()
        branch_cls = MagicMock(name="Branch")
        order_cls = MagicMock(name="Order")
        section_cls = MagicMock(name="TableSection")
        apps = MagicMock()
        apps.get_model.side_effect = lambda _app, name: {
            "Branch": branch_cls,
            "Order": order_cls,
            "TableSection": section_cls,
        }[name]
        branch_cls.objects.filter.return_value.first.return_value = default_branch
        fake_conn = MagicMock()
        fake_conn.schema_name = schema_name
        with patch.object(mod, "connection", fake_conn):
            mod.backwards(apps, MagicMock())
        return branch_cls, order_cls, section_cls

    def test_backwards_nulls_only_default_branch_rows(self):
        default_branch = MagicMock(name="default-branch")
        _, order_cls, section_cls = self._run_backwards(default_branch)
        # Only FKs pointing at the backfilled default branch are nulled —
        # never a blanket .all().update().
        order_cls.objects.filter.assert_called_once_with(branch=default_branch)
        order_cls.objects.filter.return_value.update.assert_called_once_with(
            branch=None
        )
        order_cls.objects.all.assert_not_called()
        section_cls.objects.filter.assert_called_once_with(branch=default_branch)
        section_cls.objects.filter.return_value.update.assert_called_once_with(
            branch=None
        )
        section_cls.objects.all.assert_not_called()
        default_branch.delete.assert_called_once()

    def test_backwards_does_nothing_when_no_default_branch(self):
        _, order_cls, section_cls = self._run_backwards(None)
        order_cls.objects.filter.assert_not_called()
        section_cls.objects.filter.assert_not_called()

    def test_backwards_skips_public_schema(self):
        branch_cls, order_cls, section_cls = self._run_backwards(
            MagicMock(), schema_name="public"
        )
        branch_cls.objects.filter.assert_not_called()
        order_cls.objects.filter.assert_not_called()
        section_cls.objects.filter.assert_not_called()
