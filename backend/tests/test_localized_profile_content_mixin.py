"""
Unit tests for tenancy.serializers.LocalizedProfileContentMixin edge cases.

The mixin is used by ProfileSerializer and differs from
menu.serializers.LocalizedContentMixin in one key way: its _normalize_locale
only accepts the three supported profile languages (en, fr, ar), while the
menu version accepts any 2-letter ISO code.

Covered here:

  _normalize_locale (instance method)
    - None / empty → ""
    - Valid primary code ("fr") → "fr"
    - Invalid primary code ("de") → "" (not in SUPPORTED_PROFILE_LANGUAGES)
    - "fr-CA" style locale → normalised to "fr"
    - underscore variant "fr_CA" → treated as "fr-CA" → "fr"

  _localized_text
    - Empty base, no locale match → falls back to first translation (sorted key)
    - translations is not a dict → returns base unchanged
    - translations is empty dict → returns base unchanged

  _request_locale
    - No request context → ""
    - META["HTTP_ACCEPT_LANGUAGE"] fallback when headers attr absent

  _force_locale_enabled
    - request.GET used when query_params attr is absent

  _tenant_max_languages
    - request is None → 1
    - tenant is None → 1
    - plan is None → 1
    - plan.max_languages is None → 1
    - plan.max_languages is 0 → 1

All tests are unit-level (SimpleTestCase — no real DB).
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from tenancy.serializers import ProfileSerializer


# ── helper ────────────────────────────────────────────────────────────────────

def _ser(request=None):
    return ProfileSerializer(context={"request": request})


def _req(lang=None, force_locale=None, accept_language=None,
         authenticated=False, use_meta=False, max_languages=2):
    query_params = {}
    if lang:
        query_params["lang"] = lang
    if force_locale:
        query_params["force_locale"] = force_locale

    req = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=authenticated),
        tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=max_languages)),
        query_params=query_params,
    )
    if accept_language is not None and not use_meta:
        req.headers = {"Accept-Language": accept_language}
        req.META = {}
    elif accept_language is not None and use_meta:
        req.META = {"HTTP_ACCEPT_LANGUAGE": accept_language}
        # intentionally no headers attr
    else:
        req.headers = {}
        req.META = {}
    return req


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_locale
# ══════════════════════════════════════════════════════════════════════════════

class NormalizeLocaleTests(SimpleTestCase):

    def test_none_returns_empty(self):
        self.assertEqual(_ser()._normalize_locale(None), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(_ser()._normalize_locale(""), "")

    def test_valid_supported_code_returned(self):
        self.assertEqual(_ser()._normalize_locale("fr"), "fr")
        self.assertEqual(_ser()._normalize_locale("ar"), "ar")
        self.assertEqual(_ser()._normalize_locale("en"), "en")

    def test_unsupported_primary_code_returns_empty(self):
        """'de' (German) is not in SUPPORTED_PROFILE_LANGUAGES."""
        self.assertEqual(_ser()._normalize_locale("de"), "")

    def test_fr_ca_style_normalised_to_primary(self):
        """'fr-CA' has primary 'fr' which is supported."""
        self.assertEqual(_ser()._normalize_locale("fr-CA"), "fr-ca")

    def test_underscore_variant_converted(self):
        """'fr_CA' → 'fr-ca' → matches locale regex → returned."""
        self.assertEqual(_ser()._normalize_locale("fr_CA"), "fr-ca")

    def test_uppercase_normalised(self):
        """Input is lowercased before evaluation."""
        self.assertEqual(_ser()._normalize_locale("FR"), "fr")
        self.assertEqual(_ser()._normalize_locale("AR"), "ar")


# ══════════════════════════════════════════════════════════════════════════════
# _localized_text — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class LocalizedTextEdgeCaseTests(SimpleTestCase):

    def test_empty_base_no_match_falls_back_to_first_sorted_translation(self):
        ser = _ser(_req(lang="de"))  # "de" not in supported
        result = ser._localized_text("", {"fr": "Boissons", "ar": "مشروبات"})
        # sorted keys: "ar", "fr" → first non-empty is "ar"
        self.assertEqual(result, "مشروبات")

    def test_non_dict_translations_returns_base(self):
        ser = _ser(_req())
        self.assertEqual(ser._localized_text("Hello", "not-a-dict"), "Hello")

    def test_empty_dict_returns_base(self):
        ser = _ser(_req())
        self.assertEqual(ser._localized_text("Tagline", {}), "Tagline")

    def test_none_translations_returns_base(self):
        ser = _ser(_req())
        self.assertEqual(ser._localized_text("Tagline", None), "Tagline")

    def test_matching_locale_preferred_over_base(self):
        ser = _ser(_req(lang="fr"))
        result = ser._localized_text("Original", {"fr": "Traduction"})
        self.assertEqual(result, "Traduction")


# ══════════════════════════════════════════════════════════════════════════════
# _request_locale — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class RequestLocaleEdgeCaseTests(SimpleTestCase):

    def test_no_request_returns_empty(self):
        self.assertEqual(_ser(request=None)._request_locale(), "")

    def test_meta_accept_language_fallback(self):
        req = _req(accept_language="fr,en;q=0.8", use_meta=True)
        self.assertEqual(_ser(req)._request_locale(), "fr")

    def test_no_locale_found_returns_empty(self):
        self.assertEqual(_ser(_req())._request_locale(), "")

    def test_authenticated_user_without_force_returns_empty(self):
        req = _req(lang="fr", authenticated=True)
        self.assertEqual(_ser(req)._request_locale(), "")

    def test_force_locale_enables_locale_for_authenticated(self):
        req = _req(lang="fr", force_locale="1", authenticated=True)
        self.assertEqual(_ser(req)._request_locale(), "fr")


# ══════════════════════════════════════════════════════════════════════════════
# _force_locale_enabled — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class ForceLocaleEdgeCaseTests(SimpleTestCase):

    def test_no_request_returns_false(self):
        self.assertFalse(_ser(request=None)._force_locale_enabled())

    def test_request_get_used_when_query_params_absent(self):
        req = SimpleNamespace(
            user=SimpleNamespace(is_authenticated=False),
            tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=2)),
            GET={"force_locale": "yes"},
            headers={},
            META={},
        )  # no query_params attr
        self.assertTrue(_ser(req)._force_locale_enabled())


# ══════════════════════════════════════════════════════════════════════════════
# _tenant_max_languages — edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TenantMaxLanguagesEdgeCaseTests(SimpleTestCase):

    def test_no_request_returns_one(self):
        self.assertEqual(_ser(request=None)._tenant_max_languages(), 1)

    def test_tenant_none_returns_one(self):
        req = SimpleNamespace(tenant=None)
        self.assertEqual(_ser(req)._tenant_max_languages(), 1)

    def test_plan_none_returns_one(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=None))
        self.assertEqual(_ser(req)._tenant_max_languages(), 1)

    def test_max_languages_none_returns_one(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=None)))
        self.assertEqual(_ser(req)._tenant_max_languages(), 1)

    def test_max_languages_zero_returns_one(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=0)))
        self.assertEqual(_ser(req)._tenant_max_languages(), 1)

    def test_valid_max_languages_returned(self):
        req = SimpleNamespace(tenant=SimpleNamespace(plan=SimpleNamespace(max_languages=3)))
        self.assertEqual(_ser(req)._tenant_max_languages(), 3)
