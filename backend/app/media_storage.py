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
MAX_IMAGE_DIMENSION = 2400
MEDIA_DIR = Path(__file__).resolve().parents[1] / "data" / "media"
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class InvalidImageUpload(ValueError):
    pass


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

                output = BytesIO()
                image.save(output, format="JPEG", optimize=True, quality=86)
                return output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
        raise InvalidImageUpload("Only valid JPEG, PNG, or WebP images are accepted") from exc


def store_admin_image(contents: bytes) -> str:
    image_bytes = prepare_uploaded_image(contents)
    date_path = datetime.now(UTC).strftime("%Y/%m")
    object_key = f"admin/{date_path}/{uuid4().hex}.jpg"

    r2_config = {
        "endpoint": os.getenv("R2_ENDPOINT_URL"),
        "access_key": os.getenv("R2_ACCESS_KEY_ID"),
        "secret_key": os.getenv("R2_SECRET_ACCESS_KEY"),
        "bucket": os.getenv("R2_BUCKET_NAME"),
        "public_url": os.getenv("R2_PUBLIC_BASE_URL"),
    }
    if all(r2_config.values()):
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

    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("Persistent image storage is not configured")

    target = MEDIA_DIR / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return f"/media/{object_key}"
