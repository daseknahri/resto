"""
Unit tests for private helper functions in menu/views.py:
  - _filter_by_reference
  - _slot_floor
  - _build_day_slots
  - _make_unique_slug (with mocked model)

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from datetime import datetime, date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytz
from django.test import SimpleTestCase

from menu.views import (
    _filter_by_reference,
    _slot_floor,
    _build_day_slots,
    _make_unique_slug,
)


# ══════════════════════════════════════════════════════════════════════════════
# _filter_by_reference
# ══════════════════════════════════════════════════════════════════════════════

class FilterByReferenceTests(SimpleTestCase):
    def _qs(self):
        qs = MagicMock()
        qs.filter.return_value = qs
        return qs

    def test_empty_value_returns_qs_unchanged(self):
        qs = self._qs()
        result = _filter_by_reference(qs, "", id_field="category_id", slug_field="category__slug")
        self.assertIs(result, qs)
        qs.filter.assert_not_called()

    def test_none_returns_qs_unchanged(self):
        qs = self._qs()
        result = _filter_by_reference(qs, None, id_field="category_id", slug_field="category__slug")
        self.assertIs(result, qs)
        qs.filter.assert_not_called()

    def test_numeric_value_filters_by_id(self):
        qs = self._qs()
        _filter_by_reference(qs, "42", id_field="category_id", slug_field="category__slug")
        qs.filter.assert_called_once_with(category_id=42)

    def test_slug_value_filters_by_slug_field(self):
        qs = self._qs()
        _filter_by_reference(qs, "pasta", id_field="category_id", slug_field="category__slug")
        qs.filter.assert_called_once_with(**{"category__slug": "pasta"})

    def test_whitespace_stripped_before_decision(self):
        qs = self._qs()
        _filter_by_reference(qs, "  7  ", id_field="cat_id", slug_field="cat__slug")
        qs.filter.assert_called_once_with(cat_id=7)

    def test_mixed_alphanumeric_is_slug(self):
        qs = self._qs()
        _filter_by_reference(qs, "cat-2", id_field="cat_id", slug_field="cat__slug")
        qs.filter.assert_called_once_with(**{"cat__slug": "cat-2"})


# ══════════════════════════════════════════════════════════════════════════════
# _slot_floor
# ══════════════════════════════════════════════════════════════════════════════

class SlotFloorTests(SimpleTestCase):
    def test_on_boundary_unchanged(self):
        dt = datetime(2024, 6, 1, 9, 0, 0)
        result = _slot_floor(dt, 30)
        self.assertEqual(result, datetime(2024, 6, 1, 9, 0, 0))

    def test_floors_to_previous_slot_30min(self):
        dt = datetime(2024, 6, 1, 9, 17, 45)
        result = _slot_floor(dt, 30)
        self.assertEqual(result, datetime(2024, 6, 1, 9, 0, 0))

    def test_floors_to_previous_slot_60min(self):
        dt = datetime(2024, 6, 1, 14, 45, 0)
        result = _slot_floor(dt, 60)
        self.assertEqual(result, datetime(2024, 6, 1, 14, 0, 0))

    def test_seconds_and_microseconds_cleared(self):
        dt = datetime(2024, 6, 1, 10, 5, 30, 500000)
        result = _slot_floor(dt, 15)
        self.assertEqual(result.second, 0)
        self.assertEqual(result.microsecond, 0)

    def test_slot_15_minutes(self):
        dt = datetime(2024, 6, 1, 11, 22, 0)
        result = _slot_floor(dt, 15)
        self.assertEqual(result, datetime(2024, 6, 1, 11, 15, 0))

    def test_midnight_boundary(self):
        dt = datetime(2024, 6, 1, 0, 29, 0)
        result = _slot_floor(dt, 30)
        self.assertEqual(result, datetime(2024, 6, 1, 0, 0, 0))


# ══════════════════════════════════════════════════════════════════════════════
# _build_day_slots
# ══════════════════════════════════════════════════════════════════════════════

class BuildDaySlotsTests(SimpleTestCase):
    UTC = pytz.UTC

    def test_returns_list(self):
        slots = _build_day_slots(date(2024, 6, 1), 30, self.UTC)
        self.assertIsInstance(slots, list)

    def test_30_min_slots_from_9_to_22(self):
        # 9:00 to 22:00 with 30-min slots = 26 slots
        slots = _build_day_slots(date(2024, 6, 1), 30, self.UTC)
        self.assertEqual(len(slots), 26)

    def test_60_min_slots_from_9_to_22(self):
        # 9:00 to 22:00 with 60-min slots = 13 slots
        slots = _build_day_slots(date(2024, 6, 1), 60, self.UTC)
        self.assertEqual(len(slots), 13)

    def test_first_slot_is_9am(self):
        slots = _build_day_slots(date(2024, 6, 1), 30, self.UTC)
        self.assertEqual(slots[0].hour, 9)
        self.assertEqual(slots[0].minute, 0)

    def test_last_slot_before_10pm(self):
        slots = _build_day_slots(date(2024, 6, 1), 30, self.UTC)
        self.assertLess(slots[-1].hour, 22)

    def test_all_slots_are_timezone_aware(self):
        slots = _build_day_slots(date(2024, 6, 1), 30, self.UTC)
        for s in slots:
            self.assertIsNotNone(s.tzinfo)

    def test_slots_on_correct_date(self):
        target = date(2024, 12, 25)
        slots = _build_day_slots(target, 60, self.UTC)
        for s in slots:
            self.assertEqual(s.date(), target)

    def test_slot_spacing_matches_minutes(self):
        slots = _build_day_slots(date(2024, 6, 1), 45, self.UTC)
        for i in range(1, len(slots)):
            diff = (slots[i] - slots[i - 1]).total_seconds()
            self.assertEqual(diff, 45 * 60)


# ══════════════════════════════════════════════════════════════════════════════
# _make_unique_slug
# ══════════════════════════════════════════════════════════════════════════════

class MakeUniqueSlugTests(SimpleTestCase):
    def _model_class(self, existing_slugs):
        """Return a mock model class whose .objects.filter().exists() reflects given slugs."""
        model = MagicMock()
        def filter_side(slug):
            qs = MagicMock()
            qs.exists.return_value = slug in existing_slugs
            return qs
        model.objects.filter.side_effect = lambda **kw: filter_side(kw.get("slug", ""))
        return model

    def test_no_collision_returns_slugified_name(self):
        model = self._model_class(set())
        result = _make_unique_slug("My Dish", model)
        self.assertEqual(result, "my-dish")

    def test_collision_appends_suffix(self):
        model = self._model_class({"my-dish"})
        result = _make_unique_slug("My Dish", model)
        self.assertEqual(result, "my-dish-1")

    def test_multiple_collisions_increment(self):
        model = self._model_class({"my-dish", "my-dish-1"})
        result = _make_unique_slug("My Dish", model)
        self.assertEqual(result, "my-dish-2")

    def test_empty_name_uses_item_fallback(self):
        model = self._model_class(set())
        result = _make_unique_slug("", model)
        self.assertEqual(result, "item")

    def test_respects_max_length(self):
        model = self._model_class(set())
        result = _make_unique_slug("a" * 300, model, max_length=50)
        self.assertLessEqual(len(result), 50)
