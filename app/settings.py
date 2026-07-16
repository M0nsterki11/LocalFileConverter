from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

from app.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_KEY,
    validate_language,
)


DEFAULT_THEME = "system"
DEFAULT_OUTPUT_DIRECTORY = (
    Path.home()
    / "Documents"
    / "LocalFileConverter"
    / "Converted"
)
DEFAULT_OPEN_OUTPUT_AFTER_SUCCESS = False
DEFAULT_SHOW_BATCH_SUMMARY = True
DEFAULT_IMAGE_QUALITY = 90
DEFAULT_PDF_DPI = 150
DEFAULT_MULTI_PAGE_OUTPUT_MODE = "folder"
DEFAULT_OFFICE_ENGINE = "auto"

VALID_THEMES = {"system", "light", "dark"}
VALID_PDF_DPI_VALUES = {96, 150, 200, 300}
VALID_MULTI_PAGE_OUTPUT_MODES = {"folder", "zip"}
VALID_OFFICE_ENGINES = {"auto", "libreoffice"}

THEME_KEY = "ui/theme"
DEFAULT_OUTPUT_DIRECTORY_KEY = "paths/default_output_directory"
OPEN_OUTPUT_AFTER_SUCCESS_KEY = "behavior/open_output_after_success"
SHOW_BATCH_SUMMARY_KEY = "behavior/show_batch_summary"
DEFAULT_IMAGE_QUALITY_KEY = "images/default_quality"
DEFAULT_PDF_DPI_KEY = "pdf/default_dpi"
DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY = "pdf/default_multi_page_output_mode"
DEFAULT_OFFICE_ENGINE_KEY = "office/default_engine"
LIBREOFFICE_PATH_KEY = "libreoffice/executable_path"
WINDOW_GEOMETRY_KEY = "window/geometry"
WINDOW_STATE_KEY = "window/state"
LAST_FILE_DIALOG_DIRECTORY_KEY = "paths/last_file_dialog_directory"


@dataclass
class AppSettings:
    theme: str = DEFAULT_THEME
    default_output_directory: Path = DEFAULT_OUTPUT_DIRECTORY
    open_output_after_success: bool = DEFAULT_OPEN_OUTPUT_AFTER_SUCCESS
    show_batch_summary: bool = DEFAULT_SHOW_BATCH_SUMMARY
    default_image_quality: int = DEFAULT_IMAGE_QUALITY
    default_pdf_dpi: int = DEFAULT_PDF_DPI
    default_multi_page_output_mode: str = (
        DEFAULT_MULTI_PAGE_OUTPUT_MODE
    )
    default_office_engine: str = DEFAULT_OFFICE_ENGINE
    language: str = DEFAULT_LANGUAGE
    last_file_dialog_directory: Path = DEFAULT_OUTPUT_DIRECTORY


def load_app_settings() -> AppSettings:
    settings = QSettings()

    return AppSettings(
        theme=validate_theme(
            _read_string(settings, THEME_KEY, DEFAULT_THEME)
        ),
        default_output_directory=validate_output_directory(
            _read_string(
                settings,
                DEFAULT_OUTPUT_DIRECTORY_KEY,
                str(DEFAULT_OUTPUT_DIRECTORY),
            )
        ),
        open_output_after_success=_read_bool(
            settings,
            OPEN_OUTPUT_AFTER_SUCCESS_KEY,
            DEFAULT_OPEN_OUTPUT_AFTER_SUCCESS,
        ),
        show_batch_summary=_read_bool(
            settings,
            SHOW_BATCH_SUMMARY_KEY,
            DEFAULT_SHOW_BATCH_SUMMARY,
        ),
        default_image_quality=validate_image_quality(
            _read_int(
                settings,
                DEFAULT_IMAGE_QUALITY_KEY,
                DEFAULT_IMAGE_QUALITY,
            )
        ),
        default_pdf_dpi=validate_pdf_dpi(
            _read_int(
                settings,
                DEFAULT_PDF_DPI_KEY,
                DEFAULT_PDF_DPI,
            )
        ),
        default_multi_page_output_mode=validate_multi_page_output_mode(
            _read_string(
                settings,
                DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY,
                DEFAULT_MULTI_PAGE_OUTPUT_MODE,
            )
        ),
        default_office_engine=validate_office_engine(
            _read_string(
                settings,
                DEFAULT_OFFICE_ENGINE_KEY,
                DEFAULT_OFFICE_ENGINE,
            )
        ),
        language=validate_language(
            _read_string(
                settings,
                LANGUAGE_KEY,
                DEFAULT_LANGUAGE,
            )
        ),
        last_file_dialog_directory=validate_dialog_directory(
            _read_string(
                settings,
                LAST_FILE_DIALOG_DIRECTORY_KEY,
                str(DEFAULT_OUTPUT_DIRECTORY),
            )
        ),
    )


def save_app_settings(app_settings: AppSettings) -> None:
    settings = QSettings()
    settings.setValue(
        THEME_KEY,
        validate_theme(app_settings.theme),
    )
    settings.setValue(
        DEFAULT_OUTPUT_DIRECTORY_KEY,
        str(
            validate_output_directory(
                app_settings.default_output_directory
            )
        ),
    )
    settings.setValue(
        OPEN_OUTPUT_AFTER_SUCCESS_KEY,
        bool(app_settings.open_output_after_success),
    )
    settings.setValue(
        SHOW_BATCH_SUMMARY_KEY,
        bool(app_settings.show_batch_summary),
    )
    settings.setValue(
        DEFAULT_IMAGE_QUALITY_KEY,
        validate_image_quality(app_settings.default_image_quality),
    )
    settings.setValue(
        DEFAULT_PDF_DPI_KEY,
        validate_pdf_dpi(app_settings.default_pdf_dpi),
    )
    settings.setValue(
        DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY,
        validate_multi_page_output_mode(
            app_settings.default_multi_page_output_mode
        ),
    )
    settings.setValue(
        DEFAULT_OFFICE_ENGINE_KEY,
        validate_office_engine(app_settings.default_office_engine),
    )
    settings.setValue(
        LANGUAGE_KEY,
        validate_language(app_settings.language),
    )
    settings.setValue(
        LAST_FILE_DIALOG_DIRECTORY_KEY,
        str(validate_dialog_directory(
            app_settings.last_file_dialog_directory
        )),
    )
    settings.sync()


def reset_app_settings() -> AppSettings:
    settings = QSettings()

    for key in (
        THEME_KEY,
        DEFAULT_OUTPUT_DIRECTORY_KEY,
        OPEN_OUTPUT_AFTER_SUCCESS_KEY,
        SHOW_BATCH_SUMMARY_KEY,
        DEFAULT_IMAGE_QUALITY_KEY,
        DEFAULT_PDF_DPI_KEY,
        DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY,
        DEFAULT_OFFICE_ENGINE_KEY,
        LANGUAGE_KEY,
        LAST_FILE_DIALOG_DIRECTORY_KEY,
    ):
        settings.remove(key)

    defaults = AppSettings()
    save_app_settings(defaults)
    return defaults


def validate_theme(value: object) -> str:
    text = str(value or "").strip().lower()

    if text in VALID_THEMES:
        return text

    return DEFAULT_THEME


def validate_output_directory(value: object) -> Path:
    raw_value = str(value or "").strip()

    if not raw_value:
        return DEFAULT_OUTPUT_DIRECTORY

    path = Path(raw_value).expanduser()

    if path.exists() and not path.is_dir():
        return DEFAULT_OUTPUT_DIRECTORY

    return path


def validate_dialog_directory(value: object) -> Path:
    raw_value = str(value or "").strip()

    if not raw_value:
        return DEFAULT_OUTPUT_DIRECTORY

    path = Path(raw_value).expanduser()

    if path.exists() and path.is_dir():
        return path

    return validate_output_directory(DEFAULT_OUTPUT_DIRECTORY)


def validate_image_quality(value: object) -> int:
    try:
        quality = int(value)
    except (TypeError, ValueError):
        return DEFAULT_IMAGE_QUALITY

    if 10 <= quality <= 100:
        return quality

    return DEFAULT_IMAGE_QUALITY


def validate_pdf_dpi(value: object) -> int:
    try:
        dpi = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PDF_DPI

    if dpi in VALID_PDF_DPI_VALUES:
        return dpi

    return DEFAULT_PDF_DPI


def validate_multi_page_output_mode(value: object) -> str:
    text = str(value or "").strip().lower()

    if text in VALID_MULTI_PAGE_OUTPUT_MODES:
        return text

    return DEFAULT_MULTI_PAGE_OUTPUT_MODE


def validate_office_engine(value: object) -> str:
    text = str(value or "").strip().lower()

    if text in VALID_OFFICE_ENGINES:
        return text

    return DEFAULT_OFFICE_ENGINE


def get_saved_libreoffice_path() -> Path | None:
    settings = QSettings()
    saved_value = _read_string(
        settings,
        LIBREOFFICE_PATH_KEY,
        "",
    )

    if not saved_value:
        return None

    return Path(saved_value)


def save_libreoffice_path(path: str | Path) -> None:
    settings = QSettings()
    settings.setValue(
        LIBREOFFICE_PATH_KEY,
        str(Path(path)),
    )
    settings.sync()


def clear_libreoffice_path() -> None:
    settings = QSettings()
    settings.remove(LIBREOFFICE_PATH_KEY)
    settings.sync()


def save_language(language: object) -> str:
    language_code = validate_language(language)
    settings = QSettings()
    settings.setValue(LANGUAGE_KEY, language_code)
    settings.sync()
    return language_code


def save_window_geometry(
    geometry: QByteArray,
    state: QByteArray,
) -> None:
    settings = QSettings()
    settings.setValue(WINDOW_GEOMETRY_KEY, geometry)
    settings.setValue(WINDOW_STATE_KEY, state)
    settings.sync()


def get_window_geometry() -> QByteArray | None:
    value = QSettings().value(WINDOW_GEOMETRY_KEY)

    if isinstance(value, QByteArray) and not value.isEmpty():
        return value

    return None


def get_window_state() -> QByteArray | None:
    value = QSettings().value(WINDOW_STATE_KEY)

    if isinstance(value, QByteArray) and not value.isEmpty():
        return value

    return None


def save_last_file_dialog_directory(path: str | Path) -> None:
    directory = Path(path)

    if directory.is_file():
        directory = directory.parent

    settings = QSettings()
    settings.setValue(
        LAST_FILE_DIALOG_DIRECTORY_KEY,
        str(validate_dialog_directory(directory)),
    )
    settings.sync()


def _read_string(
    settings: QSettings,
    key: str,
    default: str,
) -> str:
    try:
        value = settings.value(key, default, type=str)
    except (TypeError, ValueError):
        return default

    return str(value or default)


def _read_int(
    settings: QSettings,
    key: str,
    default: int,
) -> int:
    try:
        return int(settings.value(key, default))
    except (TypeError, ValueError):
        return default


def _read_bool(
    settings: QSettings,
    key: str,
    default: bool,
) -> bool:
    value = settings.value(key, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"1", "true", "yes", "on"}:
            return True

        if normalized in {"0", "false", "no", "off"}:
            return False

    return default
