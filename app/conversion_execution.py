from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import time

import pymupdf

from app.constants import (
    IMAGE_EXTENSIONS,
    OFFICE_EXTENSIONS,
)
from app.exceptions import DependencyNotFoundError, UnsupportedFormatError
from app.settings import (
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    DEFAULT_PDF_DPI,
)
from converters.base_converter import CancelCheck, ConversionCancelledError
from converters.image_converter import convert_image
from converters.office_converter import convert_office_to_pdf
from converters.pdf_converter import (
    convert_image_to_pdf,
    convert_pdf_to_images,
)
from utils.input_validation import validate_input_file_for_conversion
from utils.logging_utils import (
    LOGGER_NAME,
    log_exception_safely,
    sanitize_path,
)
from utils.output_safety import (
    ensure_output_directory_ready,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    human_readable_size,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


def run_conversion(
    input_file: str | Path,
    output_directory: str | Path,
    output_format: str,
    quality: int = DEFAULT_IMAGE_QUALITY,
    dpi: int = DEFAULT_PDF_DPI,
    page_selection: str | None = None,
    multi_page_output_mode: str = DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    libreoffice_path: str | Path | None = None,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    logger = logging.getLogger(LOGGER_NAME)
    started_at = time.monotonic()
    input_path = validate_input_file_for_conversion(input_file)
    output_path = ensure_output_directory_ready(output_directory)
    normalized_format = output_format.upper()
    extension = input_path.suffix.lower()
    operation = _operation_for_conversion(
        extension=extension,
        output_format=normalized_format,
    )
    page_count = (
        _safe_pdf_page_count(input_path)
        if extension == ".pdf"
        else None
    )
    required_bytes = estimate_required_space_bytes(
        input_path,
        operation=operation,
        output_format=normalized_format,
        dpi=dpi,
        page_count=page_count,
    )
    disk_check = ensure_sufficient_disk_space(
        output_path,
        required_bytes,
    )

    logger.info(
        (
            "Conversion started input=%s output_format=%s "
            "operation=%s engine=%s estimated_space=%s available=%s"
        ),
        sanitize_path(input_path),
        normalized_format,
        operation,
        "libreoffice" if extension in OFFICE_EXTENSIONS else "internal",
        human_readable_size(disk_check.required_bytes),
        human_readable_size(disk_check.available_bytes),
    )

    try:
        result_path = _run_converter(
            input_path=input_path,
            output_path=output_path,
            extension=extension,
            output_format=normalized_format,
            quality=quality,
            dpi=dpi,
            page_selection=page_selection,
            multi_page_output_mode=multi_page_output_mode,
            libreoffice_path=libreoffice_path,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )
        _log_success(
            logger=logger,
            input_path=input_path,
            result_path=result_path,
            started_at=started_at,
        )
        return result_path

    except ConversionCancelledError:
        duration_seconds = time.monotonic() - started_at
        logger.info(
            "Conversion cancelled input=%s duration=%.2fs",
            sanitize_path(input_path),
            duration_seconds,
        )
        raise

    except Exception:
        duration_seconds = time.monotonic() - started_at
        log_exception_safely(
            logger,
            (
                "Conversion failed input=%s output_format=%s "
                "duration=%.2fs"
            ),
            sanitize_path(input_path),
            normalized_format,
            duration_seconds,
        )
        raise


def _run_converter(
    *,
    input_path: Path,
    output_path: Path,
    extension: str,
    output_format: str,
    quality: int,
    dpi: int,
    page_selection: str | None,
    multi_page_output_mode: str,
    libreoffice_path: str | Path | None,
    cancel_check: CancelCheck | None,
    progress_callback: ProgressCallback | None,
    status_callback: StatusCallback | None,
) -> Path:
    if extension in IMAGE_EXTENSIONS:
        if output_format == "PDF":
            return convert_image_to_pdf(
                input_file=input_path,
                output_directory=output_path,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )

        return convert_image(
            input_file=input_path,
            output_directory=output_path,
            output_format=output_format,
            quality=quality,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    if extension == ".pdf":
        return convert_pdf_to_images(
            input_file=input_path,
            output_directory=output_path,
            output_format=output_format,
            dpi=dpi,
            quality=quality,
            page_selection=page_selection,
            multi_page_output_mode=multi_page_output_mode,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    if extension in OFFICE_EXTENSIONS:
        if output_format != "PDF":
            raise UnsupportedFormatError(
                "Office dokumenti trenutno se mogu pretvoriti samo u PDF."
            )

        if libreoffice_path is None:
            raise DependencyNotFoundError(
                "LibreOffice putanja nije postavljena."
            )

        return convert_office_to_pdf(
            input_file=input_path,
            output_directory=output_path,
            libreoffice_executable=libreoffice_path,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    raise UnsupportedFormatError(
        "Odabrani format jos nije podrzan za konverziju."
    )


def _operation_for_conversion(
    *,
    extension: str,
    output_format: str,
) -> str:
    if extension in IMAGE_EXTENSIONS:
        return "image_to_pdf" if output_format == "PDF" else "image_to_image"

    if extension == ".pdf":
        return "pdf_to_images"

    if extension in OFFICE_EXTENSIONS:
        return "office_to_pdf"

    return "unknown"


def _safe_pdf_page_count(input_path: Path) -> int | None:
    try:
        with pymupdf.open(input_path) as document:
            return document.page_count
    except Exception:
        return None


def _log_success(
    *,
    logger: logging.Logger,
    input_path: Path,
    result_path: Path,
    started_at: float,
) -> None:
    duration_seconds = time.monotonic() - started_at
    logger.info(
        "Conversion finished input=%s result=%s duration=%.2fs",
        sanitize_path(input_path),
        sanitize_path(result_path),
        duration_seconds,
    )
