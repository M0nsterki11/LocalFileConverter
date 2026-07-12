from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from app.settings import (
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    DEFAULT_OFFICE_ENGINE,
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_PDF_DPI,
    DEFAULT_THEME,
    AppSettings,
    DEFAULT_IMAGE_QUALITY_KEY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY,
    DEFAULT_OFFICE_ENGINE_KEY,
    DEFAULT_OUTPUT_DIRECTORY_KEY,
    DEFAULT_PDF_DPI_KEY,
    THEME_KEY,
    load_app_settings,
    reset_app_settings,
    save_app_settings,
    validate_image_quality,
    validate_office_engine,
    validate_pdf_dpi,
    validate_theme,
)
from app.theme_manager import ThemeManager


@pytest.fixture
def isolated_qsettings(tmp_path: Path):
    if QCoreApplication.instance() is None:
        QCoreApplication([])

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QCoreApplication.setOrganizationName("LocalFileConverterTests")
    QCoreApplication.setApplicationName(f"settings-{uuid4().hex}")

    settings = QSettings()
    settings.clear()
    yield settings
    settings.clear()


def test_save_and_load_theme(isolated_qsettings) -> None:
    save_app_settings(
        AppSettings(
            theme="dark",
            default_output_directory=DEFAULT_OUTPUT_DIRECTORY,
        )
    )

    assert load_app_settings().theme == "dark"


def test_invalid_theme_falls_back_to_system() -> None:
    assert validate_theme("nepoznato") == DEFAULT_THEME


def test_quality_validation() -> None:
    assert validate_image_quality(85) == 85
    assert validate_image_quality(-10) == DEFAULT_IMAGE_QUALITY


def test_dpi_validation() -> None:
    assert validate_pdf_dpi(300) == 300
    assert validate_pdf_dpi(999) == DEFAULT_PDF_DPI


def test_office_engine_validation() -> None:
    assert validate_office_engine("libreoffice") == "libreoffice"
    assert validate_office_engine("weird") == DEFAULT_OFFICE_ENGINE


def test_load_settings_falls_back_for_invalid_values(
    isolated_qsettings,
    tmp_path: Path,
) -> None:
    invalid_file = tmp_path / "not-a-directory"
    invalid_file.write_text("x", encoding="utf-8")

    isolated_qsettings.setValue(THEME_KEY, "weird")
    isolated_qsettings.setValue(DEFAULT_IMAGE_QUALITY_KEY, -10)
    isolated_qsettings.setValue(DEFAULT_PDF_DPI_KEY, 999)
    isolated_qsettings.setValue(
        DEFAULT_MULTI_PAGE_OUTPUT_MODE_KEY,
        "rar",
    )
    isolated_qsettings.setValue(DEFAULT_OFFICE_ENGINE_KEY, "other")
    isolated_qsettings.setValue(
        DEFAULT_OUTPUT_DIRECTORY_KEY,
        str(invalid_file),
    )
    isolated_qsettings.sync()

    settings = load_app_settings()

    assert settings.theme == DEFAULT_THEME
    assert settings.default_image_quality == DEFAULT_IMAGE_QUALITY
    assert settings.default_pdf_dpi == DEFAULT_PDF_DPI
    assert (
        settings.default_multi_page_output_mode
        == DEFAULT_MULTI_PAGE_OUTPUT_MODE
    )
    assert settings.default_office_engine == DEFAULT_OFFICE_ENGINE
    assert settings.default_output_directory == DEFAULT_OUTPUT_DIRECTORY


def test_reset_settings_restores_defaults(isolated_qsettings) -> None:
    save_app_settings(
        AppSettings(
            theme="dark",
            default_image_quality=60,
        )
    )

    settings = reset_app_settings()

    assert settings.theme == DEFAULT_THEME
    assert settings.default_image_quality == DEFAULT_IMAGE_QUALITY
    assert load_app_settings().theme == DEFAULT_THEME


def test_theme_manager_loads_light_and_dark_qss(
    tmp_path: Path,
) -> None:
    theme_dir = tmp_path / "themes"
    theme_dir.mkdir()
    (theme_dir / "common.qss").write_text(
        "QWidget { font-size: 14px; }",
        encoding="utf-8",
    )
    (theme_dir / "light.qss").write_text(
        "QWidget { color: black; }",
        encoding="utf-8",
    )
    (theme_dir / "dark.qss").write_text(
        "QWidget { color: white; }",
        encoding="utf-8",
    )

    manager = ThemeManager(theme_dir)

    assert "color: black" in manager.build_stylesheet("light")
    assert "color: white" in manager.build_stylesheet("dark")


def test_missing_qss_does_not_crash(tmp_path: Path) -> None:
    manager = ThemeManager(tmp_path / "missing")

    assert manager.build_stylesheet("light") == ""
