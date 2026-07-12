from pathlib import Path

from PySide6.QtCore import QSettings


LIBREOFFICE_PATH_KEY = "libreoffice/executable_path"


def get_saved_libreoffice_path() -> Path | None:
    """Dohvaća prethodno spremljenu LibreOffice putanju."""
    settings = QSettings()
    saved_value = settings.value(
        LIBREOFFICE_PATH_KEY,
        "",
        type=str,
    )

    if not saved_value:
        return None

    return Path(saved_value)


def save_libreoffice_path(path: str | Path) -> None:
    """Sprema LibreOffice putanju u Windows postavke aplikacije."""
    settings = QSettings()
    settings.setValue(
        LIBREOFFICE_PATH_KEY,
        str(Path(path)),
    )
    settings.sync()


def clear_libreoffice_path() -> None:
    """Briše neispravnu spremljenu LibreOffice putanju."""
    settings = QSettings()
    settings.remove(LIBREOFFICE_PATH_KEY)
    settings.sync()