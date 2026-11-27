"""R6-07: the dead per-branch models are gone.

DishBranchState / StaffBranch were deleted (migration 0082): no code read
them, no endpoint ever created a row. These tests pin the deletion:
  - the names are no longer importable from menu.models;
  - the deleting migration's emptiness guard refuses to drop tables that
    still hold rows (deploy-time safety), and passes when they are empty.
"""
import importlib
from unittest.mock import MagicMock

from django.test import SimpleTestCase


class DeadBranchModelsGoneTests(SimpleTestCase):
    def test_dish_branch_state_not_importable(self):
        with self.assertRaises(ImportError):
            from menu.models import DishBranchState  # noqa: F401

    def test_staff_branch_not_importable(self):
        with self.assertRaises(ImportError):
            from menu.models import StaffBranch  # noqa: F401

    def test_branch_itself_still_exists(self):
        from menu.models import Branch
        self.assertTrue(hasattr(Branch, "objects"))


class DeleteMigrationGuardTests(SimpleTestCase):
    def _migration(self):
        return importlib.import_module(
            "menu.migrations.0082_delete_dishbranchstate_staffbranch"
        )

    def _apps(self, has_rows):
        apps = MagicMock()
        model = MagicMock()
        model.objects.exists.return_value = has_rows
        apps.get_model.return_value = model
        return apps

    def test_guard_passes_when_tables_empty(self):
        self._migration().check_empty(self._apps(False), None)

    def test_guard_refuses_when_rows_exist(self):
        with self.assertRaises(RuntimeError):
            self._migration().check_empty(self._apps(True), None)
