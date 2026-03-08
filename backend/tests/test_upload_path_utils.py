from django.test import SimpleTestCase, override_settings

from tenancy.api import _extract_relative_media_path, _tenant_upload_prefix


@override_settings(MEDIA_URL="/media/")
class UploadPathUtilsTests(SimpleTestCase):
    def test_extract_relative_path_from_absolute_url(self):
        value = "http://demo.localhost:8000/media/uploads/demo/2026/03/file.webp"
        self.assertEqual(_extract_relative_media_path(value), "uploads/demo/2026/03/file.webp")

    def test_extract_relative_path_from_absolute_media_path(self):
        value = "/media/uploads/demo/2026/03/file.webp"
        self.assertEqual(_extract_relative_media_path(value), "uploads/demo/2026/03/file.webp")

    def test_extract_relative_path_from_relative_value(self):
        value = "uploads/demo/2026/03/file.webp"
        self.assertEqual(_extract_relative_media_path(value), "uploads/demo/2026/03/file.webp")

    def test_rejects_non_media_absolute_path(self):
        value = "/tmp/uploads/demo/file.webp"
        self.assertEqual(_extract_relative_media_path(value), "")

    def test_rejects_path_traversal(self):
        value = "../secret.txt"
        self.assertEqual(_extract_relative_media_path(value), "")

    def test_tenant_prefix_helper(self):
        self.assertEqual(_tenant_upload_prefix("Demo"), "uploads/demo/")
