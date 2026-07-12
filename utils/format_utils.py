from pathlib import Path

from app.constants import (
    DISPLAY_FORMAT_NAMES,
    OUTPUT_FORMATS_BY_EXTENSION,
    SUPPORTED_INPUT_EXTENSIONS,
)


def get_file_extension(file_path: str | Path) -> str:
    """Vraća ekstenziju datoteke malim slovima, uključujući točku."""
    return Path(file_path).suffix.lower()


def is_supported_file(file_path: str | Path) -> bool:
    """Provjerava postoji li datoteka i podržava li aplikacija njezin format."""
    path = Path(file_path)

    return (
        path.exists()
        and path.is_file()
        and get_file_extension(path) in SUPPORTED_INPUT_EXTENSIONS
    )


def get_display_format(file_path: str | Path) -> str:
    """Vraća naziv formata prikladan za prikaz u sučelju."""
    extension = get_file_extension(file_path)
    return DISPLAY_FORMAT_NAMES.get(extension, "Nepoznat format")


def get_available_output_formats(file_path: str | Path) -> list[str]:
    """Vraća podržane izlazne formate za odabranu datoteku."""
    extension = get_file_extension(file_path)
    return OUTPUT_FORMATS_BY_EXTENSION.get(extension, [])
