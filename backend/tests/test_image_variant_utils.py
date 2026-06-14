import io
import unittest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from tenancy.api import Image, _center_crop_to_ratio, _optimize_image


class ImageVariantUtilsTests(SimpleTestCase):
    def test_center_crop_to_ratio_reduces_width_for_wide_image(self):
        if Image is None:
            self.skipTest("Pillow not installed")
        image = Image.new("RGB", (2000, 1000), color=(20, 40, 60))
        cropped = _center_crop_to_ratio(image, 4 / 3)
        self.assertEqual(cropped.size, (1333, 1000))

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_optimize_image_applies_variant_constraints(self):
        source = Image.new("RGB", (2400, 1200), color=(120, 30, 50))
        buffer = io.BytesIO()
        source.save(buffer, format="PNG")
        upload = SimpleUploadedFile("hero.png", buffer.getvalue(), content_type="image/png")

        data, ext, content_type, variant = _optimize_image(upload, variant="hero")

        self.assertEqual(ext, "webp")
        self.assertEqual(content_type, "image/webp")
        self.assertEqual(variant, "hero")

        optimized = Image.open(io.BytesIO(data))
        self.assertLessEqual(optimized.size[0], 1800)
        self.assertLessEqual(optimized.size[1], 1012)
        ratio = optimized.size[0] / optimized.size[1]
        self.assertAlmostEqual(ratio, 16 / 9, delta=0.05)

    def test_optimize_image_raises_for_invalid_bytes(self):
        """OPS-5c item 1: _optimize_image now re-raises on corrupt/undecodable
        images instead of returning raw bytes with the client-supplied MIME type.
        The caller (ImageUploadView / _save_driver_doc_image) catches and rejects
        the upload — never echoing the client content_type."""
        upload = SimpleUploadedFile("broken.png", b"not-an-image", content_type="image/png")
        with self.assertRaises(Exception):
            _optimize_image(upload, variant="dish")
