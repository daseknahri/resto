"""Admin tenant-settings import must not die on a tenant that has combo dishes.

The import replaces the whole menu (deletes every Dish, then re-creates from the payload).
ComboComponent.component is on_delete=PROTECT, so deleting the dishes while any combo
existed raised ProtectedError — reported as a misleading 409 "duplicate slug or constraint
violation". The combo links must be deleted before the dishes. Mock-based (no DB).
"""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from sales.views import _apply_tenant_settings_import


@contextmanager
def _noop_ctx(*args, **kwargs):
    yield


@patch("sales.views.transaction")
@patch("sales.views.schema_context", _noop_ctx)
class SettingsImportComboTests(SimpleTestCase):
    def setUp(self):
        # One shared parent mock records the ORDER of the delete() calls across models.
        self.calls = MagicMock()
        self.models = {}
        for name in ("ComboComponent", "DishOption", "Dish", "Category", "TableLink", "SuperCategory"):
            patcher = patch(f"sales.views.{name}")
            model = patcher.start()
            self.addCleanup(patcher.stop)
            self.calls.attach_mock(model.objects.all.return_value.delete, f"{name}_delete")
            self.models[name] = model
        self.models["SuperCategory"].objects.all.return_value = []
        patcher = patch(
            "sales.views.get_or_create_default_super_category",
            return_value=SimpleNamespace(id=1, slug="menu"),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _import(self, payload):
        tenant = SimpleNamespace(id=7, slug="demo", schema_name="demo")
        return _apply_tenant_settings_import(tenant=tenant, payload=payload)

    def test_combo_links_are_deleted_before_the_dishes(self, _tx):
        self._import({"categories": [{"name": "Mains"}]})
        order = [c[0] for c in self.calls.mock_calls if c[0].endswith("_delete")]
        self.assertIn("ComboComponent_delete", order)
        self.assertLess(order.index("ComboComponent_delete"), order.index("Dish_delete"))
