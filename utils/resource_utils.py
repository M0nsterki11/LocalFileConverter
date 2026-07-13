from __future__ import annotations

import sys
from pathlib import Path


def get_bundle_root() -> Path:
    """Return the root used for bundled runtime resources."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            return Path(meipass)

        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def get_resource_path(relative_path: str | Path) -> Path:
    return get_bundle_root() / Path(relative_path)


def resource_exists(relative_path: str | Path) -> bool:
    return get_resource_path(relative_path).exists()
