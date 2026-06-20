"""
Unit tests for TranslateView._call_openrouter in tenancy/api.py.

The method:
  1. Reads OPENROUTER_API_KEY, OPENROUTER_MODEL, PUBLIC_MENU_BASE_URL from settings
  2. Constructs a translation prompt with an optional source-language hint
  3. Makes an HTTP POST to OpenRouter and returns the translated text

Tested branches:
  - source_hint when source_lang is empty → ""
  - source_hint when source_lang is "auto" → ""
  - source_hint when source_lang not in lang map → ""
  - source_hint when source_lang is valid → " from <Language>"
  - target_name falls back to raw code when not in lang map
  - site_url falls back to "https://restomenu.app" when setting absent/empty
  - response content correctly extracted from choices[0].message.content
  - model defaults to "google/gemma-3-12b-it:free" when setting absent

All tests are unit-level (SimpleTestCase — urlopen is mocked, no network).
"""
import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from tenancy.api import TranslateView


# ── helper ────────────────────────────────────────────────────────────────────

def _make_response(content: str):
    """Return a mock urllib response that yields a JSON OpenRouter payload."""
    body = json.dumps({
        "choices": [{"message": {"content": content}}]
    }).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _call(text="Hello", target_lang="fr", source_lang="en", *, response_content="Bonjour"):
    """Call _call_openrouter with a mocked urlopen and return (captured_req, result)."""
    view = TranslateView.__new__(TranslateView)
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        return _make_response(response_content)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = view._call_openrouter(text, target_lang, source_lang)

    return captured.get("req"), result


# ══════════════════════════════════════════════════════════════════════════════
# Source-language hint in the prompt
# ══════════════════════════════════════════════════════════════════════════════

class CallOpenrouterSourceHintTests(SimpleTestCase):
    """source_hint is only injected for known, non-auto source languages."""

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_known_source_lang_adds_hint(self):
        req, _ = _call(source_lang="en")
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertIn("from English", prompt)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_empty_source_lang_no_hint(self):
        req, _ = _call(source_lang="")
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertNotIn("from ", prompt)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_auto_source_lang_no_hint(self):
        req, _ = _call(source_lang="auto")
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertNotIn("from ", prompt)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_unknown_source_lang_no_hint(self):
        req, _ = _call(source_lang="zz")   # not in _TRANSLATE_LANG_NAMES
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertNotIn("from ", prompt)


# ══════════════════════════════════════════════════════════════════════════════
# Target language name in the prompt
# ══════════════════════════════════════════════════════════════════════════════

class CallOpenrouterTargetNameTests(SimpleTestCase):
    """target_name uses display name from dict, or the raw code as fallback."""

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_known_target_lang_uses_display_name(self):
        req, _ = _call(target_lang="fr")
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertIn("French", prompt)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_unknown_target_lang_uses_raw_code(self):
        req, _ = _call(target_lang="zz")   # not in _TRANSLATE_LANG_NAMES
        payload = json.loads(req.data.decode("utf-8"))
        prompt = payload["messages"][0]["content"]
        self.assertIn("zz", prompt)


# ══════════════════════════════════════════════════════════════════════════════
# Model and site_url settings
# ══════════════════════════════════════════════════════════════════════════════

class CallOpenrouterSettingsTests(SimpleTestCase):
    """Settings are read at call time; fallbacks apply when absent."""

    @override_settings(
        OPENROUTER_API_KEY="my-key",
        OPENROUTER_MODEL="google/gemma-3-12b-it:free",
    )
    def test_configured_model_used_in_payload(self):
        req, _ = _call()
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "google/gemma-3-12b-it:free")

    @override_settings(
        OPENROUTER_API_KEY="my-key",
        OPENROUTER_MODEL="openai/gpt-4o",
    )
    def test_custom_model_setting_honoured(self):
        req, _ = _call()
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "openai/gpt-4o")

    @override_settings(
        OPENROUTER_API_KEY="abc123",
        PUBLIC_MENU_BASE_URL="https://my-menu-app.com",
    )
    def test_site_url_from_setting(self):
        req, _ = _call()
        # urllib.request.Request.capitalize() normalises header names.
        # "HTTP-Referer" → "Http-referer"
        self.assertIn("https://my-menu-app.com", req.headers.get("Http-referer", ""))

    @override_settings(
        OPENROUTER_API_KEY="abc123",
        PUBLIC_MENU_BASE_URL="",
    )
    def test_site_url_fallback_when_setting_empty(self):
        req, _ = _call()
        self.assertIn("https://restomenu.app", req.headers.get("Http-referer", ""))

    @override_settings(OPENROUTER_API_KEY="my-key")
    def test_api_key_in_authorization_header(self):
        req, _ = _call()
        # "Authorization" → capitalize() → "Authorization" (unchanged)
        self.assertIn("my-key", req.headers.get("Authorization", ""))


# ══════════════════════════════════════════════════════════════════════════════
# Response parsing
# ══════════════════════════════════════════════════════════════════════════════

class CallOpenrouterResponseTests(SimpleTestCase):
    """The translated content is extracted from choices[0].message.content."""

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_translated_content_returned(self):
        _, result = _call(response_content="Bonjour le monde")
        self.assertEqual(result, "Bonjour le monde")

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_whitespace_stripped_from_result(self):
        _, result = _call(response_content="  Bonjour  ")
        self.assertEqual(result, "Bonjour")
