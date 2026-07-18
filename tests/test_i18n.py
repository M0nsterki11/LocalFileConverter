from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from app.constants import APP_NAME
from app.dialogs.about_dialog import AboutDialog
from app.dialogs.settings_dialog import SettingsDialog
from app.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_KEY,
    TRANSLATION_FILES,
    get_translation_manager,
    translate,
    validate_language,
)
from app.main_window import MainWindow
from app.settings import (
    AppSettings,
    DEFAULT_THEME,
    load_app_settings,
    save_app_settings,
    save_language,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_qsettings(tmp_path: Path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QCoreApplication.setOrganizationName("LocalFileConverterI18nTests")
    QCoreApplication.setApplicationName(f"i18n-{uuid4().hex}")

    settings = QSettings()
    settings.clear()
    get_translation_manager().set_language(DEFAULT_LANGUAGE)
    yield settings
    settings.clear()
    get_translation_manager().set_language(DEFAULT_LANGUAGE)


def test_default_language_is_english(isolated_qsettings) -> None:
    settings = load_app_settings()

    assert settings.language == "en"
    assert validate_language("bogus") == DEFAULT_LANGUAGE


def test_language_save_and_restore_preserves_other_settings(
    isolated_qsettings,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "converted"
    save_app_settings(
        AppSettings(
            theme="dark",
            default_output_directory=output_dir,
        )
    )

    saved_language = save_language("hr")
    loaded = load_app_settings()

    assert saved_language == "hr"
    assert loaded.language == "hr"
    assert loaded.theme == "dark"
    assert loaded.default_output_directory == output_dir


def test_translation_manager_loads_and_unloads_croatian() -> None:
    manager = get_translation_manager()

    assert manager.set_language("hr") == "hr"
    assert translate("ConversionStatus", "Pending") == "Na čekanju"

    assert manager.set_language("en") == "en"
    assert translate("ConversionStatus", "Pending") == "Pending"


def test_missing_translation_falls_back_to_english(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = get_translation_manager()
    manager.set_language("en")
    monkeypatch.setitem(TRANSLATION_FILES, "hr", "missing_translation.qm")

    with caplog.at_level("WARNING"):
        active_language = manager.set_language("hr")

    assert active_language == "en"
    assert "using English" in caplog.text


def test_main_settings_and_about_runtime_language_switch(
    isolated_qsettings,
    qapp,
    tmp_path: Path,
) -> None:
    app_settings = AppSettings(
        theme=DEFAULT_THEME,
        default_output_directory=tmp_path,
        language="en",
    )
    main_window = MainWindow(app_settings=app_settings)
    settings_dialog = SettingsDialog(app_settings, None)
    about_dialog = AboutDialog()

    try:
        assert main_window.add_files_button.text() == "Add files"
        assert settings_dialog.windowTitle() == "Settings"
        assert about_dialog.windowTitle() == f"About {APP_NAME}"
        assert about_dialog.license_label.text() == (
            "Licensed under GNU AGPL version 3 only"
        )
        assert about_dialog.warranty_label.text() == "No warranty"
        assert about_dialog.license_button.text() == "View license"
        assert about_dialog.third_party_button.text() == "Third-party notices"
        assert about_dialog.source_code_button.text() == "Source code"

        get_translation_manager().set_language("hr")

        assert main_window.add_files_button.text() == "Dodaj datoteke"
        assert settings_dialog.windowTitle() == "Postavke"
        assert about_dialog.windowTitle() == f"O aplikaciji {APP_NAME}"
        assert about_dialog.license_label.text() == (
            "Licencirano pod GNU AGPL verzijom 3 samo"
        )
        assert about_dialog.warranty_label.text() == "Bez jamstva"
        assert about_dialog.license_button.text() == "Prikaži licencu"
        assert about_dialog.third_party_button.text() == (
            "Obavijesti trećih strana"
        )
        assert about_dialog.source_code_button.text() == "Izvorni kod"
    finally:
        main_window.close()
        settings_dialog.close()
        about_dialog.close()
        get_translation_manager().set_language("en")


def test_settings_dialog_language_change_saves_immediately(
    isolated_qsettings,
    tmp_path: Path,
) -> None:
    dialog = SettingsDialog(
        AppSettings(default_output_directory=tmp_path, language="en"),
        None,
    )

    try:
        index = dialog.language_combo.findData("hr")
        dialog.language_combo.setCurrentIndex(index)

        assert QSettings().value(LANGUAGE_KEY, "", type=str) == "hr"
        assert get_translation_manager().language == "hr"
    finally:
        dialog.close()
        get_translation_manager().set_language("en")


def test_translation_resources_are_packaged() -> None:
    assert (PROJECT_ROOT / "translations" / "local_file_converter_hr.ts").exists()
    assert (
        PROJECT_ROOT / "translations" / "local_file_converter_hr.qm"
    ).stat().st_size > 0

    spec_text = (PROJECT_ROOT / "LocalFileConverter.spec").read_text(
        encoding="utf-8"
    )
    verify_build_text = (
        PROJECT_ROOT / "scripts" / "verify_build.py"
    ).read_text(encoding="utf-8")
    verify_installer_text = (
        PROJECT_ROOT / "scripts" / "verify_installer.py"
    ).read_text(encoding="utf-8")
    release_script_text = (
        PROJECT_ROOT / "scripts" / "build_release.ps1"
    ).read_text(encoding="utf-8")
    installer_script_text = (
        PROJECT_ROOT / "scripts" / "build_installer.ps1"
    ).read_text(encoding="utf-8")

    assert "translations_path" in spec_text
    assert "local_file_converter_hr.qm" in verify_build_text
    assert "local_file_converter_hr.qm" in verify_installer_text
    assert "build_translations.ps1" in release_script_text
    assert "build_translations.ps1" in installer_script_text


def test_python_source_has_no_hardcoded_croatian_ui_strings() -> None:
    source_roots = [
        PROJECT_ROOT / "app",
        PROJECT_ROOT / "converters",
        PROJECT_ROOT / "utils",
        PROJECT_ROOT / "scripts",
    ]
    forbidden_fragments = [
        "Odaberi",
        "Nije",
        "nije",
        "Datoteka",
        "datoteka nije",
        "Konverzija",
        "konverzija je",
        "Greška",
        "greska",
        "Spremanje",
        "Pretvaranje",
        "Otvori izlaznu",
        "Postavke",
        "Dodaj datoteke",
        "Ponovi neuspjele",
    ]

    offenders: list[str] = []

    for root in source_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            text = text.replace('"hr": "Hrvatski"', "")

            for fragment in forbidden_fragments:
                if fragment in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {fragment}")

    assert offenders == []
