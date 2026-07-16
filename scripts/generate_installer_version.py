from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_FILE = PROJECT_ROOT / "app" / "constants.py"
OUTPUT_FILE = PROJECT_ROOT / "packaging" / "generated_version.iss"


def read_app_version() -> str:
    text = CONSTANTS_FILE.read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)

    if match is None:
        raise RuntimeError("APP_VERSION was not found in app/constants.py")

    return match.group(1)


def main() -> int:
    version = read_app_version()
    setup_base_name = f"LocalFileConverter_Setup_{version}_x64"
    content = f"""#define AppVersion \"{version}\"
#define AppName \"Local File Converter\"
#define AppPublisher \"LocalFileConverter\"
#define AppExeName \"LocalFileConverter.exe\"
#define AppSetupBaseName \"{setup_base_name}\"
"""
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} for version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
