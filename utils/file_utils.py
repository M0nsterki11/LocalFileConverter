"""Filesystem naming and shell-opening helpers."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.settings import DEFAULT_OUTPUT_DIRECTORY


def get_default_output_directory() -> Path:
    """Return the application's default output directory."""
    return DEFAULT_OUTPUT_DIRECTORY


def generate_unique_output_path(
    input_file: str | Path,
    output_directory: str | Path,
    output_extension: str,
    name_suffix: str = "",
) -> Path:
    """
    Generate a unique output path without overwriting files.

    Examples:
    image.png
    image_1.png
    document_pages.zip
    document_pages_1.zip
    """
    input_path = Path(input_file)
    output_path = Path(output_directory)

    normalized_extension = output_extension.lower()

    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"

    base_name = f"{input_path.stem}{name_suffix}"

    candidate = output_path / f"{base_name}{normalized_extension}"
    counter = 1

    while candidate.exists():
        candidate = (
            output_path
            / f"{base_name}_{counter}{normalized_extension}"
        )
        counter += 1

    return candidate


def generate_unique_output_directory(
    input_file: str | Path,
    output_directory: str | Path,
    name_suffix: str = "_pages",
) -> Path:
    """
    Generate a unique output directory name.

    Examples:
    document_pages
    document_pages_1
    document_pages_2
    """
    input_path = Path(input_file)
    output_path = Path(output_directory)

    base_name = f"{input_path.stem}{name_suffix}"

    candidate = output_path / base_name
    counter = 1

    while candidate.exists():
        candidate = output_path / f"{base_name}_{counter}"
        counter += 1

    return candidate


def open_directory(directory: str | Path) -> bool:
    """Create the directory if needed and open it in Windows Explorer."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    return QDesktopServices.openUrl(
        QUrl.fromLocalFile(str(path.resolve()))
    )
