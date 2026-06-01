"""
Unit tests for OwnerRatingListView._csv_response in menu/views.py.

The method builds a CSV response from a ratings queryset:
  - Header row: Date, Order Number, Customer, Score, Comment
  - One data row per rating object
  - Returns HttpResponse with text/csv content-type and attachment disposition

All tests are unit-level (SimpleTestCase — the queryset is mocked).
"""
import csv
import io
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from menu.views import OwnerRatingListView


# ── helpers ───────────────────────────────────────────────────────────────────

def _view():
    return OwnerRatingListView.__new__(OwnerRatingListView)


def _rating(
    order_number="ORD-A1B2C3",
    customer_name="John Doe",
    score=5,
    comment="Great!",
    created_at=None,
):
    order = SimpleNamespace(order_number=order_number, customer_name=customer_name)
    dt = created_at or datetime(2026, 1, 15, 12, 30)
    return SimpleNamespace(order=order, score=score, comment=comment, created_at=dt)


def _parse_csv(response):
    # Decode with utf-8-sig so the UTF-8 BOM (if present) is stripped
    # automatically before the CSV is parsed.
    content = response.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content))
    return list(reader)


# ══════════════════════════════════════════════════════════════════════════════
# _csv_response
# ══════════════════════════════════════════════════════════════════════════════

class RatingCsvResponseTests(SimpleTestCase):

    def test_content_type_is_csv(self):
        resp = _view()._csv_response([])
        self.assertIn("text/csv", resp["Content-Type"])

    def test_content_disposition_is_attachment(self):
        resp = _view()._csv_response([])
        disposition = resp["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("ratings.csv", disposition)

    def test_header_row_present(self):
        rows = _parse_csv(_view()._csv_response([]))
        self.assertEqual(rows[0], ["Date", "Order Number", "Customer", "Score", "Comment"])

    def test_empty_queryset_yields_header_only(self):
        rows = _parse_csv(_view()._csv_response([]))
        self.assertEqual(len(rows), 1)

    def test_single_rating_row_written(self):
        r = _rating(order_number="ORD-001", customer_name="Alice", score=4, comment="Good")
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertEqual(len(rows), 2)   # header + 1 data row

    def test_rating_order_number_in_row(self):
        r = _rating(order_number="ORD-XYZ99")
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertIn("ORD-XYZ99", rows[1])

    def test_rating_customer_name_in_row(self):
        r = _rating(customer_name="Jane Smith")
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertIn("Jane Smith", rows[1])

    def test_rating_score_in_row(self):
        r = _rating(score=3)
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertIn("3", rows[1])

    def test_rating_comment_in_row(self):
        r = _rating(comment="Average experience")
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertIn("Average experience", rows[1])

    def test_rating_date_formatted_correctly(self):
        dt = datetime(2026, 3, 22, 8, 5)
        r = _rating(created_at=dt)
        rows = _parse_csv(_view()._csv_response([r]))
        self.assertIn("2026-03-22 08:05", rows[1])

    def test_multiple_ratings_produce_multiple_rows(self):
        ratings = [_rating(order_number=f"ORD-{i}") for i in range(5)]
        rows = _parse_csv(_view()._csv_response(ratings))
        self.assertEqual(len(rows), 6)   # header + 5 data rows
