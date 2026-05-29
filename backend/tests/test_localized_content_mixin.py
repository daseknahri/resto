"""
Unit tests for menu.serializers.LocalizedContentMixin edge cases not covered
by the higher-level test_menu_i18n_serializer.py tests.

Specifically:

  _localized_text
    - base is empty AND no translation matches locale → falls back to first
      available translation (alphabetical key order)
    - translations arg is not a dict → returns base unchanged
    - translations arg is an empty dict → returns base unchanged

  _request_locale
    - request is None → returns ""
    - request has no `headers` attr → falls back to META["HTTP_ACCEPT_LANGUAGE"]
    - no locale found anywhere → returns ""

  _force_locale_enabled
    - request has no `query_params` attr → falls back to request.GET

  _tenant_max_languages
    - request is None → returns 1
    - tenant is None → returns 1
    - plan is None → returns 1
    - plan.max_languages is None → returns 1
    - plan.max_languages is invalid (raises) → returns 1
    - plan.max_languages is 0 → max(0, 1) = 1

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from menu.serializers import CategorySerializer


# ── helpers ───────────────────────────────────────────────────────────────────

def _serializer(request=None):
    return CategorySerializer(context={"request": request})


def _request(lang=None, *, force_locale=None, accept_language=None,
             authenticated=False, use_meta=False, max_languages=2,
             tenant=None):
    """Build a minimal fake request for LocalizedContentMixin."""
    query_params = {}
    if lang:
        query_params["lang"] = lang
    if force_locale:
        query_params["force_locale"] = force_locale

    plan = SimpleNamespace(max_languages=max_languages)
    t = tenant or SimpleNamespace(plan=plan)

    req = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=authenticated),
        tenant=t,
        query_params=query_params,
    )
    if accept_language is not None and not use_meta:
        req.headers = {"Accept-Language": accept_language}
        req.META = {}
    elif accept_language is not None and use_meta:
        req.META = {"HTTP_ACCEPT_LANGUAGE": accept_language}
        # no headers attr
    else:
        req.headers = {}
        req.META = {}
    return req


# ══════════════════════════════════════════════════════════════════════════════
# _localized_text — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class LocalizedTextEdgeCaseTests(SimpleTestCase):

    def test_no_matching_locale_empty_base_falls_back_to_first_translation(self):
        """When base is empty and no translation matches, the first key (sorted)
        is used as a last-resort fallback."""
        ser = _serializer(_request(lang="de"))  # "de" not in translations
        # sorted keys: "ar", "fr" → first is "ar"
        result = ser._localized_text("", {"fr": "Boissons", "ar": "مشروبات"})
        self.assertEqual(result, "مشروبات")

    def test_non_dict_translations_returns_base(self):
        ser = _serializer(_request())
        self.assertEqual(ser._localized_text("Hello", "not-a-dict"), "Hello")

    def test_empty_dict_translations_returns_base(self):
        ser = _serializer(_request())
        self.assertEqual(ser._localized_text("Hello", {}), "Hello")

    def test_none_translations_returns_base(self):
        ser = _serializer(_request())
        self.assertEqual(ser._localized_text("Hello", None), "Hello")

    def test_locale_with_region_tries_primary_language_too(self):
        """'fr-CA' should match 'fr' in translations via the primary-code fallback."""
        ser = _serializer(_request(lang="fr-CA"))
        result = ser._localized_text("Salad", {"fr": "Salade"})
        self.assertEqual(result, "Salade")

    def test_all_translation_values_empty_returns_base(self):
        """If every translation value is blank, fall through to base text."""
        ser = _serializer(_request(lang="de"))
        result = ser._localized_text("Burger", {"fr": "", "ar": "  "})
        self.assertEqual(result, "Burger")


# ══════════════════════════════════════════════════════════════════════════════
# _request_locale — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class RequestLocaleEdgeCaseTests(SimpleTestCase):

    def test_no_request_returns_empty_string(self):
        ser = _serializer(request=None)
        self.assertEqual(ser._request_locale(), "")

    def test_meta_accept_language_used_when_headers_absent(self):
        """When the request object has no `headers` attr, fall back to META."""
        req = _request(accept_language="fr,en;q=0.8", use_meta=True)
        ser = _serializer(req)
        self.assertEqual(ser._request_locale(), "fr")

    def test_no_locale_anywhere_returns_empty_string(self):
        """Neither lang param nor Accept-Language header present → ""."""
        ser = _serializer(_request())
        self.assertEqual(ser._request_locale(), "")

    def test_empty_accept_language_header_returns_empty(self):
        ser = _serializer(_request(accept_language=""))
        self.assertEqual(ser._request_locale(), "")

    def test_invalid_accept_language_tokens_skipped(self):
        """Tokens that don't parse as valid locales are skipped."""
        ser = _serializer(_request(accept_language="zz-XX-XX, en;q=0.5"))
        # "zz-XX-XX" is 8 chars — _normalize_locale returns "" for it,
        # then "en" is valid → should return "en"
        result = ser._request_locale()
        self.assertEqual(result, "en")


# ══════════════════════════════════════════════════════════════════════════════
# _force_locale_enabled — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class ForceLocaleEnabledEdgeCaseTests(SimpleTestCase):

    def test_no_force_locale_param_returns_false(self):
        ser = _serializer(_request())
        self.assertFalse(ser._force_locale_enabled())

    def test_force_locale_one_returns_true(self):
        ser = _serializer(_request(force_locale="1"))
        self.assertTrue(ser._force_locale_enabled())

    def test_force_locale_true_returns_true(self):
        ser = _serializer(_request(force_locale="true"))
        self.assertTrue(ser._force_locale_enabled())

    def test_request_get_used_when_query_params_absent(self):
        """When the request has no query_params attr, falls back to request.GET."""
        req = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=2)),
            GET={"force_locale": "1"},
            headers={},
            META={},
        )
        # no query_params attr on req
        ser = _serializer(req)
        self.assertTrue(ser._force_locale_enabled())

    def test_no_request_returns_false(self):
        ser = _serializer(request=None)
        self.assertFalse(ser._force_locale_enabled())


# ══════════════════════════════════════════════════════════════════════════════
# _tenant_max_languages — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TenantMaxLanguagesEdgeCaseTests(SimpleTestCase):

    def test_no_request_returns_one(self):
        ser = _serializer(request=None)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_no_tenant_on_request_returns_one(self):
        req = SimpleNamespace(tenant=None)
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_tenant_with_no_plan_returns_one(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=None))
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_plan_max_languages_none_returns_one(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=None)))
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_plan_max_languages_zero_returns_one(self):
        """max(0, 1) = 1 — zero is treated as effectively one."""
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=0)))
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_plan_max_languages_invalid_string_returns_one(self):
        """Non-numeric value raises (caught) → returns 1."""
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages="many")))
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 1)

    def test_valid_max_languages_returned(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=5)))
        ser = _serializer(req)
        self.assertEqual(ser._tenant_max_languages(), 5)
