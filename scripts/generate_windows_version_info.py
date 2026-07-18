from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_FILE = PROJECT_ROOT / "app" / "constants.py"
OUTPUT_FILE = PROJECT_ROOT / "packaging" / "windows_version_info.txt"


def read_app_version() -> str:
    text = CONSTANTS_FILE.read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)

    if match is None:
        raise RuntimeError("APP_VERSION was not found in app/constants.py")

    return match.group(1)


def to_windows_version(version: str) -> tuple[int, int, int, int]:
    numeric_part = version.split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []

    for part in numeric_part.split("."):
        try:
            parts.append(max(0, int(part)))
        except ValueError:
            parts.append(0)

    while len(parts) < 4:
        parts.append(0)

    return tuple(parts[:4])


def build_version_info(version: str) -> str:
    numeric = to_windows_version(version)
    year = _dt.date.today().year

    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'MyFile Converter'),
          StringStruct('FileDescription', 'MyFile Converter'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'MyFileConverter'),
          StringStruct('OriginalFilename', 'MyFileConverter.exe'),
          StringStruct('ProductName', 'MyFile Converter'),
          StringStruct('ProductVersion', '{version}'),
          StringStruct('LegalCopyright', 'Copyright {year}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    version = read_app_version()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        build_version_info(version),
        encoding="utf-8",
    )
    print(f"Generated {OUTPUT_FILE} for version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
