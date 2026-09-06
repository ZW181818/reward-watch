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

R2_ENVIRONMENT_KEYS = (
    "R2_ENDPOINT_URL",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_PUBLIC_BASE_URL",
)


class InvalidImageUpload(ValueError):
    pass


def media_storage_status() -> dict[str, object]:
    missing = [key for key in R2_ENVIRONMENT_KEYS if not os.getenv(key)]
    is_production = os.getenv("APP_ENV", "development").lower() == "production"
    if not missing:
        return {"ready": True, "provider": "r2", "missing": []}
    if is_production:
        return {"ready": False, "provider": "r2", "missing": missing}
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

    r2_config = {
        "endpoint": os.getenv(R2_ENVIRONMENT_KEYS[0]),
        "access_key": os.getenv(R2_ENVIRONMENT_KEYS[1]),
        "secret_key": os.getenv(R2_ENVIRONMENT_KEYS[2]),
        "bucket": os.getenv(R2_ENVIRONMENT_KEYS[3]),
        "public_url": os.getenv(R2_ENVIRONMENT_KEYS[4]),
    }
    storage_status = media_storage_status()
    if storage_status["provider"] == "r2" and not storage_status["missing"]:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=r2_config["endpoint"],
            aws_access_key_id=r2_config["access_key"],
            aws_secret_access_key=r2_config["secret_key"],
            region_name="auto",
        )
        client.put_object(
            Bucket=r2_config["bucket"],
            Key=object_key,
            Body=image_bytes,
            ContentType="image/jpeg",
            CacheControl="public, max-age=31536000, immutable",
        )
        return f"{str(r2_config['public_url']).rstrip('/')}/{object_key}"

    if not storage_status["ready"]:
        raise RuntimeError("Persistent image storage is not configured")

    target = MEDIA_DIR / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return f"/media/{object_key}"
