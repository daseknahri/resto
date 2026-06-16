"""R19 policing: every ``create=True`` in the test suite must be justified.

WHY THIS EXISTS
---------------
``unittest.mock.patch(..., create=True)`` tells mock to *invent* the target
attribute if it does not already exist.  That is occasionally legitimate (e.g.
patching an optional Django setting, or a name that is only imported lazily
*inside* a function and therefore is not a module attribute at patch time).

But it is also a notorious footgun: ``create=True`` will happily mock a symbol
that a typo, a relocated import, or a deleted attribute has made nonexistent —
silently masking the very bug a test should catch.  A production incident once
500'd every marketplace order via a wrong-module ``Profile`` import that the
tests hid behind exactly this flag.

So: ``create=True`` is allowed, but never *silently*.  Each occurrence must
carry an inline allow-comment stating WHY, forcing a deliberate decision:

    patch("django.conf.settings.SOME_OPTIONAL", "x", create=True)  # create-true-ok: optional setting, env-fallback default

This test scans every ``tests/*.py`` file and fails listing any ``create=True``
that lacks a ``# create-true-ok: <reason>`` annotation on the same line.

It is pure file I/O — no DB, runs everywhere.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

# The annotation that whitelists a single create=True occurrence.
ALLOW_MARKER = "create-true-ok:"

# Match `create=True` as a keyword argument (optional whitespace around `=`),
# not e.g. a variable named `xcreate`.
_CREATE_TRUE_RE = re.compile(r"(?<![\w.])create\s*=\s*True\b")

# Strip backtick-quoted inline-code / RST spans (``...`` or `...`) so that
# prose mentions of create=True in docstrings — like this very file's siblings'
# documentation — are not mistaken for real patch() calls.
_BACKTICK_SPAN_RE = re.compile(r"`+[^`]*`+")

TESTS_DIR = Path(__file__).resolve().parent


class NoUnannotatedCreateTrueTests(SimpleTestCase):
    """Every patch(..., create=True) in tests/ must carry a justification comment."""

    def test_all_create_true_uses_are_annotated(self):
        offenders = []
        scanned = 0

        for path in sorted(TESTS_DIR.glob("*.py")):
            if path.name == Path(__file__).name:
                # Don't flag the regex/marker literals in this policing test itself.
                continue
            scanned += 1
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                # Ignore backtick-quoted prose (docstring/RST inline code).
                code = _BACKTICK_SPAN_RE.sub("", line)
                if not _CREATE_TRUE_RE.search(code):
                    continue
                if ALLOW_MARKER in line:
                    continue
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")

        # Guard against the scan silently matching nothing (e.g. glob breaks).
        self.assertGreater(
            scanned,
            0,
            "create=True policer scanned 0 test files — discovery is broken.",
        )

        self.assertEqual(
            offenders,
            [],
            "Found `create=True` in tests without a `# create-true-ok: <reason>` "
            "annotation. create=True invents a missing attribute and can silently "
            "mask a real import/attribute bug. For each occurrence either (a) patch "
            "the REAL attribute/source instead, or (b) add a trailing "
            "`# create-true-ok: <short reason>` explaining why inventing the "
            "attribute is safe here:\n  " + "\n  ".join(offenders),
        )
