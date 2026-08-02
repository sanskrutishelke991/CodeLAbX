"""Validation and metadata-stripping normalization for image uploads."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .api import APIRequestError

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _invalid_image(message="The uploaded file is not a supported image."):
    raise APIRequestError("INVALID_IMAGE", message, 400)


def normalize_uploaded_image(uploaded_file):
    """Decode, validate, resize, strip metadata, and return a safe JPEG."""
    if uploaded_file.size > settings.AI_IMAGE_MAX_BYTES:
        raise APIRequestError(
            "IMAGE_TOO_LARGE",
            "Image size must be no more than 5 MB.",
            413,
        )

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source:
            image_format = (source.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                _invalid_image()

            width, height = source.size
            if width < 1 or height < 1:
                _invalid_image()
            if width > settings.AI_IMAGE_MAX_DIMENSION or height > settings.AI_IMAGE_MAX_DIMENSION:
                _invalid_image("The image dimensions are too large.")
            if width * height > settings.AI_IMAGE_MAX_PIXELS:
                _invalid_image("The image contains too many pixels.")
            if getattr(source, "n_frames", 1) != 1:
                _invalid_image("Animated images are not supported.")

            source.load()
            normalized = ImageOps.exif_transpose(source)
            normalized.thumbnail(
                (
                    settings.AI_IMAGE_NORMALIZED_MAX_DIMENSION,
                    settings.AI_IMAGE_NORMALIZED_MAX_DIMENSION,
                ),
                Image.Resampling.LANCZOS,
            )

            if normalized.mode in {"RGBA", "LA"}:
                rgba = normalized.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                background.alpha_composite(rgba)
                normalized = background.convert("RGB")
            else:
                normalized = normalized.convert("RGB")

            output = BytesIO()
            normalized.save(
                output,
                format="JPEG",
                quality=88,
                optimize=True,
            )

    except APIRequestError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise APIRequestError(
            "INVALID_IMAGE",
            "The uploaded file could not be decoded safely.",
            400,
        ) from exc
    finally:
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError):
            pass

    return ContentFile(
        output.getvalue(),
        name=f"{uuid4().hex}.jpg",
    )
