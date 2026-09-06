from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
import os
from pathlib import Path
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_DIMENSION = 1600
MAX_STORED_IMAGE_BYTES = 600 * 1024
MIN_IMAGE_DIMENSION = 720
JPEG_QUALITY_STEPS = (78, 70, 62, 54, 46)
MEDIA_DIR = Path(__file__).resolve().parents[1] / "data" / "media"
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

CLOUDINARY_ENVIRONMENT_KEYS = ("CLOUDINARY_URL",)


class InvalidImageUpload(ValueError):
    pass


def media_storage_status() -> dict[str, object]:
    missing = [key for key in CLOUDINARY_ENVIRONMENT_KEYS if not os.getenv(key)]
    is_production = os.getenv("APP_ENV", "development").lower() == "production"
    if not missing:
        return {"ready": True, "provider": "cloudinary", "missing": []}
    if is_production:
        return {"ready": False, "provider": "cloudinary", "missing": missing}
    return {"ready": True, "provider": "local", "missing": missing}


def _encode_jpeg_under_limit(image: Image.Image) -> bytes:
    working = image
    smallest_result: bytes | None = None

    while True:
        for quality in JPEG_QUALITY_STEPS:
            output = BytesIO()
            working.save(
                output,
                format="JPEG",
                optimize=True,
                progressive=True,
                quality=quality,
            )
            encoded = output.getvalue()
            if smallest_result is None or len(encoded) < len(smallest_result):
                smallest_result = encoded
            if len(encoded) <= MAX_STORED_IMAGE_BYTES:
                return encoded

        largest_dimension = max(working.size)
        if largest_dimension <= MIN_IMAGE_DIMENSION:
            break

        scale = max(MIN_IMAGE_DIMENSION / largest_dimension, 0.82)
        next_size = (
            max(1, round(working.width * scale)),
            max(1, round(working.height * scale)),
        )
        if next_size == working.size:
            break
        working = working.resize(next_size, Image.Resampling.LANCZOS)

    if smallest_result is not None and len(smallest_result) <= MAX_STORED_IMAGE_BYTES:
        return smallest_result
    raise InvalidImageUpload("The image could not be compressed below 600 KB")


def prepare_uploaded_image(contents: bytes) -> bytes:
    if not contents:
        raise InvalidImageUpload("The image file is empty")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise InvalidImageUpload("Images must be 10 MB or smaller")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contents)) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
                if image.mode in {"RGBA", "LA"}:
                    background = Image.new("RGB", image.size, "white")
                    alpha = image.getchannel("A")
                    background.paste(image.convert("RGB"), mask=alpha)
                    image = background
                elif image.mode != "RGB":
                    image = image.convert("RGB")

                return _encode_jpeg_under_limit(image)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
        raise InvalidImageUpload("Only valid JPEG, PNG, or WebP images are accepted") from exc


def store_admin_image(contents: bytes) -> str:
    image_bytes = prepare_uploaded_image(contents)
    date_path = datetime.now(UTC).strftime("%Y/%m")
    object_key = f"admin/{date_path}/{uuid4().hex}.jpg"

    storage_status = media_storage_status()
    if storage_status["provider"] == "cloudinary" and not storage_status["missing"]:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(secure=True)
            result = cloudinary.uploader.upload(
                BytesIO(image_bytes),
                format="jpg",
                overwrite=False,
                public_id=f"reward-watch/{object_key.removesuffix('.jpg')}",
                resource_type="image",
                tags=["reward-watch", "admin-upload"],
                unique_filename=False,
            )
        except Exception as exc:
            raise RuntimeError("Persistent image upload failed") from exc

        secure_url = result.get("secure_url")
        if not isinstance(secure_url, str) or not secure_url.startswith("https://"):
            raise RuntimeError("Persistent image upload returned no secure URL")
        return secure_url

    if not storage_status["ready"]:
        raise RuntimeError("Persistent image storage is not configured")

    target = MEDIA_DIR / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return f"/media/{object_key}"
