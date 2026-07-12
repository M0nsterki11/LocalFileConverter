from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from app.constants import APP_STORAGE_DIRECTORY_NAME


def get_default_output_directory() -> Path:
    """Vraća zadanu mapu u koju će se spremati konvertirane datoteke."""
    return Path.home() / "Documents" / APP_STORAGE_DIRECTORY_NAME / "Converted"


def open_directory(directory: str | Path) -> bool:
    """Stvara mapu ako ne postoji i otvara je u Windows Exploreru."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
