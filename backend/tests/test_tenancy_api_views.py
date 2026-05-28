"""
Tests for tenancy API views:
  - ImageUploadView       POST /api/upload-image/
  - ImageDeleteView       POST /api/delete-image/
  - TranslateView         POST /api/translate/
  - OwnerDeletionRequestView POST /api/owner/deletion-request/
  - AppManifestView       GET  /app-manifest.json

All tests are unit-level (SimpleTestCase + mocks — no real DB or filesystem).
"""
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from django.test import override_settings

from tenancy.api import (
    AppManifestView,
    ImageDeleteView,
    ImageUploadView,
    OwnerDeletionRequestView,
    TranslateView,
)
from accounts.models import User


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owner(tenant_id=1):
    u = MagicMock(spec=User)
    u.is_authenticated = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.is_tenant_owner = True
    u.is_tenant_staff = False
    u.role = User.Roles.TENANT_OWNER
    u.tenant_id = tenant_id
    u.Roles = User.Roles
    u.email = "owner@example.com"
    return u


def _anon():
    u = MagicMock()
    u.is_authenticated = False
    return u


def _tenant(tenant_id=1):
    t = SimpleNamespace(
        id=tenant_id,
        pk=tenant_id,
        slug="myrestaurant",
        name="My Restaurant",
        schema_name="myrestaurant",
    )
    return t


def _image_file(name="photo.jpg", content=b"FAKEJPG"):
    return SimpleUploadedFile(name, content, content_type="image/jpeg")


# ── ImageUploadView ───────────────────────────────────────────────────────────

class ImageUploadViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ImageUploadView.as_view()

    def _post(self, file=None, user=None, tenant=None, variant=None):
        data = {}
        if file is not None:
            data["image"] = file
        if variant is not None:
            data["variant"] = variant
        req = self.factory.post("/api/upload-image/", data, format="multipart")
        req.user = user or _owner()
        if tenant is not None:
            req.tenant = tenant
        else:
            req.tenant = _tenant()
        return self.view(req)

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_wrong_tenant_returns_403(self):
        user = _owner(tenant_id=99)
        resp = self._post(user=user, tenant=_tenant(tenant_id=1))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_file_returns_400(self):
        resp = self._post(file=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_image_file_returns_400(self):
        f = SimpleUploadedFile("doc.pdf", b"PDF...", content_type="application/pdf")
        resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_variant_returns_400(self):
        f = _image_file()
        resp = self._post(file=f, variant="invalid_variant")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_upload_returns_201_with_url(self):
        f = _image_file()
        with patch("tenancy.api._optimize_image", return_value=(b"OPTIMIZED", "jpg", "image/jpeg", "")) as mock_opt:
            with patch("tenancy.api.default_storage") as mock_storage:
                mock_storage.save.return_value = "uploads/myrestaurant/2026/01/abc.jpg"
                mock_storage.url.return_value = "https://cdn.example.com/uploads/myrestaurant/2026/01/abc.jpg"
                resp = self._post(file=f)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("url", resp.data)
        self.assertIn("path", resp.data)

    def test_logo_variant_accepted(self):
        f = _image_file()
        with patch("tenancy.api._optimize_image", return_value=(b"OPTIMIZED", "jpg", "image/jpeg", "logo")):
            with patch("tenancy.api.default_storage") as mock_storage:
                mock_storage.save.return_value = "uploads/myrestaurant/2026/01/abc.jpg"
                mock_storage.url.return_value = "/media/abc.jpg"
                resp = self._post(file=f, variant="logo")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["variant"], "logo")

    def test_relative_url_is_made_absolute(self):
        """When storage returns a relative URL, it should be made absolute."""
        f = _image_file()
        with patch("tenancy.api._optimize_image", return_value=(b"OPTIMIZED", "jpg", "image/jpeg", "")):
            with patch("tenancy.api.default_storage") as mock_storage:
                mock_storage.save.return_value = "uploads/abc.jpg"
                mock_storage.url.return_value = "/media/uploads/abc.jpg"  # relative
                resp = self._post(file=f)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # URL starts with "http" after build_absolute_uri
        self.assertTrue(resp.data["url"].startswith("http"))


# ── ImageDeleteView ───────────────────────────────────────────────────────────

class ImageDeleteViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = ImageDeleteView.as_view()

    def _post(self, data=None, user=None, tenant=None):
        req = self.factory.post("/api/delete-image/", data or {}, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_path_returns_400(self):
        resp = self._post(data={})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outside_tenant_path_returns_403(self):
        # Path from a different tenant
        data = {"path": "uploads/othertenant/2026/01/abc.jpg"}
        resp = self._post(data=data)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_valid_path_deletes_and_returns_200(self):
        path = "uploads/myrestaurant/2026/01/abc.jpg"
        with patch("tenancy.api.default_storage") as mock_storage:
            mock_storage.exists.return_value = True
            resp = self._post(data={"path": path})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["deleted"])
        self.assertEqual(resp.data["path"], path)
        mock_storage.delete.assert_called_once_with(path)

    def test_non_existent_path_returns_200_with_deleted_false(self):
        path = "uploads/myrestaurant/2026/01/gone.jpg"
        with patch("tenancy.api.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            resp = self._post(data={"path": path})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["deleted"])
        mock_storage.delete.assert_not_called()


# ── TranslateView ─────────────────────────────────────────────────────────────

class TranslateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = TranslateView.as_view()

    def _post(self, data=None, user=None, tenant=None):
        req = self.factory.post("/api/translate/", data or {}, format="json")
        req.user = user or _owner()
        req.tenant = tenant or _tenant()
        return self.view(req)

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_api_key_returns_503(self):
        with override_settings(OPENROUTER_API_KEY=""):
            resp = self._post(data={"text": "Hello", "target_lang": "fr"})
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["code"], "not_configured")

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_empty_text_returns_400(self):
        resp = self._post(data={"text": "", "target_lang": "fr"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_unsupported_language_returns_400(self):
        resp = self._post(data={"text": "Hello", "target_lang": "zh"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_text_too_long_returns_400(self):
        resp = self._post(data={"text": "x" * 2001, "target_lang": "fr"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OPENROUTER_API_KEY="test-key", OPENROUTER_MODEL="gemma", PUBLIC_MENU_BASE_URL="https://example.com")
    def test_successful_translation_returns_200(self):
        with patch.object(TranslateView, "_call_openrouter", return_value="Bonjour"):
            resp = self._post(data={"text": "Hello", "target_lang": "fr"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["translated"], "Bonjour")
        self.assertEqual(resp.data["target_lang"], "fr")

    @override_settings(OPENROUTER_API_KEY="test-key", OPENROUTER_MODEL="gemma", PUBLIC_MENU_BASE_URL="https://example.com")
    def test_provider_http_error_returns_502(self):
        import urllib.error
        err = urllib.error.HTTPError(url="", code=429, msg="Too many requests", hdrs={}, fp=io.BytesIO(b"rate limited"))
        with patch.object(TranslateView, "_call_openrouter", side_effect=err):
            resp = self._post(data={"text": "Hello", "target_lang": "ar"})
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(resp.data["code"], "provider_error")

    @override_settings(OPENROUTER_API_KEY="test-key", OPENROUTER_MODEL="gemma", PUBLIC_MENU_BASE_URL="https://example.com")
    def test_url_error_returns_502(self):
        import urllib.error
        with patch.object(TranslateView, "_call_openrouter", side_effect=urllib.error.URLError("timeout")):
            resp = self._post(data={"text": "Hello", "target_lang": "fr"})
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(resp.data["code"], "provider_unavailable")


# ── OwnerDeletionRequestView ──────────────────────────────────────────────────

class OwnerDeletionRequestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerDeletionRequestView.as_view()

    def _post(self, data=None, user=None, tenant=None):
        req = self.factory.post("/api/owner/deletion-request/", data or {}, format="json")
        req.user = user or _owner()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_unauthenticated_returns_403(self):
        resp = self._post(user=_anon())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_returns_403(self):
        user = _owner()
        user.is_tenant_owner = False
        resp = self._post(user=user)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_tenant_returns_400(self):
        resp = self._post(tenant=None)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_success_returns_200(self):
        tenant = _tenant()
        tenant_obj = MagicMock()
        tenant_obj.deletion_requested_at = None
        from datetime import datetime, timezone as tz
        deletion_time = datetime(2026, 1, 1, 12, 0, tzinfo=tz.utc)
        tenant_obj.deletion_requested_at = deletion_time

        def sc(*args, **kwargs):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield
            return _cm()

        with patch("django_tenants.utils.schema_context", sc):
            with patch("tenancy.models.Tenant") as mock_tenant_model:
                mock_tenant_model.objects.get.return_value = tenant_obj
                with patch("django.utils.timezone.now", return_value=deletion_time):
                    resp = self._post(tenant=tenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["status"], "requested")

    def test_reason_stored(self):
        tenant = _tenant()
        tenant_obj = MagicMock()
        tenant_obj.deletion_requested_at = None
        from datetime import datetime, timezone as tz
        deletion_time = datetime(2026, 1, 1, 12, 0, tzinfo=tz.utc)
        tenant_obj.deletion_requested_at = deletion_time

        def sc(*args, **kwargs):
            from contextlib import contextmanager
            @contextmanager
            def _cm():
                yield
            return _cm()

        with patch("django_tenants.utils.schema_context", sc):
            with patch("tenancy.models.Tenant") as mock_tenant_model:
                mock_tenant_model.objects.get.return_value = tenant_obj
                with patch("django.utils.timezone.now", return_value=deletion_time):
                    resp = self._post(data={"reason": "Closing down"}, tenant=tenant)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(tenant_obj.deletion_reason, "Closing down")


# ── AppManifestView ───────────────────────────────────────────────────────────

class AppManifestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AppManifestView.as_view()

    def _get(self, tenant=None):
        req = self.factory.get("/app-manifest.json")
        req.user = _anon()
        if tenant is not None:
            req.tenant = tenant
        return self.view(req)

    def test_no_tenant_returns_400(self):
        resp = self._get(tenant=None)
        self.assertEqual(resp.status_code, 400)

    def test_returns_manifest_json_content_type(self):
        t = _tenant()
        t.profile = None
        resp = self._get(tenant=t)
        self.assertIn("application/manifest+json", resp.get("Content-Type", ""))

    def test_manifest_contains_required_fields(self):
        t = _tenant()
        t.profile = None
        resp = self._get(tenant=t)
        import json
        data = json.loads(resp.content)
        for field in ("name", "short_name", "icons", "start_url", "display"):
            self.assertIn(field, data, f"Missing manifest field: {field}")

    def test_restaurant_name_in_manifest(self):
        t = _tenant()
        t.name = "Bistro Bleu"
        t.profile = None
        resp = self._get(tenant=t)
        import json
        data = json.loads(resp.content)
        self.assertEqual(data["name"], "Bistro Bleu")

    def test_logo_url_added_to_icons(self):
        t = _tenant()
        profile = MagicMock()
        profile.logo_url = "https://cdn.example.com/logo.png"
        profile.primary_color = "#ff0000"
        profile.secondary_color = "#00ff00"
        t.profile = profile
        resp = self._get(tenant=t)
        import json
        data = json.loads(resp.content)
        srcs = [icon["src"] for icon in data["icons"]]
        self.assertIn("https://cdn.example.com/logo.png", srcs)

    def test_cache_control_header_set(self):
        t = _tenant()
        t.profile = None
        resp = self._get(tenant=t)
        self.assertIn("max-age=3600", resp.get("Cache-Control", ""))
