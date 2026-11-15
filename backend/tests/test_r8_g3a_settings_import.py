"""Run 8 G3a — A2-13: the settings-import summary discloses the wipe.

_apply_tenant_settings_import counts the existing menu/table rows BEFORE the
delete (inside the transaction) and reports replaces_menu / existing_menu /
replaces_tables / existing_table_links, so the dry-run review modal can warn
the admin instead of showing incoming counts only. Dry-run (commit=False)
rolls back — the counts are still the pre-import state.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from sales.views import _apply_tenant_settings_import


def _ctx():
    ctx = MagicMock()
    ctx.__enter__ = lambda s: None
    ctx.__exit__ = lambda s, *a: None
    return ctx


class SettingsImportWipeSummaryTests(SimpleTestCase):
    def _apply(self, payload, commit=True):
        tenant = MagicMock()
        tenant.schema_name = "tenant1"
        tenant.id = 1
        return _apply_tenant_settings_import(tenant=tenant, payload=payload, commit=commit)

    @patch("sales.views.transaction")
    @patch("sales.views.schema_context", return_value=_ctx())
    @patch("sales.views.get_or_create_default_super_category")
    @patch("menu.models.SuperCategory.objects")
    @patch("menu.models.TableLink.objects")
    @patch("menu.models.ComboComponent.objects")
    @patch("menu.models.DishOption.objects")
    @patch("menu.models.Dish.objects")
    @patch("menu.models.Category.objects")
    def test_categories_payload_reports_existing_menu(
        self, mock_cat_objs, mock_dish_objs, mock_opt_objs, mock_combo_objs,
        mock_table_objs, mock_super_objs, mock_default_sc, mock_schema, mock_tx,
    ):
        mock_tx.atomic.return_value = _ctx()
        mock_cat_objs.count.return_value = 5
        mock_dish_objs.count.return_value = 42
        mock_opt_objs.count.return_value = 17
        mock_combo_objs.count.return_value = 3
        mock_super_objs.all.return_value = []
        mock_default_sc.return_value = MagicMock(slug="default")

        summary = self._apply({
            "categories": [{"name": "Starters", "dishes": [{"name": "Soup", "price": "5"}]}],
        })

        self.assertTrue(summary["replaces_menu"])
        self.assertEqual(summary["existing_menu"], {
            "categories": 5, "dishes": 42, "options": 17, "combos": 3,
        })
        self.assertEqual(summary["categories"], 1)
        self.assertEqual(summary["dishes"], 1)
        # The wipe ran before the re-import.
        mock_cat_objs.all.return_value.delete.assert_called_once()
        mock_dish_objs.all.return_value.delete.assert_called_once()

    @patch("sales.views.transaction")
    @patch("sales.views.schema_context", return_value=_ctx())
    @patch("menu.models.TableLink.objects")
    def test_table_links_payload_reports_existing_table_links(
        self, mock_table_objs, mock_schema, mock_tx
    ):
        mock_tx.atomic.return_value = _ctx()
        mock_table_objs.count.return_value = 8

        summary = self._apply({"table_links": [{"label": "T1"}]})

        self.assertTrue(summary["replaces_tables"])
        self.assertEqual(summary["existing_table_links"], 8)
        self.assertEqual(summary["table_links"], 1)
        self.assertNotIn("replaces_menu", summary)

    @patch("sales.views.transaction")
    @patch("sales.views.schema_context", return_value=_ctx())
    @patch("menu.models.TableLink.objects")
    def test_profile_only_payload_reports_no_wipe(
        self, mock_table_objs, mock_schema, mock_tx
    ):
        mock_tx.atomic.return_value = _ctx()
        with patch("sales.views.Profile") as mock_profile, \
             patch("sales.views.ProfileSerializer") as mock_ser:
            mock_profile.objects.get_or_create.return_value = (MagicMock(), True)
            summary = self._apply({"profile": {"name": "Chez Test"}})

        self.assertNotIn("replaces_menu", summary)
        self.assertNotIn("replaces_tables", summary)
        self.assertTrue(summary["profile_updated"])
