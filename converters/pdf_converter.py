"""Convert PDFs to images and images to single or multi-page PDFs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from app.constants import IMAGE_EXTENSIONS
from app.exceptions import ConversionError, UnsupportedFormatError
from app.i18n import translate
from converters.base_converter import (
    CancelCheck,
    ConversionCancelledError,
    check_cancelled,
)
from utils.file_utils import (
    generate_unique_output_directory,
    generate_unique_output_path,
)
from utils.input_validation import (
    validate_image_file,
    validate_pdf_file,
)
from utils.output_safety import (
    cleanup_temporary_path,
    ensure_output_directory_ready,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    get_temporary_output_path,
    publish_temporary_directory,
    publish_temporary_file,
    validate_zip_file,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


class PdfConversionError(ConversionError):
    """Error raised while converting PDF files."""


PDF_IMAGE_FORMATS = {
    "PNG": ".png",
    "JPG": ".jpg",
}

MULTI_PAGE_OUTPUT_MODES = {
    "folder",
    "zip",
}

AUTO_ZIP_THRESHOLD_BYTES = 100 * 1024 * 1024


def convert_pdf_to_images(
    input_file: str | Path,
    output_directory: str | Path,
    output_format: str,
    dpi: int = 150,
    quality: int = 90,
    page_selection: str | None = None,
    multi_page_output_mode: str = "folder",
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    """Render selected PDF pages to one image, a folder, or a ZIP archive."""
    input_path = validate_pdf_file(input_file)
    output_path = ensure_output_directory_ready(output_directory)
    normalized_format = output_format.upper()
    normalized_output_mode = multi_page_output_mode.lower().strip()

    if normalized_format not in PDF_IMAGE_FORMATS:
        raise UnsupportedFormatError(
            _tr("PDF cannot be converted to {format_name}.").format(
                format_name=normalized_format,
            )
        )

    if normalized_output_mode not in MULTI_PAGE_OUTPUT_MODES:
        raise PdfConversionError(
            _tr("Unknown save mode for multiple PDF pages.")
        )

    dpi = max(72, min(600, int(dpi)))
    quality = max(1, min(100, int(quality)))

    _emit_status(status_callback, _tr("Opening PDF document..."))
    _emit_progress(progress_callback, 5)
    check_cancelled(cancel_check)

    try:
        with pymupdf.open(input_path) as document:
            check_cancelled(cancel_check)

            if document.needs_pass:
                raise PdfConversionError(
                    _tr("The PDF is password-protected.")
                )

            if document.page_count == 0:
                raise PdfConversionError(
                    _tr("The PDF document does not contain any pages.")
                )

            ensure_sufficient_disk_space(
                output_path,
                estimate_required_space_bytes(
                    input_path,
                    operation="pdf_to_images",
                    output_format=normalized_format,
                    dpi=dpi,
                    page_count=document.page_count,
                ),
            )

            page_indexes = parse_page_selection(
                selection=page_selection,
                page_count=document.page_count,
            )
            _emit_progress(progress_callback, 10)

            if len(page_indexes) == 1:
                return _convert_single_pdf_page(
                    document=document,
                    input_path=input_path,
                    output_directory=output_path,
                    page_index=page_indexes[0],
                    output_format=normalized_format,
                    dpi=dpi,
                    quality=quality,
                    cancel_check=cancel_check,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                )

            return _convert_multiple_pdf_pages(
                document=document,
                input_path=input_path,
                output_directory=output_path,
                page_indexes=page_indexes,
                output_format=normalized_format,
                dpi=dpi,
                quality=quality,
                multi_page_output_mode=normalized_output_mode,
                progress_callback=progress_callback,
                status_callback=status_callback,
                cancel_check=cancel_check,
            )

    except PdfConversionError:
        raise
    except (RuntimeError, ValueError, OSError) as error:
        raise PdfConversionError(
            _tr("The PDF could not be processed: {error}").format(
                error=error,
            )
        ) from error


def convert_image_to_pdf(
    input_file: str | Path,
    output_directory: str | Path,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    """Convert one supported image into a uniquely named PDF."""
    input_path = validate_image_file(input_file)
    output_path = ensure_output_directory_ready(output_directory)

    if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(
            _tr("The selected image format is not supported.")
        )

    ensure_sufficient_disk_space(
        output_path,
        estimate_required_space_bytes(
            input_path,
            operation="image_to_pdf",
        ),
    )

    result_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_path,
        output_extension=".pdf",
    )
    temporary_path = get_temporary_output_path(result_path)

    try:
        _emit_status(status_callback, _tr("Opening image..."))
        _emit_progress(progress_callback, 15)

        with Image.open(input_path) as source_image:
            source_image.load()
            image = ImageOps.exif_transpose(source_image)

            _emit_status(status_callback, _tr("Preparing image for PDF..."))
            _emit_progress(progress_callback, 45)

            prepared_image = _prepare_image_for_pdf(image)

            _emit_status(status_callback, _tr("Saving PDF..."))
            _emit_progress(progress_callback, 75)

            prepared_image.save(
                temporary_path,
                format="PDF",
                resolution=300.0,
            )
            prepared_image.close()

        result_path = publish_temporary_file(
            temporary_path,
            result_path,
        )

        _emit_progress(progress_callback, 100)
        _emit_status(status_callback, _tr("Conversion is finished."))
        return result_path

    except UnidentifiedImageError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("The file is not a valid image or is corrupted.")
        ) from error
    except PermissionError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("Permission is missing for reading or saving the file.")
        ) from error
    except PdfConversionError:
        cleanup_temporary_path(temporary_path)
        raise
    except OSError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("The image could not be converted to PDF: {error}").format(
                error=error,
            )
        ) from error
    except Exception:
        cleanup_temporary_path(temporary_path)
        raise


def convert_images_to_pdf(
    input_files: list[str | Path],
    output_directory: str | Path,
    output_filename: str = "combined.pdf",
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    """Combine two or more images into an ordered multi-page PDF."""
    if len(input_files) < 2:
        raise PdfConversionError(
            _tr("Choose at least two images for a combined PDF.")
        )

    input_paths = [validate_image_file(path) for path in input_files]
    output_path = ensure_output_directory_ready(output_directory)
    ensure_sufficient_disk_space(
        output_path,
        estimate_required_space_bytes(
            input_paths,
            operation="images_to_pdf",
        ),
    )
    requested_name = Path(output_filename).name.strip() or "combined.pdf"

    if Path(requested_name).suffix.lower() != ".pdf":
        requested_name = f"{requested_name}.pdf"

    result_path = generate_unique_output_path(
        input_file=Path(requested_name),
        output_directory=output_path,
        output_extension=".pdf",
    )
    temporary_path = get_temporary_output_path(result_path)
    prepared_images: list[Image.Image] = []

    try:
        total_images = len(input_paths)

        for position, input_path in enumerate(input_paths, start=1):
            check_cancelled(cancel_check)
            _emit_status(
                status_callback,
                _tr(
                    "Preparing image {position} of {total}: {file_name}"
                ).format(
                    position=position,
                    total=total_images,
                    file_name=input_path.name,
                ),
            )

            with Image.open(input_path) as source_image:
                source_image.load()
                image = ImageOps.exif_transpose(source_image)
                prepared_images.append(
                    _prepare_image_for_pdf(image)
                )

            progress = int((position / total_images) * 85)
            _emit_progress(progress_callback, progress)

        check_cancelled(cancel_check)

        _emit_status(
            status_callback,
            _tr("Saving PDF {file_name}...").format(
                file_name=result_path.name,
            ),
        )
        _emit_progress(progress_callback, 90)

        first_image = prepared_images[0]
        remaining_images = prepared_images[1:]
        first_image.save(
            temporary_path,
            format="PDF",
            save_all=True,
            append_images=remaining_images,
            resolution=300.0,
        )

        check_cancelled(cancel_check)
        result_path = publish_temporary_file(
            temporary_path,
            result_path,
        )

        _emit_progress(progress_callback, 100)
        _emit_status(
            status_callback,
            _tr("Images were merged into a PDF successfully."),
        )
        return result_path

    except ConversionCancelledError:
        cleanup_temporary_path(temporary_path)
        raise
    except UnidentifiedImageError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("One of the files is not a valid image or is corrupted.")
        ) from error
    except PermissionError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("Permission is missing for reading or saving the file.")
        ) from error
    except PdfConversionError:
        cleanup_temporary_path(temporary_path)
        raise
    except OSError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("The images could not be merged into a PDF: {error}").format(
                error=error,
            )
        ) from error
    except Exception:
        cleanup_temporary_path(temporary_path)
        raise
    finally:
        for image in prepared_images:
            image.close()


def parse_page_selection(
    selection: str | None,
    page_count: int,
) -> list[int]:
    """Parse one-based page numbers/ranges into unique zero-based indexes."""
    if page_count <= 0:
        raise PdfConversionError(
            _tr("The PDF has no available pages.")
        )

    if selection is None or not selection.strip():
        return list(range(page_count))

    cleaned_selection = selection.replace(" ", "")
    selected_pages: list[int] = []

    for part in cleaned_selection.split(","):
        if not part:
            raise PdfConversionError(
                _tr("Invalid page selection.")
            )

        if "-" in part:
            range_parts = part.split("-")

            if len(range_parts) != 2:
                raise PdfConversionError(
                    _tr("Invalid page range: {range_text}").format(
                        range_text=part,
                    )
                )

            start_text, end_text = range_parts

            if not start_text.isdigit() or not end_text.isdigit():
                raise PdfConversionError(
                    _tr("Invalid page range: {range_text}").format(
                        range_text=part,
                    )
                )

            start_page = int(start_text)
            end_page = int(end_text)

            if start_page > end_page:
                raise PdfConversionError(
                    _tr(
                        "The start of the range must be lower than the end: {range_text}"
                    ).format(range_text=part)
                )

            for page_number in range(start_page, end_page + 1):
                _validate_page_number(page_number, page_count)
                page_index = page_number - 1

                if page_index not in selected_pages:
                    selected_pages.append(page_index)

        else:
            if not part.isdigit():
                raise PdfConversionError(
                    _tr("Invalid page number: {page_text}").format(
                        page_text=part,
                    )
                )

            page_number = int(part)
            _validate_page_number(page_number, page_count)
            page_index = page_number - 1

            if page_index not in selected_pages:
                selected_pages.append(page_index)

    if not selected_pages:
        raise PdfConversionError(
            _tr("No pages were selected.")
        )

    return selected_pages


def _convert_single_pdf_page(
    document: pymupdf.Document,
    input_path: Path,
    output_directory: Path,
    page_index: int,
    output_format: str,
    dpi: int,
    quality: int,
    cancel_check: CancelCheck | None,
    progress_callback: ProgressCallback | None,
    status_callback: StatusCallback | None,
) -> Path:
    page_number = page_index + 1
    extension = PDF_IMAGE_FORMATS[output_format]
    result_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_directory,
        output_extension=extension,
        name_suffix=f"_page_{page_number}",
    )
    temporary_path = get_temporary_output_path(result_path)

    _emit_status(
        status_callback,
        _tr("Converting page {page_number}...").format(
            page_number=page_number,
        ),
    )
    _emit_progress(progress_callback, 35)
    check_cancelled(cancel_check)

    image = _render_pdf_page(
        document=document,
        page_index=page_index,
        dpi=dpi,
    )

    try:
        _emit_progress(progress_callback, 70)
        _save_rendered_page(
            image=image,
            output_path=temporary_path,
            output_format=output_format,
            quality=quality,
        )
        check_cancelled(cancel_check)
        result_path = publish_temporary_file(
            temporary_path,
            result_path,
        )
    except Exception:
        cleanup_temporary_path(temporary_path)
        raise
    finally:
        image.close()

    _emit_progress(progress_callback, 100)
    _emit_status(status_callback, _tr("Conversion is finished."))
    return result_path


def _convert_multiple_pdf_pages(
    document: pymupdf.Document,
    input_path: Path,
    output_directory: Path,
    page_indexes: list[int],
    output_format: str,
    dpi: int,
    quality: int,
    multi_page_output_mode: str,
    progress_callback: ProgressCallback | None,
    status_callback: StatusCallback | None,
    cancel_check: CancelCheck | None,
) -> Path:
    extension = PDF_IMAGE_FORMATS[output_format]
    number_width = max(2, len(str(document.page_count)))

    with TemporaryDirectory(
        prefix="lfc_pdf_pages_",
        ignore_cleanup_errors=True,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        rendered_paths: list[Path] = []
        total_pages = len(page_indexes)

        for position, page_index in enumerate(page_indexes, start=1):
            check_cancelled(cancel_check)
            page_number = page_index + 1

            _emit_status(
                status_callback,
                _tr(
                    "Converting page {page_number} ({position} of {total})..."
                ).format(
                    page_number=page_number,
                    position=position,
                    total=total_pages,
                ),
            )

            image = _render_pdf_page(
                document=document,
                page_index=page_index,
                dpi=dpi,
            )
            page_filename = (
                f"{input_path.stem}_page_"
                f"{page_number:0{number_width}d}"
                f"{extension}"
            )
            rendered_path = temporary_path / page_filename

            try:
                _save_rendered_page(
                    image=image,
                    output_path=rendered_path,
                    output_format=output_format,
                    quality=quality,
                )
            finally:
                image.close()

            rendered_paths.append(rendered_path)
            check_cancelled(cancel_check)

            progress = 10 + int((position / total_pages) * 75)
            _emit_progress(progress_callback, progress)

        total_size_bytes = sum(path.stat().st_size for path in rendered_paths)
        automatic_zip = (
            multi_page_output_mode == "folder"
            and total_size_bytes > AUTO_ZIP_THRESHOLD_BYTES
        )
        should_create_zip = (
            multi_page_output_mode == "zip"
            or automatic_zip
        )
        check_cancelled(cancel_check)

        if should_create_zip:
            if automatic_zip:
                size_mb = total_size_bytes / (1024 * 1024)
                _emit_status(
                    status_callback,
                    _tr(
                        "The result is {size_mb:.1f} MB. Packing into ZIP automatically..."
                    ).format(size_mb=size_mb),
                )
            else:
                _emit_status(
                    status_callback,
                    _tr("Packing images into a ZIP archive..."),
                )

            _emit_progress(progress_callback, 90)
            zip_path = _create_zip_result(
                input_path=input_path,
                output_directory=output_directory,
                rendered_paths=rendered_paths,
            )
            _emit_progress(progress_callback, 100)

            if automatic_zip:
                _emit_status(
                    status_callback,
                    _tr(
                        "Conversion is finished. The result was automatically zipped because it exceeded 100 MB."
                    ),
                )
            else:
                _emit_status(
                    status_callback,
                    _tr("Conversion and ZIP packing are finished."),
                )

            return zip_path

        _emit_status(
            status_callback,
            _tr("Saving images into a plain folder..."),
        )
        _emit_progress(progress_callback, 90)
        result_directory = _create_folder_result(
            input_path=input_path,
            output_directory=output_directory,
            rendered_paths=rendered_paths,
        )
        _emit_progress(progress_callback, 100)
        _emit_status(
            status_callback,
            _tr("Conversion is finished and images were saved into a folder."),
        )
        return result_directory


def _create_folder_result(
    input_path: Path,
    output_directory: Path,
    rendered_paths: list[Path],
) -> Path:
    result_directory = generate_unique_output_directory(
        input_file=input_path,
        output_directory=output_directory,
        name_suffix="_pages",
    )

    with TemporaryDirectory(
        prefix="lfc_result_pages_",
        dir=output_directory,
        ignore_cleanup_errors=True,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)

        try:
            for rendered_path in rendered_paths:
                destination_path = temporary_path / rendered_path.name
                rendered_path.rename(destination_path)

            return publish_temporary_directory(
                temporary_path,
                result_directory,
            )
        except OSError as error:
            cleanup_temporary_path(temporary_path)
            raise PdfConversionError(
                _tr("Could not save the output folder: {error}").format(
                    error=error,
                )
            ) from error
        except Exception:
            cleanup_temporary_path(temporary_path)
            raise


def _create_zip_result(
    input_path: Path,
    output_directory: Path,
    rendered_paths: list[Path],
) -> Path:
    zip_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_directory,
        output_extension=".zip",
        name_suffix="_pages",
    )
    temporary_path = get_temporary_output_path(zip_path)

    try:
        with ZipFile(
            temporary_path,
            mode="w",
            compression=ZIP_DEFLATED,
        ) as archive:
            for rendered_path in rendered_paths:
                archive.write(
                    rendered_path,
                    arcname=rendered_path.name,
                )

        validate_zip_file(temporary_path)
        return publish_temporary_file(temporary_path, zip_path)

    except OSError as error:
        cleanup_temporary_path(temporary_path)
        raise PdfConversionError(
            _tr("Could not create the ZIP archive: {error}").format(
                error=error,
            )
        ) from error
    except Exception:
        cleanup_temporary_path(temporary_path)
        raise


def _render_pdf_page(
    document: pymupdf.Document,
    page_index: int,
    dpi: int,
) -> Image.Image:
    page = document.load_page(page_index)
    zoom = dpi / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(
        matrix=matrix,
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    return Image.frombytes(
        "RGB",
        (pixmap.width, pixmap.height),
        pixmap.samples,
    )


def _save_rendered_page(
    image: Image.Image,
    output_path: Path,
    output_format: str,
    quality: int,
) -> None:
    if output_format == "PNG":
        image.save(
            output_path,
            format="PNG",
            optimize=True,
        )
        return

    if output_format == "JPG":
        image.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True,
        )
        return

    raise UnsupportedFormatError(
        _tr("Unsupported output format: {format_name}").format(
            format_name=output_format,
        )
    )


def _prepare_image_for_pdf(image: Image.Image) -> Image.Image:
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


def _validate_page_number(
    page_number: int,
    page_count: int,
) -> None:
    if page_number < 1 or page_number > page_count:
        raise PdfConversionError(
            _tr(
                "Page {page_number} does not exist. The PDF has {page_count} pages."
            ).format(
                page_number=page_number,
                page_count=page_count,
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
    return translate("PdfConverter", source_text)
