from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_OUTPUT = PROJECT_ROOT / "installer_output"
LIBREOFFICE_CONFIG = PROJECT_ROOT / "packaging" / "libreoffice_dependency.json"
THIRD_PARTY_NOTICES = PROJECT_ROOT / "packaging" / "THIRD_PARTY_NOTICES.txt"


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
        "DOWNLOAD_URL",
        "SHA256",
        "EXPECTED_SOFFICE_PATH",
    }
    missing_keys = required_keys - set(data)

    if missing_keys:
        errors.append(
            "LibreOffice config nema polja: "
            + ", ".join(sorted(missing_keys))
        )

    if data.get("ENABLED") is True:
        for key in (
            "VERSION",
            "DOWNLOAD_URL",
            "SHA256",
            "EXPECTED_SOFFICE_PATH",
        ):
            if not str(data.get(key, "")).strip():
                errors.append(
                    f"LibreOffice ENABLED=true, ali nedostaje {key}."
                )

    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
