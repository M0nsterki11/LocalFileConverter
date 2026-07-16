from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.constants import IMAGE_EXTENSIONS
from app.exceptions import ConversionError, UnsupportedFormatError
from app.i18n import translate
from utils.file_utils import generate_unique_output_path
from utils.input_validation import validate_image_file
from utils.output_safety import (
    cleanup_temporary_path,
    ensure_output_directory_ready,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    get_temporary_output_path,
    publish_temporary_file,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


class ImageConversionError(ConversionError):
    """Error raised while converting an image."""


OUTPUT_EXTENSIONS = {
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


def convert_image(
    input_file: str | Path,
    output_directory: str | Path,
    output_format: str,
    quality: int = 90,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    input_path = validate_image_file(input_file)
    output_path = ensure_output_directory_ready(output_directory)
    normalized_format = output_format.upper()

    if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(
            _tr("Format {format_name} is not a supported image.").format(
                format_name=input_path.suffix,
            )
        )

    if normalized_format not in OUTPUT_EXTENSIONS:
        raise UnsupportedFormatError(
            _tr("Output format {format_name} is not supported.").format(
                format_name=normalized_format,
            )
        )

    quality = max(1, min(100, int(quality)))
    ensure_sufficient_disk_space(
        output_path,
        estimate_required_space_bytes(
            input_path,
            operation="image_to_image",
            output_format=normalized_format,
        ),
    )

    requested_result_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_path,
        output_extension=OUTPUT_EXTENSIONS[normalized_format],
    )
    temporary_path = get_temporary_output_path(requested_result_path)

    try:
        _emit_status(
            status_callback,
            _tr("Opening file {file_name}...").format(
                file_name=input_path.name,
            ),
        )
        _emit_progress(progress_callback, 10)

        with Image.open(input_path) as source_image:
            source_image.load()
            image = ImageOps.exif_transpose(source_image)

            _emit_status(
                status_callback,
                _tr("Preparing image for {format_name} format...").format(
                    format_name=normalized_format,
                ),
            )
            _emit_progress(progress_callback, 35)

            prepared_image = _prepare_image(
                image=image,
                output_format=normalized_format,
            )

            _emit_status(
                status_callback,
                _tr("Saving file {file_name}...").format(
                    file_name=requested_result_path.name,
                ),
            )
            _emit_progress(progress_callback, 70)

            _save_image(
                image=prepared_image,
                output_path=temporary_path,
                output_format=normalized_format,
                quality=quality,
            )

            if prepared_image is not image:
                prepared_image.close()

        result_path = publish_temporary_file(
            temporary_path,
            requested_result_path,
        )

        _emit_progress(progress_callback, 100)
        _emit_status(status_callback, _tr("Conversion is finished."))
        return result_path

    except UnidentifiedImageError as error:
        cleanup_temporary_path(temporary_path)
        raise ImageConversionError(
            _tr("The file is not a valid image or is corrupted.")
        ) from error

    except PermissionError as error:
        cleanup_temporary_path(temporary_path)
        raise ImageConversionError(
            _tr("Permission is missing for reading or saving the file.")
        ) from error

    except ImageConversionError:
        cleanup_temporary_path(temporary_path)
        raise

    except OSError as error:
        cleanup_temporary_path(temporary_path)
        raise ImageConversionError(
            _tr("The image could not be converted: {error}").format(
                error=error,
            )
        ) from error

    except Exception:
        cleanup_temporary_path(temporary_path)
        raise


def _prepare_image(
    image: Image.Image,
    output_format: str,
) -> Image.Image:
    if output_format == "JPG":
        return _prepare_for_jpeg(image)

    if output_format == "PNG":
        if image.mode == "CMYK":
            return image.convert("RGB")

        return image.copy()

    if output_format == "WEBP":
        if _has_transparency(image):
            return image.convert("RGBA")

        return image.convert("RGB")

    raise ImageConversionError(
        _tr("Unknown output format: {format_name}").format(
            format_name=output_format,
        )
    )


def _prepare_for_jpeg(image: Image.Image) -> Image.Image:
    if _has_transparency(image):
        rgba_image = image.convert("RGBA")
        white_background = Image.new(
            mode="RGB",
            size=rgba_image.size,
            color=(255, 255, 255),
        )
        white_background.paste(
            rgba_image,
            mask=rgba_image.getchannel("A"),
        )
        rgba_image.close()
        return white_background

    return image.convert("RGB")


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return True

    if image.mode == "P" and "transparency" in image.info:
        return True

    return False


def _save_image(
    image: Image.Image,
    output_path: Path,
    output_format: str,
    quality: int,
) -> None:
    if output_format == "JPG":
        image.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True,
        )
        return

    if output_format == "WEBP":
        image.save(
            output_path,
            format="WEBP",
            quality=quality,
            method=6,
        )
        return

    if output_format == "PNG":
        image.save(
            output_path,
            format="PNG",
            optimize=True,
        )
        return

    raise UnsupportedFormatError(
        _tr("Saving format {format_name} is not supported.").format(
            format_name=output_format,
        )
    )


def _emit_progress(
    callback: ProgressCallback | None,
    value: int,
) -> None:
    if callback is not None:
        callback(value)


def _emit_status(
    callback: StatusCallback | None,
    message: str,
) -> None:
    if callback is not None:
        callback(message)


def _tr(source_text: str) -> str:
    return translate("ImageConverter", source_text)
