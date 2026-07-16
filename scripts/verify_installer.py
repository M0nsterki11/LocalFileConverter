from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_OUTPUT = PROJECT_ROOT / "installer_output"
LIBREOFFICE_CONFIG = PROJECT_ROOT / "packaging" / "libreoffice_dependency.json"
THIRD_PARTY_NOTICES = PROJECT_ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt"
INSTALLER_SCRIPT = PROJECT_ROOT / "packaging" / "LocalFileConverter.iss"
APP_ICON_PATH = PROJECT_ROOT / "resources" / "app_icon.ico"
ONEDIR_BUNDLE = PROJECT_ROOT / "dist" / "LocalFileConverter"
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
        else INSTALLER_OUTPUT / f"LocalFileConverter_Setup_{version}_x64.exe"
    )
    errors: list[str] = []

    if not installer_path.exists():
        errors.append(f"Setup EXE ne postoji: {installer_path}")
    elif installer_path.stat().st_size <= 0:
        errors.append(f"Setup EXE je prazan: {installer_path}")

    if version not in installer_path.name:
        errors.append("Naziv installera ne sadrzi APP_VERSION.")

    if "x64" not in installer_path.name.casefold():
        errors.append("Naziv installera ne sadrzi x64 oznaku.")

    try:
        installer_path.resolve().relative_to(
            (PROJECT_ROOT / "dist" / "LocalFileConverter").resolve()
        )
        errors.append("Installer output je unutar dist app foldera.")
    except ValueError:
        pass

    if not THIRD_PARTY_NOTICES.exists():
        errors.append("THIRD_PARTY_NOTICES.txt ne postoji.")

    _check_non_empty_file(APP_ICON_PATH, "resources/app_icon.ico", errors)
    _check_installer_icon_configuration(errors)
    _check_installer_setup_configuration(errors)
    _check_libreoffice_installer_flow(errors)
    _check_bundle_icon(errors)

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
        errors.append(f"{label} ne postoji: {path}")
        return

    if path.stat().st_size <= 0:
        errors.append(f"{label} je prazan: {path}")


def _check_bundle_icon(errors: list[str]) -> None:
    candidates = [
        ONEDIR_BUNDLE / "_internal" / "resources" / "app_icon.ico",
        ONEDIR_BUNDLE / "resources" / "app_icon.ico",
    ]

    for candidate in candidates:
        if candidate.exists():
            _check_non_empty_file(
                candidate,
                "app_icon.ico u ONEDIR bundleu",
                errors,
            )
            return

    errors.append("app_icon.ico nije ukljucen u release ONEDIR bundle.")


def _check_installer_icon_configuration(errors: list[str]) -> None:
    if not INSTALLER_SCRIPT.exists():
        errors.append(f"Inno Setup skripta ne postoji: {INSTALLER_SCRIPT}")
        return

    script_text = INSTALLER_SCRIPT.read_text(encoding="utf-8").casefold()
    required_snippets = {
        "SetupIconFile": "setupiconfile=..\\resources\\app_icon.ico",
        "UninstallDisplayIcon": "uninstalldisplayicon={app}\\{#appexename}",
        "shortcut IconFilename": 'iconfilename: "{app}\\{#appexename}"',
    }

    for label, snippet in required_snippets.items():
        if snippet.casefold() not in script_text:
            errors.append(f"Inno Setup skripti nedostaje {label} za app ikonu.")


def _check_installer_setup_configuration(errors: list[str]) -> None:
    script_text = _read_installer_script_text(errors)

    if not script_text:
        return

    required_snippets = {
        "fixed AppId": APP_ID_GUID.casefold(),
        "DisableDirPage=no": "disabledirpage=no",
        "UsePreviousAppDir=yes": "usepreviousappdir=yes",
        "per-user privileges": "privilegesrequired=lowest",
    }

    normalized = _normalize_iss_text(script_text)

    for label, snippet in required_snippets.items():
        if snippet not in normalized:
            errors.append(f"Inno Setup skripti nedostaje {label}.")


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
        errors.append("RunLibreOfficeInstaller funkcija nije pronadena.")
    else:
        verify_index = run_body.casefold().find("verifylibreofficeinstaller()")
        exec_index = run_body.casefold().find("exec(")

        if verify_index < 0:
            errors.append(
                "RunLibreOfficeInstaller ne poziva VerifyLibreOfficeInstaller."
            )
        elif exec_index < 0:
            errors.append("RunLibreOfficeInstaller ne pokrece msiexec.")
        elif verify_index > exec_index:
            errors.append(
                "LibreOffice MSI se pokrece prije SHA-256 provjere."
            )

    if _section_exists(script_text, "UninstallRun"):
        errors.append("Installer ne smije imati [UninstallRun] za LibreOffice.")

    uninstall_delete = _extract_section(script_text, "UninstallDelete")

    if "libreoffice" in uninstall_delete.casefold():
        errors.append("Uninstall ne smije uklanjati LibreOffice.")

    files_section = _extract_section(script_text, "Files")

    if PINNED_LIBREOFFICE["FILENAME"].casefold() in files_section.casefold():
        errors.append("LibreOffice MSI ne smije biti ukljucen u Setup EXE.")


def _read_installer_script_text(errors: list[str]) -> str:
    if not INSTALLER_SCRIPT.exists():
        errors.append(f"Inno Setup skripta ne postoji: {INSTALLER_SCRIPT}")
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


def read_app_version() -> str:
    constants = (PROJECT_ROOT / "app" / "constants.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', constants)

    if match is None:
        raise RuntimeError("APP_VERSION nije pronaden.")

    return match.group(1)


def validate_libreoffice_config(path: Path) -> list[str]:
    errors: list[str] = []

    if not path.exists():
        return [f"LibreOffice config ne postoji: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"LibreOffice config nije valjan JSON: {error}"]

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
            "LibreOffice config nema polja: "
            + ", ".join(sorted(missing_keys))
        )

    for key, expected_value in PINNED_LIBREOFFICE.items():
        if data.get(key) != expected_value:
            errors.append(
                f"LibreOffice {key} nije pinned vrijednost: {expected_value!r}."
            )

    parsed_url = urlparse(str(data.get("DOWNLOAD_URL", "")))

    if parsed_url.scheme != "https":
        errors.append("LibreOffice DOWNLOAD_URL mora koristiti HTTPS.")

    if parsed_url.netloc.casefold() != "download.documentfoundation.org":
        errors.append(
            "LibreOffice DOWNLOAD_URL mora koristiti sluzbenu documentfoundation.org domenu."
        )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(data.get("SHA256", ""))):
        errors.append("LibreOffice SHA256 mora imati 64 heksadecimalna znaka.")

    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
