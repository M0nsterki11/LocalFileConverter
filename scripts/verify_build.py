from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ICON_PATH = PROJECT_ROOT / "resources" / "app_icon.ico"


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
    _check_file(exe_path, errors)

    resource_root = _find_resource_root(bundle_path)

    if resource_root is None:
        errors.append("resources folder nije pronaden u bundleu")
    else:
        _check_file(resource_root / "app_icon.ico", errors)

        for qss_name in ("common.qss", "light.qss", "dark.qss"):
            _check_file(resource_root / "themes" / qss_name, errors)

    if not list(bundle_path.rglob("qwindows.dll")):
        errors.append("Qt platforms plugin qwindows.dll nije pronaden")

    if not list(bundle_path.rglob("PySide6*.dll")):
        errors.append("PySide6 DLL-ovi nisu pronadeni")

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
        errors.append(f"Datoteka ne postoji: {path}")
        return

    if path.is_file() and path.stat().st_size <= 0:
        errors.append(f"Datoteka je prazna: {path}")


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
