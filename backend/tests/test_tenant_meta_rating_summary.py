"""
Unit tests for TenantMetaSerializer._rating_summary in tenancy/serializers.py.

The static method computes an aggregate over the Rating model:
  - Returns {"average": float rounded to 1dp, "count": int}
  - Returns None for average when there are no ratings (agg["avg"] is None)
  - Returns {"average": None, "count": 0} on any exception

All tests are unit-level (SimpleTestCase — Rating.objects.aggregate is mocked).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from tenancy.serializers import TenantMetaSerializer


class RatingSummaryTests(SimpleTestCase):

    def _call(self, avg=None, total=0):
        """Call _rating_summary with a mocked aggregate result."""
        with patch("menu.models.Rating") as mock_rating_cls:
            mock_rating_cls.objects.aggregate.return_value = {
                "avg": avg,
                "total": total,
            }
            with patch("tenancy.serializers.TenantMetaSerializer._rating_summary",
                       wraps=TenantMetaSerializer._rating_summary):
                return TenantMetaSerializer._rating_summary()

    @patch("menu.models.Rating")
    def test_no_ratings_returns_none_average(self, mock_rating_cls):
        mock_rating_cls.objects.aggregate.return_value = {"avg": None, "total": 0}
        result = TenantMetaSerializer._rating_summary()
        self.assertIsNone(result["average"])
        self.assertEqual(result["count"], 0)

    @patch("menu.models.Rating")
    def test_average_rounded_to_one_decimal_place(self, mock_rating_cls):
        mock_rating_cls.objects.aggregate.return_value = {"avg": 4.666, "total": 3}
        result = TenantMetaSerializer._rating_summary()
        self.assertAlmostEqual(result["average"], 4.7)
        self.assertEqual(result["count"], 3)

    @patch("menu.models.Rating")
    def test_perfect_score(self, mock_rating_cls):
        mock_rating_cls.objects.aggregate.return_value = {"avg": 5.0, "total": 10}
        result = TenantMetaSerializer._rating_summary()
        self.assertEqual(result["average"], 5.0)
        self.assertEqual(result["count"], 10)

    @patch("menu.models.Rating")
    def test_integer_average_returned_as_float(self, mock_rating_cls):
        mock_rating_cls.objects.aggregate.return_value = {"avg": 4, "total": 1}
        result = TenantMetaSerializer._rating_summary()
        self.assertEqual(result["average"], 4.0)

    @patch("menu.models.Rating")
    def test_exception_returns_safe_fallback(self, mock_rating_cls):
        """Any exception during DB access is swallowed → safe fallback returned."""
        mock_rating_cls.objects.aggregate.side_effect = Exception("DB unavailable")
        result = TenantMetaSerializer._rating_summary()
        self.assertIsNone(result["average"])
        self.assertEqual(result["count"], 0)
