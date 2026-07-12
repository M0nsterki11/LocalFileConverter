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


def validate_input_file_for_queue(
    input_file: str | Path,
) -> Path:
    return _validate_basic_input(input_file)


def validate_input_file_for_conversion(
    input_file: str | Path,
) -> Path:
    return _validate_basic_input(input_file)


def validate_image_file(input_file: str | Path) -> Path:
    path = _validate_basic_input(input_file)

    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise UnsupportedFormatError(
            "Odabrana datoteka nije podrzana slika."
        )

    try:
        with Image.open(path) as image:
            image.verify()
    except UnidentifiedImageError as error:
        raise CorruptedFileError(
            "Slika je ostecena ili nije valjana slikovna datoteka."
        ) from error
    except OSError as error:
        raise CorruptedFileError(
            f"Slika se ne moze otvoriti ili je ostecena: {error}"
        ) from error

    return path


def validate_pdf_file(input_file: str | Path) -> Path:
    path = _validate_basic_input(input_file)

    if path.suffix.lower() != ".pdf":
        raise UnsupportedFormatError(
            "Odabrana datoteka nije PDF."
        )

    try:
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise CorruptedFileError(
                    "PDF je zakljucan lozinkom i ne moze se obraditi."
                )

            if document.page_count <= 0:
                raise CorruptedFileError(
                    "PDF dokument nema nijednu stranicu."
                )
    except CorruptedFileError:
        raise
    except (RuntimeError, ValueError, OSError) as error:
        raise CorruptedFileError(
            f"PDF se ne moze otvoriti ili je ostecen: {error}"
        ) from error

    return path


def _validate_basic_input(input_file: str | Path) -> Path:
    path = Path(input_file)

    if not path.exists():
        raise InputFileError(
            "Odabrana datoteka vise ne postoji."
        )

    if not path.is_file():
        raise InputFileError(
            "Odabrana putanja nije datoteka."
        )

    if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        raise UnsupportedFormatError(
            "Odabrani format nije podrzan."
        )

    try:
        if path.stat().st_size <= 0:
            raise InputFileError(
                "Odabrana datoteka je prazna."
            )
    except OSError as error:
        raise FileLockedError(
            "Datoteku trenutacno koristi drugi program."
        ) from error

    try:
        with path.open("rb") as file:
            file.read(1)
    except PermissionError as error:
        raise FileLockedError(
            "Datoteku trenutacno koristi drugi program."
        ) from error
    except OSError as error:
        raise FileLockedError(
            f"Datoteka nije dostupna za citanje: {error}"
        ) from error

    return path
