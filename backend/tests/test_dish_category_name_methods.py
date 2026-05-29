"""
Unit tests for the SerializerMethodField helpers:
  - DishSerializer.get_category_name
  - DishSerializer.get_super_category_name
  - CategorySerializer.get_super_category_name

All three delegate to self._localized_text(), so they are tested both for
the None-guard paths and for the locale-resolution paths.

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.serializers import CategorySerializer, DishSerializer


# ── helpers ───────────────────────────────────────────────────────────────────

def _dish_ser(lang=None):
    """DishSerializer with optional lang query-param in context."""
    if lang:
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=2)),
            query_params={"lang": lang},
            headers={},
            META={},
        )
    else:
        request = None
    return DishSerializer(context={"request": request})


def _cat_ser(lang=None):
    """CategorySerializer with optional lang query-param in context."""
    if lang:
        request = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=2)),
            query_params={"lang": lang},
            headers={},
            META={},
        )
    else:
        request = None
    return CategorySerializer(context={"request": request})


def _category(name="Mains", name_i18n=None, super_category=None):
    return SimpleNamespace(name=name, name_i18n=name_i18n or {}, super_category=super_category)


def _super_category(name="Hot Dishes", name_i18n=None):
    return SimpleNamespace(name=name, name_i18n=name_i18n or {})


def _dish(category=None):
    return SimpleNamespace(category=category)


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.get_category_name
# ══════════════════════════════════════════════════════════════════════════════

class DishGetCategoryNameTests(SimpleTestCase):

    def test_no_category_attr_returns_empty_string(self):
        """Instance without a category attribute returns ""."""
        instance = SimpleNamespace()  # no category attr
        self.assertEqual(_dish_ser().get_category_name(instance), "")

    def test_category_none_returns_empty_string(self):
        self.assertEqual(_dish_ser().get_category_name(_dish(category=None)), "")

    def test_category_name_returned_when_no_i18n(self):
        cat = _category(name="Starters", name_i18n={})
        self.assertEqual(_dish_ser().get_category_name(_dish(cat)), "Starters")

    def test_category_name_localized_when_lang_matches(self):
        cat = _category(name="Starters", name_i18n={"fr": "Entrées"})
        self.assertEqual(_dish_ser(lang="fr").get_category_name(_dish(cat)), "Entrées")

    def test_category_name_base_returned_when_no_locale_match(self):
        cat = _category(name="Starters", name_i18n={"ar": "مقبلات"})
        # lang=de is not in translations, base is non-empty → use base
        self.assertEqual(_dish_ser(lang="de").get_category_name(_dish(cat)), "Starters")

    def test_category_name_empty_base_falls_back_to_first_translation(self):
        """If base is empty and locale doesn't match, first sorted translation used."""
        cat = _category(name="", name_i18n={"fr": "Entrées", "ar": "مقبلات"})
        # sorted keys: ar, fr → first is "ar"
        result = _dish_ser(lang="de").get_category_name(_dish(cat))
        self.assertEqual(result, "مقبلات")


# ══════════════════════════════════════════════════════════════════════════════
# DishSerializer.get_super_category_name
# ══════════════════════════════════════════════════════════════════════════════

class DishGetSuperCategoryNameTests(SimpleTestCase):

    def test_no_category_returns_empty_string(self):
        self.assertEqual(_dish_ser().get_super_category_name(_dish(category=None)), "")

    def test_category_has_no_super_category_returns_empty_string(self):
        cat = _category(super_category=None)
        self.assertEqual(_dish_ser().get_super_category_name(_dish(cat)), "")

    def test_super_category_name_returned_when_no_i18n(self):
        sc = _super_category(name="Hot Dishes", name_i18n={})
        cat = _category(super_category=sc)
        self.assertEqual(_dish_ser().get_super_category_name(_dish(cat)), "Hot Dishes")

    def test_super_category_name_localized_when_lang_matches(self):
        sc = _super_category(name="Hot Dishes", name_i18n={"ar": "أطباق ساخنة"})
        cat = _category(super_category=sc)
        self.assertEqual(_dish_ser(lang="ar").get_super_category_name(_dish(cat)), "أطباق ساخنة")

    def test_super_category_name_base_when_no_locale_match(self):
        sc = _super_category(name="Hot Dishes", name_i18n={"fr": "Plats chauds"})
        cat = _category(super_category=sc)
        self.assertEqual(_dish_ser(lang="de").get_super_category_name(_dish(cat)), "Hot Dishes")


# ══════════════════════════════════════════════════════════════════════════════
# CategorySerializer.get_super_category_name
# ══════════════════════════════════════════════════════════════════════════════

class CategoryGetSuperCategoryNameTests(SimpleTestCase):

    def _cat_instance(self, super_category=None):
        return SimpleNamespace(super_category=super_category)

    def test_no_super_category_returns_empty_string(self):
        inst = self._cat_instance(super_category=None)
        self.assertEqual(_cat_ser().get_super_category_name(inst), "")

    def test_super_category_name_returned(self):
        sc = _super_category(name="Seasonal", name_i18n={})
        inst = self._cat_instance(super_category=sc)
        self.assertEqual(_cat_ser().get_super_category_name(inst), "Seasonal")

    def test_super_category_name_localized(self):
        sc = _super_category(name="Seasonal", name_i18n={"fr": "Saisonniers"})
        inst = self._cat_instance(super_category=sc)
        self.assertEqual(_cat_ser(lang="fr").get_super_category_name(inst), "Saisonniers")

    def test_super_category_no_locale_match_uses_base(self):
        sc = _super_category(name="Seasonal", name_i18n={"ar": "موسمي"})
        inst = self._cat_instance(super_category=sc)
        self.assertEqual(_cat_ser(lang="de").get_super_category_name(inst), "Seasonal")
