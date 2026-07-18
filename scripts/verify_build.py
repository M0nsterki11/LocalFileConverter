from __future__ import annotations

import argparse
import importlib.metadata as metadata
import sys
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ICON_PATH = PROJECT_ROOT / "resources" / "app_icon.ico"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"
NOTICE_PATH = PROJECT_ROOT / "NOTICE"
SOURCE_CODE_PATH = PROJECT_ROOT / "SOURCE_CODE.md"
THIRD_PARTY_NOTICES = PROJECT_ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt"
PYMUPDF_COPYING = PROJECT_ROOT / "licenses" / "PyMuPDF-COPYING"
TRANSLATION_PATH = (
    PROJECT_ROOT / "translations" / "local_file_converter_hr.qm"
)
PUBLIC_REPOSITORY_URL = "https://github.com/M0nsterki11/LocalFileConverter"
PYMUPDF_LICENSE_WORDING = (
    "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        default=str(PROJECT_ROOT / "dist" / "LocalFileConverter"),
    )
    parser.add_argument("--name", default="LocalFileConverter")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    exe_path = bundle_path / f"{args.name}.exe"
    errors: list[str] = []

    _check_file(APP_ICON_PATH, errors)
    _check_legal_notice_files(errors)
    _check_file(TRANSLATION_PATH, errors)
    _check_file(exe_path, errors)

    resource_root = _find_resource_root(bundle_path)

    if resource_root is None:
        errors.append("The resources folder was not found in the bundle.")
    else:
        _check_file(resource_root / "app_icon.ico", errors)

        for qss_name in ("common.qss", "light.qss", "dark.qss"):
            _check_file(resource_root / "themes" / qss_name, errors)

    translation_root = _find_translation_root(bundle_path)

    if translation_root is None:
        errors.append("The translations folder was not found in the bundle.")
    else:
        _check_file(translation_root / "local_file_converter_hr.qm", errors)

    if not list(bundle_path.rglob("qwindows.dll")):
        errors.append("Qt platforms plugin qwindows.dll was not found.")

    if not list(bundle_path.rglob("PySide6*.dll")):
        errors.append("PySide6 DLL files were not found.")

    _check_bundle_notice_files(bundle_path, errors)

    bundle_size = _directory_size(bundle_path)
    print(f"Bundle: {bundle_path}")
    print(f"Size: {bundle_size / (1024 * 1024):.1f} MB")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Build verification passed.")
    return 0


def _check_file(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"File does not exist: {path}")
        return

    if path.is_file() and path.stat().st_size <= 0:
        errors.append(f"File is empty: {path}")


def _check_legal_notice_files(errors: list[str]) -> None:
    for path in (
        LICENSE_PATH,
        NOTICE_PATH,
        SOURCE_CODE_PATH,
        THIRD_PARTY_NOTICES,
        PYMUPDF_COPYING,
    ):
        _check_file(path, errors)

    if errors:
        return

    license_text = LICENSE_PATH.read_text(encoding="utf-8")
    notice_text = NOTICE_PATH.read_text(encoding="utf-8")
    source_text = SOURCE_CODE_PATH.read_text(encoding="utf-8")
    third_party_text = THIRD_PARTY_NOTICES.read_text(encoding="utf-8")
    pymupdf_copying_text = PYMUPDF_COPYING.read_text(encoding="utf-8")

    if "GNU AFFERO GENERAL PUBLIC LICENSE" not in license_text:
        errors.append("LICENSE does not contain the AGPL version 3 heading.")

    if "Version 3, 19 November 2007" not in license_text:
        errors.append("LICENSE does not contain the AGPL version 3 date.")

    required_notice = (
        "Local File Converter's original project code is licensed under the "
        "GNU\nAffero General Public License version 3 only."
    )

    if required_notice not in notice_text:
        errors.append("NOTICE does not say the project is licensed version 3 only.")

    if "or any later version" in notice_text:
        errors.append("NOTICE must not say 'or any later version'.")

    if PYMUPDF_LICENSE_WORDING not in third_party_text:
        errors.append("THIRD_PARTY_NOTICES is missing PyMuPDF dual-license wording.")

    pymupdf_section = _extract_section_text(
        third_party_text,
        "PyMuPDF / MuPDF",
        "PyInstaller",
    )

    if "AGPL-3.0-only" in pymupdf_section:
        errors.append("PyMuPDF section must not assign AGPL-3.0-only.")

    if "AGPL-3.0-or-later" in pymupdf_section:
        errors.append("PyMuPDF section must not assign AGPL-3.0-or-later.")

    if pymupdf_copying_text != _installed_pymupdf_copying_text():
        errors.append("licenses/PyMuPDF-COPYING does not match installed PyMuPDF COPYING.")

    if PUBLIC_REPOSITORY_URL not in source_text:
        errors.append("SOURCE_CODE.md does not contain the public repository URL.")

    parsed_url = urlparse(PUBLIC_REPOSITORY_URL)

    if parsed_url.scheme != "https" or parsed_url.netloc != "github.com":
        errors.append("SOURCE_CODE.md must use a stable HTTPS GitHub URL.")

    if "v0.5.0" not in source_text:
        errors.append("SOURCE_CODE.md does not identify tag v0.5.0.")


def _check_bundle_notice_files(bundle_path: Path, errors: list[str]) -> None:
    required_files = {
        "LICENSE": LICENSE_PATH,
        "NOTICE": NOTICE_PATH,
        "SOURCE_CODE.md": SOURCE_CODE_PATH,
        "THIRD_PARTY_NOTICES.txt": THIRD_PARTY_NOTICES,
        str(Path("licenses") / "PyMuPDF-COPYING"): PYMUPDF_COPYING,
    }

    for relative_path, source_path in required_files.items():
        bundle_file = _find_bundle_file(bundle_path, Path(relative_path))

        if bundle_file is None:
            errors.append(f"{relative_path} is not included in the ONEDIR bundle.")
            continue

        _check_file(bundle_file, errors)

        if bundle_file.exists() and source_path.exists():
            if bundle_file.read_text(encoding="utf-8") != source_path.read_text(
                encoding="utf-8"
            ):
                errors.append(f"{relative_path} in the bundle differs from source.")


def _find_bundle_file(bundle_path: Path, relative_path: Path) -> Path | None:
    candidates = [
        bundle_path / relative_path,
        bundle_path / "_internal" / relative_path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(bundle_path.rglob(str(relative_path)))
    return matches[0] if matches else None


def _installed_pymupdf_copying_text() -> str:
    distribution = metadata.distribution("PyMuPDF")
    copying_path = distribution.locate_file(
        Path(f"pymupdf-{distribution.version}.dist-info") / "COPYING"
    )
    return Path(copying_path).read_text(encoding="utf-8")


def _extract_section_text(text: str, start: str, end: str) -> str:
    start_index = text.find(start)

    if start_index < 0:
        return ""

    end_index = text.find(end, start_index)

    if end_index < 0:
        return text[start_index:]

    return text[start_index:end_index]


def _find_resource_root(bundle_path: Path) -> Path | None:
    candidates = [
        bundle_path / "resources",
        bundle_path / "_internal" / "resources",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(bundle_path.rglob("resources"))
    return matches[0] if matches else None


def _find_translation_root(bundle_path: Path) -> Path | None:
    candidates = [
        bundle_path / "translations",
        bundle_path / "_internal" / "translations",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(bundle_path.rglob("translations"))
    return matches[0] if matches else None


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0

    return sum(
        file_path.stat().st_size
        for file_path in path.rglob("*")
        if file_path.is_file()
    )


if __name__ == "__main__":
    raise SystemExit(main())
