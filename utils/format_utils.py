from pathlib import Path

from app.constants import (
    DISPLAY_FORMAT_NAMES,
    OUTPUT_FORMATS_BY_EXTENSION,
    SUPPORTED_INPUT_EXTENSIONS,
)


def get_file_extension(file_path: str | Path) -> str:
    """Return the lowercase file extension, including the dot."""
    return Path(file_path).suffix.lower()


def is_supported_file(file_path: str | Path) -> bool:
    """Return whether the path exists and has a supported format."""
    path = Path(file_path)

    return (
        path.exists()
        and path.is_file()
        and get_file_extension(path) in SUPPORTED_INPUT_EXTENSIONS
    )


def get_display_format(file_path: str | Path) -> str:
    """Return a display-friendly format name."""
    extension = get_file_extension(file_path)
    return DISPLAY_FORMAT_NAMES.get(extension, "Unknown format")


def get_available_output_formats(file_path: str | Path) -> list[str]:
    """Return supported output formats for the selected file."""
    extension = get_file_extension(file_path)
    return OUTPUT_FORMATS_BY_EXTENSION.get(extension, [])
