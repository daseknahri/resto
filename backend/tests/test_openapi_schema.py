"""
RISK SCHEMA-1: OpenAPI generation via drf-spectacular.

DB-free regression test: builds the full API schema the same way `manage.py
spectacular` does (drf_spectacular.generators.SchemaGenerator) and asserts there
are zero duplicate `operationId` values across all paths/methods.

Why this matters: drf-spectacular auto-resolves operationId collisions (e.g. two
views both named "...Retrieve") by appending numeral suffixes (`_2`, `_3`, ...)
and only *warns* about it — it does not fail generation. A regression that
reintroduces ambiguous operation naming would ship silently (still 200/green)
unless something asserts the resolved IDs are actually unique. That's what this
test guards.

Uses SimpleTestCase (no DB) — pytest-django's DJANGO_SETTINGS_MODULE wiring
handles django.setup(); no extra bootstrap needed.
"""
from collections import Counter

from django.test import SimpleTestCase

from drf_spectacular.generators import SchemaGenerator


class OpenAPISchemaTests(SimpleTestCase):
    databases = set()  # explicit: this test must never touch the DB

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        generator = SchemaGenerator()
        cls.schema = generator.get_schema(request=None, public=True)

    def test_schema_builds(self):
        self.assertIn("paths", self.schema)
        self.assertGreater(len(self.schema["paths"]), 0, "expected at least one API path in the schema")

    def test_no_duplicate_operation_ids(self):
        operation_ids = []
        for path, methods in self.schema["paths"].items():
            for method, operation in methods.items():
                # Skip non-HTTP-method keys drf-spectacular may emit (e.g. "parameters").
                if not isinstance(operation, dict) or "operationId" not in operation:
                    continue
                operation_ids.append((operation["operationId"], path, method))

        counts = Counter(op_id for op_id, _path, _method in operation_ids)
        duplicates = {op_id: count for op_id, count in counts.items() if count > 1}

        if duplicates:
            offending = [
                (op_id, path, method)
                for op_id, path, method in operation_ids
                if op_id in duplicates
            ]
            self.fail(
                "Duplicate operationId(s) found in the generated OpenAPI schema: "
                f"{duplicates}. Offending path/method entries: {offending}. "
                "Add an explicit `operation_id=` via @extend_schema on the "
                "colliding view(s) to disambiguate."
            )

        self.assertGreater(len(operation_ids), 0, "expected at least one operation in the schema")
