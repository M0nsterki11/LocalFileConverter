from __future__ import annotations

import sys
from pathlib import Path


def get_bundle_roots() -> tuple[Path, ...]:
    """Return candidate roots used for bundled runtime resources."""
    if getattr(sys, "frozen", False):
        roots: list[Path] = []
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            roots.append(Path(meipass))

        executable_root = Path(sys.executable).resolve().parent
        roots.append(executable_root)
        roots.append(executable_root / "_internal")

        unique_roots: list[Path] = []
        seen: set[Path] = set()

        for root in roots:
            resolved_root = root.resolve()

            if resolved_root not in seen:
                unique_roots.append(resolved_root)
                seen.add(resolved_root)

        return tuple(unique_roots)

    return (Path(__file__).resolve().parent.parent,)


def get_bundle_root() -> Path:
    """Return the preferred root used for bundled runtime resources."""
    return get_bundle_roots()[0]


def get_resource_path(relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    roots = get_bundle_roots()

    for root in roots:
        candidate = root / relative

        if candidate.exists():
            return candidate

    return roots[0] / relative


def resource_exists(relative_path: str | Path) -> bool:
    return get_resource_path(relative_path).exists()
