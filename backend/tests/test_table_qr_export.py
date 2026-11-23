from io import BytesIO
from unittest.mock import MagicMock
from types import SimpleNamespace
import zipfile

from django.test import SimpleTestCase, override_settings
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from menu.views import TableLinkViewSet


class FakeQuerySet(list):
    def filter(self, **kwargs):
        rows = list(self)
        if "is_active" in kwargs:
            rows = [row for row in rows if bool(getattr(row, "is_active", False)) == bool(kwargs["is_active"])]
        return FakeQuerySet(rows)


class DummyTableLinkViewSet(TableLinkViewSet):
    permission_classes = [AllowAny]
    test_rows = []
    test_object = None

    def get_queryset(self):
        return FakeQuerySet(self.__class__.test_rows)

    def get_object(self):
        return self.__class__.test_object


class TableQrExportTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        DummyTableLinkViewSet.test_rows = []
        DummyTableLinkViewSet.test_object = None

    def test_qr_export_returns_zip_with_manifest_and_pngs(self):
        DummyTableLinkViewSet.test_rows = [
            SimpleNamespace(id=1, label="Table 1", slug="table-1", is_active=True),
            SimpleNamespace(id=2, label="Table 2", slug="table-2", is_active=True),
        ]
        req = self.factory.get("/api/tables/qr-export/?menu_base_url=https://demo.example.com")
        req.tenant = SimpleNamespace(slug="demo")

        response = DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

        archive = zipfile.ZipFile(BytesIO(response.content))
        names = set(archive.namelist())
        self.assertIn("manifest.csv", names)
        self.assertIn("qr/table-1.png", names)
        self.assertIn("qr/table-2.png", names)

        manifest = archive.read("manifest.csv").decode("utf-8")
        self.assertIn("https://demo.example.com/t/table-1", manifest)
        self.assertIn("https://demo.example.com/menu?table=Table+1", manifest)

    def test_qr_export_rejects_when_no_rows(self):
        req = self.factory.get("/api/tables/qr-export/")
        req.tenant = SimpleNamespace(slug="demo")
        response = DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_tables")

    def test_qr_export_pdf_returns_pdf_bytes(self):
        DummyTableLinkViewSet.test_rows = [
            SimpleNamespace(id=1, label="Table 1", slug="table-1", is_active=True),
        ]
        req = self.factory.get("/api/tables/qr-export/?export_format=pdf&menu_base_url=https://demo.example.com")
        req.tenant = SimpleNamespace(slug="demo", name="Demo Restaurant")
        response = DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_qr_export_rejects_invalid_format(self):
        DummyTableLinkViewSet.test_rows = [
            SimpleNamespace(id=1, label="Table 1", slug="table-1", is_active=True),
        ]
        req = self.factory.get("/api/tables/qr-export/?export_format=docx")
        req.tenant = SimpleNamespace(slug="demo")
        response = DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_format")

    def test_qr_image_returns_png_payload(self):
        DummyTableLinkViewSet.test_object = SimpleNamespace(id=1, label="Table A", slug="table-a", is_active=True)
        req = self.factory.get("/api/tables/1/qr-image/?menu_base_url=https://demo.example.com")
        req.tenant = SimpleNamespace(slug="demo")

        response = DummyTableLinkViewSet.as_view({"get": "qr_image"})(req, pk=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))
class TableQrBaseUrlValidationTests(SimpleTestCase):
    """Wave D QR-1: the QR base URL must match the tenant's public menu host."""

    def setUp(self):
        self.factory = APIRequestFactory()
        DummyTableLinkViewSet.test_rows = [
            SimpleNamespace(id=1, label="Table 1", slug="table-1", is_active=True),
        ]
        DummyTableLinkViewSet.test_object = SimpleNamespace(
            id=1, label="Table A", slug="table-a", is_active=True
        )

    def _tenant_with_primary(self, domain):
        domains = MagicMock()
        domains.filter.return_value.first.return_value = SimpleNamespace(domain=domain)
        return SimpleNamespace(slug="demo", domains=domains)

    def _export(self, tenant, query=""):
        url = "/api/tables/qr-export/"
        if query:
            url = f"{url}?{query}"
        req = self.factory.get(url)
        req.tenant = tenant
        return DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)

    def test_matching_primary_domain_passes(self):
        tenant = self._tenant_with_primary("menu.demo.example")
        resp = self._export(tenant, "menu_base_url=https://menu.demo.example")
        self.assertEqual(resp.status_code, 200)

    def test_mismatched_base_is_refused(self):
        tenant = self._tenant_with_primary("menu.demo.example")
        resp = self._export(tenant, "menu_base_url=https://evil.example.com")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["code"], "menu_base_url_mismatch")
        self.assertIn("menu.demo.example", resp.data["expected_hosts"])

    def test_unset_env_falls_back_to_request_host(self):
        # Nothing authoritative configured (no primary domain, no env, no suffix):
        # the export falls back to the request host, as before.
        req = self.factory.get("/api/tables/qr-export/")
        req.tenant = SimpleNamespace(slug="demo")
        resp = DummyTableLinkViewSet.as_view({"get": "qr_export"})(req)
        self.assertEqual(resp.status_code, 200)
        archive = zipfile.ZipFile(BytesIO(resp.content))
        manifest = archive.read("manifest.csv").decode("utf-8")
        self.assertIn("http://testserver/t/table-1", manifest)

    @override_settings(PUBLIC_MENU_BASE_URL="https://menu.example.com")
    def test_configured_env_host_passes_and_other_host_refused(self):
        tenant = self._tenant_with_primary("menu.demo.example")
        ok = self._export(tenant, "menu_base_url=https://menu.example.com")
        self.assertEqual(ok.status_code, 200)
        bad = self._export(tenant, "menu_base_url=https://evil.example.com")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.data["code"], "menu_base_url_mismatch")

    @override_settings(TENANT_DOMAIN_SUFFIX="example.com")
    def test_slug_suffix_host_passes(self):
        tenant = self._tenant_with_primary("menu.demo.example")
        ok = self._export(tenant, "menu_base_url=https://demo.example.com")
        self.assertEqual(ok.status_code, 200)

    def test_qr_image_refuses_mismatched_base(self):
        tenant = self._tenant_with_primary("menu.demo.example")
        req = self.factory.get("/api/tables/1/qr-image/?menu_base_url=https://evil.example.com")
        req.tenant = tenant
        resp = DummyTableLinkViewSet.as_view({"get": "qr_image"})(req, pk=1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["code"], "menu_base_url_mismatch")
