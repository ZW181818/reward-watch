import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import media_storage


class MediaStorageTests(unittest.TestCase):
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

    def test_invalid_upload_is_rejected(self):
        with self.assertRaises(media_storage.InvalidImageUpload):
            media_storage.prepare_uploaded_image(b"not-an-image")


if __name__ == "__main__":
    unittest.main()
