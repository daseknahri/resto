"""Onboarding publish gate counts only CUSTOMER-VISIBLE menu content (fresh publish).

ProfileSerializer.validate used to count ``Category(is_published=True)`` and
``Dish(is_published=True, category__is_published=True)`` only — ignoring the category's
paused flag and the parent super-category's published/paused flags. An owner could therefore
publish a menu whose only section was unpublished or paused: "live", but nothing a customer
can see. A FRESH (OFF→ON) publish now counts with ``menu.visibility`` — the exact customer
filter the public menu applies — while an already-published profile keeps the legacy check so
the wizard's full-profile PUTs (``is_menu_published=True`` round-trips) aren't newly blocked.

SimpleTestCase + an in-memory fake manager (no DB). Run with DJANGO_DEBUG=True.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import serializers

from menu.views import CategoryViewSet, DishViewSet
from menu.visibility import CUSTOMER_VISIBLE_CATEGORY_FILTER, CUSTOMER_VISIBLE_DISH_FILTER
from tenancy.serializers import ProfileSerializer


def _inst(**over):
    """A minimal stub Profile carrying the attributes ProfileSerializer.validate reads."""
    base = dict(is_menu_temporarily_disabled=False, menu_disabled_note="",
                is_menu_published=False, city="", lat=None, lng=None, directory_opt_in=False)
    base.update(over)
    return SimpleNamespace(**base)


def _menu(*, section_published=True, section_paused=False, category_published=True,
          category_paused=False, dish_published=True):
    """One super-category → one category → one dish, as nested dicts."""
    section = {"is_published": section_published, "is_temporarily_disabled": section_paused}
    category = {"is_published": category_published, "is_temporarily_disabled": category_paused,
                "super_category": section}
    dish = {"is_published": dish_published, "category": category}
    return [category], [dish]


def _resolve(row, path):
    for part in path.split("__"):
        row = row[part]
    return row


def _manager(rows):
    """Fake ``Model.objects`` whose ``.filter(**exact_lookups).count()`` evaluates over rows."""
    def _filter(**lookups):
        matched = [r for r in rows if all(_resolve(r, k) == v for k, v in lookups.items())]
        return SimpleNamespace(count=lambda: len(matched))
    manager = MagicMock()
    manager.filter.side_effect = _filter
    return manager


class PublishGateVisibilityTests(SimpleTestCase):
    def _validate(self, attrs, *, instance, categories, dishes):
        with patch("menu.models.Category") as mock_cat, patch("menu.models.Dish") as mock_dish:
            mock_cat.objects = _manager(categories)
            mock_dish.objects = _manager(dishes)
            return ProfileSerializer(instance=instance).validate(attrs)

    # ── Regression: a fresh publish of an invisible menu is rejected ─────────────────
    def test_fresh_publish_rejected_when_only_section_is_paused(self):
        categories, dishes = _menu(section_paused=True)
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._validate({"is_menu_published": True}, instance=_inst(),
                           categories=categories, dishes=dishes)
        self.assertIn("is_menu_published", ctx.exception.detail)

    def test_fresh_publish_rejected_when_only_section_is_unpublished(self):
        categories, dishes = _menu(section_published=False)
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._validate({"is_menu_published": True}, instance=_inst(),
                           categories=categories, dishes=dishes)
        self.assertIn("is_menu_published", ctx.exception.detail)

    def test_fresh_publish_rejected_when_only_category_is_paused(self):
        categories, dishes = _menu(category_paused=True)
        with self.assertRaises(serializers.ValidationError) as ctx:
            self._validate({"is_menu_published": True}, instance=_inst(),
                           categories=categories, dishes=dishes)
        self.assertIn("is_menu_published", ctx.exception.detail)

    def test_fresh_publish_with_no_instance_uses_visibility_too(self):
        categories, dishes = _menu(section_paused=True)
        with self.assertRaises(serializers.ValidationError):
            self._validate({"is_menu_published": True}, instance=None,
                           categories=categories, dishes=dishes)

    # ── Guards: what must keep working ───────────────────────────────────────────────
    def test_fresh_publish_with_visible_content_passes(self):
        categories, dishes = _menu()
        out = self._validate({"is_menu_published": True}, instance=_inst(),
                             categories=categories, dishes=dishes)
        self.assertTrue(out["is_menu_published"])

    def test_fresh_publish_still_rejects_an_unpublished_dish(self):
        categories, dishes = _menu(dish_published=False)
        with self.assertRaises(serializers.ValidationError):
            self._validate({"is_menu_published": True}, instance=_inst(),
                           categories=categories, dishes=dishes)

    def test_already_published_unrelated_save_is_not_newly_blocked(self):
        # The wizard PUTs the whole profile, so is_menu_published=True round-trips on every
        # save. A published menu whose section was later paused must still save its phone.
        categories, dishes = _menu(section_paused=True)
        out = self._validate({"is_menu_published": True, "phone": "+212600000000"},
                             instance=_inst(is_menu_published=True),
                             categories=categories, dishes=dishes)
        self.assertEqual(out["phone"], "+212600000000")

    def test_already_published_keeps_the_legacy_empty_menu_check(self):
        # Unchanged behavior: a published profile with no published category still 400s.
        categories, dishes = _menu(category_published=False)
        with self.assertRaises(serializers.ValidationError):
            self._validate({"is_menu_published": True},
                           instance=_inst(is_menu_published=True),
                           categories=categories, dishes=dishes)

    def test_unpublished_save_runs_no_menu_count(self):
        with patch("menu.models.Category") as mock_cat, patch("menu.models.Dish") as mock_dish:
            ProfileSerializer(instance=_inst()).validate({"phone": "+212600000000"})
            mock_cat.objects.filter.assert_not_called()
            mock_dish.objects.filter.assert_not_called()


class VisibilityPredicateParityTests(SimpleTestCase):
    """menu.visibility must stay byte-identical to the public menu's own customer filter,
    so the publish gate counts exactly what an anonymous customer is served."""

    def _customer_filter(self, viewset_cls, model_name):
        with patch(f"menu.views.{model_name}") as mock_model:
            base = MagicMock()
            mock_model.objects.select_related.return_value.prefetch_related.return_value.all.return_value = base
            viewset = viewset_cls()
            viewset.request = SimpleNamespace(method="GET", query_params={})
            with patch.object(viewset_cls, "_can_preview_unpublished", return_value=False):
                viewset.get_queryset()
        return base.filter.call_args.kwargs

    def test_category_predicate_matches_category_viewset(self):
        self.assertEqual(self._customer_filter(CategoryViewSet, "Category"), CUSTOMER_VISIBLE_CATEGORY_FILTER)

    def test_dish_predicate_matches_dish_viewset(self):
        self.assertEqual(self._customer_filter(DishViewSet, "Dish"), CUSTOMER_VISIBLE_DISH_FILTER)
