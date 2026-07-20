from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_OUTPUT = PROJECT_ROOT / "installer_output"
LIBREOFFICE_CONFIG = PROJECT_ROOT / "packaging" / "libreoffice_dependency.json"
THIRD_PARTY_NOTICES = PROJECT_ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt"
INSTALLER_SCRIPT = PROJECT_ROOT / "packaging" / "MyFileConverter.iss"
APP_ICON_PATH = PROJECT_ROOT / "resources" / "app_icon.ico"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"
NOTICE_PATH = PROJECT_ROOT / "NOTICE"
SOURCE_CODE_PATH = PROJECT_ROOT / "SOURCE_CODE.md"
PYMUPDF_COPYING = PROJECT_ROOT / "licenses" / "PyMuPDF-COPYING"
TRANSLATION_PATH = (
    PROJECT_ROOT / "translations" / "local_file_converter_hr.qm"
)
ONEDIR_BUNDLE = PROJECT_ROOT / "dist" / "MyFileConverter"
PUBLIC_REPOSITORY_URL = "https://github.com/M0nsterki11/LocalFileConverter"
PYMUPDF_LICENSE_WORDING = (
    "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"
)
PINNED_LIBREOFFICE = {
    "ENABLED": True,
    "VERSION": "26.2.4",
    "ARCHITECTURE": "x64",
    "FILENAME": "LibreOffice_26.2.4_Win_x86-64.msi",
    "DOWNLOAD_URL": (
        "https://download.documentfoundation.org/libreoffice/stable/"
        "26.2.4/win/x86_64/LibreOffice_26.2.4_Win_x86-64.msi"
    ),
    "SHA256": (
        "202f26cda071c5aa4996a5a28412fddceb3891dceb0366982c62650456c0730f"
    ),
    "EXPECTED_FILE_SIZE": 372539392,
    "EXPECTED_SOFFICE_PATH": (
        r"C:\Program Files\LibreOffice\program\soffice.exe"
    ),
}
APP_ID_GUID = "2B037AD6-19DE-43D9-9976-689D3202587F"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", default="")
    args = parser.parse_args()

    version = read_app_version()
    installer_path = (
        Path(args.installer)
        if args.installer
        else INSTALLER_OUTPUT / f"MyFileConverter_Setup_{version}_x64.exe"
    )
    errors: list[str] = []

    if not installer_path.exists():
        errors.append(f"Setup EXE does not exist: {installer_path}")
    elif installer_path.stat().st_size <= 0:
        errors.append(f"Setup EXE is empty: {installer_path}")

    if version not in installer_path.name:
        errors.append("Installer name does not contain APP_VERSION.")

    expected_installer_name = f"MyFileConverter_Setup_{version}_x64.exe"

    if installer_path.name != expected_installer_name:
        errors.append(
            f"Installer name must be {expected_installer_name}, "
            f"got {installer_path.name}."
        )

    if "x64" not in installer_path.name.casefold():
        errors.append("Installer name does not contain the x64 marker.")

    try:
        installer_path.resolve().relative_to(
            (PROJECT_ROOT / "dist" / "MyFileConverter").resolve()
        )
        errors.append("Installer output is inside the dist app folder.")
    except ValueError:
        pass

    if not THIRD_PARTY_NOTICES.exists():
        errors.append("THIRD_PARTY_NOTICES.txt does not exist.")

    _check_legal_notice_files(errors)
    _check_non_empty_file(APP_ICON_PATH, "resources/app_icon.ico", errors)
    _check_non_empty_file(
        TRANSLATION_PATH,
        "translations/local_file_converter_hr.qm",
        errors,
    )
    _check_installer_icon_configuration(errors)
    _check_installer_notice_configuration(errors)
    _check_installer_version_include(errors, version)
    _check_installer_setup_configuration(errors)
    _check_libreoffice_installer_flow(errors)
    _check_bundle_icon(errors)
    _check_bundle_translation(errors)

    config_errors = validate_libreoffice_config(LIBREOFFICE_CONFIG)
    errors.extend(config_errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    digest = sha256_file(installer_path)
    INSTALLER_OUTPUT.mkdir(parents=True, exist_ok=True)
    sha_file = INSTALLER_OUTPUT / "SHA256SUMS.txt"
    sha_file.write_text(
        f"{digest}  {installer_path.name}\n",
        encoding="utf-8",
    )

    print(f"Installer: {installer_path}")
    print(f"Size: {installer_path.stat().st_size / (1024 * 1024):.1f} MB")
    print(f"SHA-256: {digest}")
    print(f"Wrote: {sha_file}")
    return 0


def _check_non_empty_file(
    path: Path,
    label: str,
    errors: list[str],
) -> None:
    if not path.exists():
        errors.append(f"{label} does not exist: {path}")
        return

    if path.stat().st_size <= 0:
        errors.append(f"{label} is empty: {path}")


def _check_bundle_icon(errors: list[str]) -> None:
    candidates = [
        ONEDIR_BUNDLE / "_internal" / "resources" / "app_icon.ico",
        ONEDIR_BUNDLE / "resources" / "app_icon.ico",
    ]

    for candidate in candidates:
        if candidate.exists():
            _check_non_empty_file(
                candidate,
                "app_icon.ico in the ONEDIR bundle",
                errors,
            )
            return

    errors.append("app_icon.ico is not included in the release ONEDIR bundle.")


def _check_bundle_translation(errors: list[str]) -> None:
    candidates = [
        ONEDIR_BUNDLE
        / "_internal"
        / "translations"
        / "local_file_converter_hr.qm",
        ONEDIR_BUNDLE / "translations" / "local_file_converter_hr.qm",
    ]

    for candidate in candidates:
        if candidate.exists():
            _check_non_empty_file(
                candidate,
                "local_file_converter_hr.qm in the ONEDIR bundle",
                errors,
            )
            return

    errors.append(
        "local_file_converter_hr.qm is not included in the release ONEDIR bundle."
    )


def _check_legal_notice_files(errors: list[str]) -> None:
    for path, label in (
        (LICENSE_PATH, "LICENSE"),
        (NOTICE_PATH, "NOTICE"),
        (SOURCE_CODE_PATH, "SOURCE_CODE.md"),
        (THIRD_PARTY_NOTICES, "THIRD_PARTY_NOTICES.txt"),
        (PYMUPDF_COPYING, "licenses/PyMuPDF-COPYING"),
    ):
        _check_non_empty_file(path, label, errors)

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

    if "Affero General Public License version 3 only" not in notice_text:
        errors.append("NOTICE does not say the project is licensed version 3 only.")

    if "or any later version" in notice_text:
        errors.append("NOTICE must not say 'or any later version'.")

    if PYMUPDF_LICENSE_WORDING not in third_party_text:
        errors.append("THIRD_PARTY_NOTICES is missing PyMuPDF dual-license wording.")

    pymupdf_section = _extract_notice_section(
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

    if "v0.5.1" not in source_text:
        errors.append("SOURCE_CODE.md does not identify tag v0.5.1.")


def _check_installer_icon_configuration(errors: list[str]) -> None:
    if not INSTALLER_SCRIPT.exists():
        errors.append(f"Inno Setup script does not exist: {INSTALLER_SCRIPT}")
        return

    script_text = INSTALLER_SCRIPT.read_text(encoding="utf-8").casefold()
    required_snippets = {
        "SetupIconFile": "setupiconfile=..\\resources\\app_icon.ico",
        "UninstallDisplayIcon": "uninstalldisplayicon={app}\\{#appexename}",
        "shortcut IconFilename": 'iconfilename: "{app}\\{#appexename}"',
    }

    for label, snippet in required_snippets.items():
        if snippet.casefold() not in script_text:
            errors.append(f"Inno Setup script is missing {label} for the app icon.")


def _check_installer_notice_configuration(errors: list[str]) -> None:
    script_text = _read_installer_script_text(errors)

    if not script_text:
        return

    normalized = _normalize_iss_text(script_text)
    required_snippets = {
        "LICENSE install": r'source: "..\license"; destdir: "{app}"',
        "NOTICE install": r'source: "..\notice"; destdir: "{app}"',
        "SOURCE_CODE install": r'source: "..\source_code.md"; destdir: "{app}"',
        "THIRD_PARTY_NOTICES install": (
            r'source: "third_party_notices.txt"; destdir: "{app}"'
        ),
        "PyMuPDF COPYING install": (
            r'source: "..\licenses\pymupdf-copying"; '
            r'destdir: "{app}\licenses"'
        ),
        "License Start Menu entry": (
            r'name: "{group}\license"; filename: "{app}\license"'
        ),
        "Third-party notices Start Menu entry": (
            r'name: "{group}\third-party notices"; '
            r'filename: "{app}\third_party_notices.txt"'
        ),
        "Source Code Information Start Menu entry": (
            r'name: "{group}\source code information"; '
            r'filename: "{app}\source_code.md"'
        ),
    }

    for label, snippet in required_snippets.items():
        if snippet not in normalized:
            errors.append(f"Inno Setup script is missing {label}.")


def _check_installer_setup_configuration(errors: list[str]) -> None:
    script_text = _read_installer_script_text(errors)

    if not script_text:
        return

    required_snippets = {
        "fixed AppId": APP_ID_GUID.casefold(),
        "MyFile default directory": "defaultdirname={localappdata}\\programs\\myfileconverter",
        "DisableDirPage=no": "disabledirpage=no",
        "UsePreviousAppDir=yes": "usepreviousappdir=yes",
        "per-user privileges": "privilegesrequired=lowest",
    }

    normalized = _normalize_iss_text(script_text)

    for label, snippet in required_snippets.items():
        if snippet not in normalized:
            errors.append(f"Inno Setup script is missing {label}.")


def _check_installer_version_include(errors: list[str], version: str) -> None:
    version_include = PROJECT_ROOT / "packaging" / "generated_version.iss"

    if not version_include.exists():
        errors.append(f"Installer version include does not exist: {version_include}")
        return

    normalized = _normalize_iss_text(version_include.read_text(encoding="utf-8"))
    required_snippets = {
        "AppName": '#define appname "myfile converter"',
        "AppExeName": '#define appexename "myfileconverter.exe"',
        "AppSetupBaseName": (
            f'#define appsetupbasename "myfileconverter_setup_{version}_x64"'
        ),
    }

    for label, snippet in required_snippets.items():
        if snippet not in normalized:
            errors.append(f"Installer version include is missing {label}.")


def _check_libreoffice_installer_flow(errors: list[str]) -> None:
    script_text = _read_installer_script_text(errors)

    if not script_text:
        return

    normalized = _normalize_iss_text(script_text)

    required_snippets = {
        "LibreOffice generated include": (
            '#include "generated_libreoffice_dependency.iss"'
        ),
        "LibreOffice enabled gate": "function libreofficedownloadsenabled()",
        "optional LibreOffice page": "createinputoptionpage(",
        "unchecked LibreOffice option": "libreofficepage.values[0] := false",
        "download only when not found": "if detectlibreoffice() then",
        "no silent download": "if wizardsilent then",
        "download page": "createdownloadpage(",
        "SHA-pinned download": "libreofficedownloadpage.add(",
        "SHA file verification": "getsha256offile(",
        "msiexec launch": "msiexec.exe",
        "temporary MSI cleanup": "deletefile(installerpath)",
    }

    for label, snippet in required_snippets.items():
        if snippet.casefold() not in normalized:
            errors.append(f"LibreOffice installer flow missing: {label}.")

    run_body = _extract_function_body(script_text, "RunLibreOfficeInstaller")

    if not run_body:
        errors.append("RunLibreOfficeInstaller function was not found.")
    else:
        verify_index = run_body.casefold().find("verifylibreofficeinstaller()")
        exec_index = run_body.casefold().find("exec(")

        if verify_index < 0:
            errors.append(
                "RunLibreOfficeInstaller does not call VerifyLibreOfficeInstaller."
            )
        elif exec_index < 0:
            errors.append("RunLibreOfficeInstaller does not start msiexec.")
        elif verify_index > exec_index:
            errors.append(
                "LibreOffice MSI starts before SHA-256 verification."
            )

    if _section_exists(script_text, "UninstallRun"):
        errors.append("Installer must not have [UninstallRun] for LibreOffice.")

    uninstall_delete = _extract_section(script_text, "UninstallDelete")

    if "libreoffice" in uninstall_delete.casefold():
        errors.append("Uninstall must not remove LibreOffice.")

    files_section = _extract_section(script_text, "Files")

    if PINNED_LIBREOFFICE["FILENAME"].casefold() in files_section.casefold():
        errors.append("LibreOffice MSI must not be included in Setup EXE.")


def _read_installer_script_text(errors: list[str]) -> str:
    if not INSTALLER_SCRIPT.exists():
        errors.append(f"Inno Setup script does not exist: {INSTALLER_SCRIPT}")
        return ""

    return INSTALLER_SCRIPT.read_text(encoding="utf-8")


def _normalize_iss_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold())


def _section_exists(text: str, section_name: str) -> bool:
    return re.search(
        rf"(?im)^\[{re.escape(section_name)}\]\s*$",
        text,
    ) is not None


def _extract_section(text: str, section_name: str) -> str:
    match = re.search(
        rf"(?ims)^\[{re.escape(section_name)}\]\s*(.*?)(?=^\[|\Z)",
        text,
    )

    if match is None:
        return ""

    return match.group(1)


def _extract_function_body(text: str, function_name: str) -> str:
    match = re.search(
        rf"(?is)function\s+{re.escape(function_name)}\s*\([^)]*\)\s*:\s*Boolean\s*;.*?begin(.*?)\nend;",
        text,
    )

    if match is None:
        return ""

    return match.group(1)


def _extract_notice_section(text: str, start: str, end: str) -> str:
    start_index = text.find(start)

    if start_index < 0:
        return ""

    end_index = text.find(end, start_index)

    if end_index < 0:
        return text[start_index:]

    return text[start_index:end_index]


def _installed_pymupdf_copying_text() -> str:
    distribution = metadata.distribution("PyMuPDF")
    copying_path = distribution.locate_file(
        Path(f"pymupdf-{distribution.version}.dist-info") / "COPYING"
    )
    return Path(copying_path).read_text(encoding="utf-8")


def read_app_version() -> str:
    constants = (PROJECT_ROOT / "app" / "constants.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', constants)

    if match is None:
        raise RuntimeError("APP_VERSION was not found.")

    return match.group(1)


def validate_libreoffice_config(path: Path) -> list[str]:
    errors: list[str] = []

    if not path.exists():
        return [f"LibreOffice config does not exist: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"LibreOffice config is not valid JSON: {error}"]

    required_keys = {
        "ENABLED",
        "VERSION",
        "ARCHITECTURE",
        "FILENAME",
        "DOWNLOAD_URL",
        "SHA256",
        "EXPECTED_FILE_SIZE",
        "EXPECTED_SOFFICE_PATH",
    }
    missing_keys = required_keys - set(data)

    if missing_keys:
        errors.append(
            "LibreOffice config is missing fields: "
            + ", ".join(sorted(missing_keys))
        )

    for key, expected_value in PINNED_LIBREOFFICE.items():
        if data.get(key) != expected_value:
            errors.append(
                f"LibreOffice {key} is not the pinned value: {expected_value!r}."
            )

    parsed_url = urlparse(str(data.get("DOWNLOAD_URL", "")))

    if parsed_url.scheme != "https":
        errors.append("LibreOffice DOWNLOAD_URL must use HTTPS.")

    if parsed_url.netloc.casefold() != "download.documentfoundation.org":
        errors.append(
            "LibreOffice DOWNLOAD_URL must use the official documentfoundation.org domain."
        )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(data.get("SHA256", ""))):
        errors.append("LibreOffice SHA256 must contain 64 hexadecimal characters.")

    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
