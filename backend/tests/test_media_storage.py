import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import media_storage


class MediaStorageTests(unittest.TestCase):
    def test_production_storage_status_reports_missing_r2_configuration(self):
        environment = {"APP_ENV": "production", **{key: "" for key in media_storage.R2_ENVIRONMENT_KEYS}}
        with patch.dict(os.environ, environment, clear=False):
            status = media_storage.media_storage_status()

        self.assertFalse(status["ready"])
        self.assertEqual(status["provider"], "r2")
        self.assertEqual(status["missing"], list(media_storage.R2_ENVIRONMENT_KEYS))

    def test_complete_r2_configuration_reports_ready(self):
        environment = {"APP_ENV": "production", **{key: "configured" for key in media_storage.R2_ENVIRONMENT_KEYS}}
        with patch.dict(os.environ, environment, clear=False):
            status = media_storage.media_storage_status()

        self.assertTrue(status["ready"])
        self.assertEqual(status["provider"], "r2")
        self.assertEqual(status["missing"], [])

    def test_local_upload_is_resized_and_strips_metadata(self):
        source = BytesIO()
        Image.new("RGB", (3200, 1600), "#4466AA").save(
            source,
            format="JPEG",
            exif=Image.Exif(),
            quality=95,
        )

        with tempfile.TemporaryDirectory() as directory, patch.object(
            media_storage, "MEDIA_DIR", Path(directory)
        ), patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            url = media_storage.store_admin_image(source.getvalue())
            output_path = Path(directory) / url.removeprefix("/media/")

            self.assertTrue(output_path.exists())
            with Image.open(output_path) as uploaded:
                self.assertLessEqual(max(uploaded.size), media_storage.MAX_IMAGE_DIMENSION)
                self.assertEqual(uploaded.getexif(), {})
            self.assertLessEqual(
                output_path.stat().st_size,
                media_storage.MAX_STORED_IMAGE_BYTES,
            )

    def test_noisy_upload_is_compressed_below_storage_limit(self):
        source = BytesIO()
        Image.effect_noise((3200, 2400), 100).convert("RGB").save(
            source,
            format="JPEG",
            quality=95,
        )

        compressed = media_storage.prepare_uploaded_image(source.getvalue())

        self.assertLessEqual(len(compressed), media_storage.MAX_STORED_IMAGE_BYTES)
        with Image.open(BytesIO(compressed)) as uploaded:
            self.assertLessEqual(max(uploaded.size), media_storage.MAX_IMAGE_DIMENSION)

    def test_invalid_upload_is_rejected(self):
        with self.assertRaises(media_storage.InvalidImageUpload):
            media_storage.prepare_uploaded_image(b"not-an-image")


if __name__ == "__main__":
    unittest.main()
