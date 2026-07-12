from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def get_default_output_directory() -> Path:
    """Vraća zadanu izlaznu mapu aplikacije."""
    return Path.home() / "Documents" / "LocalFileConverter" / "Converted"


def generate_unique_output_path(
    input_file: str | Path,
    output_directory: str | Path,
    output_extension: str,
) -> Path:
    """
    Generira izlaznu putanju bez prepisivanja postojeće datoteke.

    Primjer:
    slika.png
    slika_1.png
    slika_2.png
    """
    input_path = Path(input_file)
    output_path = Path(output_directory)

    normalized_extension = output_extension.lower()

    if not normalized_extension.startswith("."):
        normalized_extension = f".{normalized_extension}"

    candidate = output_path / f"{input_path.stem}{normalized_extension}"
    counter = 1

    while candidate.exists():
        candidate = (
            output_path
            / f"{input_path.stem}_{counter}{normalized_extension}"
        )
        counter += 1

    return candidate


def open_directory(directory: str | Path) -> bool:
    """Stvara mapu ako ne postoji i otvara je u Windows Exploreru."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    return QDesktopServices.openUrl(
        QUrl.fromLocalFile(str(path.resolve()))
    )