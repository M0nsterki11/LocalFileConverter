from __future__ import annotations

import importlib.metadata as metadata
from pathlib import Path
from urllib.parse import urlparse

from app.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_SETTINGS_APPLICATION_NAME,
    APP_VERSION,
    GITHUB_REPOSITORY_URL,
)
from app.dialogs.about_dialog import AboutDialog


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_REPOSITORY_URL = "https://github.com/M0nsterki11/LocalFileConverter"
PYMUPDF_LICENSE_WORDING = (
    "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"
)
APP_ID_GUID = "2B037AD6-19DE-43D9-9976-689D3202587F"


def test_project_license_and_notice_are_agpl_v3_only() -> None:
    license_path = PROJECT_ROOT / "LICENSE"
    notice_path = PROJECT_ROOT / "NOTICE"
    license_text = license_path.read_text(encoding="utf-8")
    notice_text = notice_path.read_text(encoding="utf-8")

    assert license_path.stat().st_size > 0
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    assert (
        "MyFile Converter's original project code is licensed under the "
        "GNU\nAffero General Public License version 3 only."
    ) in notice_text
    assert "or any later version" not in notice_text


def test_pymupdf_notice_uses_cautious_upstream_wording() -> None:
    notices_path = PROJECT_ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt"
    notices_text = notices_path.read_text(encoding="utf-8")
    pymupdf_section = _section_text(
        notices_text,
        "PyMuPDF / MuPDF",
        "PyInstaller",
    )

    assert "Version: 1.28.0" in pymupdf_section
    assert "Bundled MuPDF runtime reported by PyMuPDF: 1.29.0" in pymupdf_section
    assert PYMUPDF_LICENSE_WORDING in pymupdf_section
    assert "Artifex Software, Inc." in pymupdf_section
    assert "licenses/PyMuPDF-COPYING" in pymupdf_section
    assert "commercial Artifex license is required" in pymupdf_section
    assert "AGPL-3.0-only" not in pymupdf_section
    assert "AGPL-3.0-or-later" not in pymupdf_section


def test_pymupdf_copying_is_installed_copying_verbatim() -> None:
    distribution = metadata.distribution("PyMuPDF")
    installed_copying = distribution.locate_file(
        Path(f"pymupdf-{distribution.version}.dist-info") / "COPYING"
    )
    tracked_copying = PROJECT_ROOT / "licenses" / "PyMuPDF-COPYING"

    assert tracked_copying.read_text(encoding="utf-8") == Path(
        installed_copying
    ).read_text(encoding="utf-8")


def test_source_code_notice_uses_public_https_repository_and_release_tag() -> None:
    source_text = (PROJECT_ROOT / "SOURCE_CODE.md").read_text(encoding="utf-8")
    parsed_url = urlparse(PUBLIC_REPOSITORY_URL)

    assert PUBLIC_REPOSITORY_URL in source_text
    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "github.com"
    assert "v0.6.2" in source_text
    assert "must be created and pushed before publishing the installer" in source_text


def test_packaging_includes_required_notice_files() -> None:
    spec_text = (PROJECT_ROOT / "MyFileConverter.spec").read_text(
        encoding="utf-8"
    )
    installer_text = (
        PROJECT_ROOT / "packaging" / "MyFileConverter.iss"
    ).read_text(encoding="utf-8")
    verify_build_text = (
        PROJECT_ROOT / "scripts" / "verify_build.py"
    ).read_text(encoding="utf-8")
    verify_installer_text = (
        PROJECT_ROOT / "scripts" / "verify_installer.py"
    ).read_text(encoding="utf-8")

    for required_name in (
        "LICENSE",
        "NOTICE",
        "SOURCE_CODE.md",
        "THIRD_PARTY_NOTICES.txt",
        "PyMuPDF-COPYING",
    ):
        assert required_name in spec_text
        assert required_name in installer_text
        assert required_name in verify_build_text
        assert required_name in verify_installer_text


def test_about_dialog_exposes_license_notices_source_and_no_warranty(qapp) -> None:
    dialog = AboutDialog()

    try:
        assert dialog.version_label.text() == f"Version {APP_VERSION}"
        assert dialog.license_label.text() == "Licensed under GNU AGPL version 3 only"
        assert dialog.warranty_label.text() == "No warranty"
        assert dialog.license_button.text() == "View license"
        assert dialog.third_party_button.text() == "Third-party notices"
        assert dialog.source_code_button.text() == "Source code"
        assert GITHUB_REPOSITORY_URL in dialog.body_label.text()
    finally:
        dialog.close()


def test_app_version_and_installer_app_id() -> None:
    installer_text = (
        PROJECT_ROOT / "packaging" / "MyFileConverter.iss"
    ).read_text(encoding="utf-8")

    assert APP_VERSION == "0.6.2"
    assert APP_ID_GUID in installer_text
    assert "DefaultDirName={localappdata}\\Programs\\MyFileConverter" in installer_text
    assert "MyFile Converter" in installer_text


def test_visible_name_changed_but_qsettings_identity_is_preserved() -> None:
    assert APP_NAME == "MyFile Converter"
    assert APP_ORGANIZATION == "LocalFileConverter"
    assert APP_SETTINGS_APPLICATION_NAME == "Local File Converter"


def _section_text(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]
