"""Validate conversion inputs and translate parser failures to domain errors."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.constants import IMAGE_EXTENSIONS, SUPPORTED_INPUT_EXTENSIONS
from app.exceptions import (
    CorruptedFileError,
    FileLockedError,
    InputFileError,
    UnsupportedFormatError,
)
from app.i18n import translate


def validate_input_file_for_queue(
    input_file: str | Path,
) -> Path:
    """Validate the basic requirements for adding a path to the queue."""
    return _validate_basic_input(input_file)


def validate_input_file_for_conversion(
    input_file: str | Path,
) -> Path:
    """Validate the basic requirements shared by conversion backends."""
    return _validate_basic_input(input_file)


def validate_image_file(input_file: str | Path) -> Path:
    """Return a readable supported image path after verifying its contents."""
    path = _validate_basic_input(input_file)

    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(
            _tr("The selected file is not a supported image.")
        )

    try:
        with Image.open(path) as image:
            image.verify()
    except UnidentifiedImageError as error:
        raise CorruptedFileError(
            _tr("The image is corrupted or is not a valid image file.")
        ) from error
    except OSError as error:
        raise CorruptedFileError(
            _tr("The image cannot be opened or is corrupted: {error}").format(
                error=error,
            )
        ) from error

    return path


def validate_pdf_file(input_file: str | Path) -> Path:
    """Return a readable PDF path after checking encryption and page count."""
    path = _validate_basic_input(input_file)

    if path.suffix.lower() != ".pdf":
        raise UnsupportedFormatError(
            _tr("The selected file is not a PDF.")
        )

    try:
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise CorruptedFileError(
                    _tr(
                        "The PDF is password-protected and cannot be processed."
                    )
                )

            if document.page_count <= 0:
                raise CorruptedFileError(
                    _tr("The PDF document does not contain any pages.")
                )
    except CorruptedFileError:
        raise
    except (RuntimeError, ValueError, OSError) as error:
        raise CorruptedFileError(
            _tr("The PDF cannot be opened or is corrupted: {error}").format(
                error=error,
            )
        ) from error

    return path


def _validate_basic_input(input_file: str | Path) -> Path:
    path = Path(input_file)

    if not path.exists():
        raise InputFileError(
            _tr("The selected file no longer exists.")
        )

    if not path.is_file():
        raise InputFileError(
            _tr("The selected path is not a file.")
        )

    if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        raise UnsupportedFormatError(
            _tr("The selected format is not supported.")
        )

    try:
        if path.stat().st_size <= 0:
            raise InputFileError(
                _tr("The selected file is empty.")
            )
    except OSError as error:
        raise FileLockedError(
            _tr("The file is currently being used by another program.")
        ) from error

    try:
        with path.open("rb") as file:
            file.read(1)
    except PermissionError as error:
        raise FileLockedError(
            _tr("The file is currently being used by another program.")
        ) from error
    except OSError as error:
        raise FileLockedError(
            _tr("The file is not available for reading: {error}").format(
                error=error,
            )
        ) from error

    return path


def _tr(source_text: str) -> str:
    return translate("InputValidation", source_text)
