import os
import shutil
from pathlib import Path


VALID_LIBREOFFICE_EXECUTABLE_NAMES = {
    "soffice.exe",
    "soffice.com",
    "soffice",
}


def is_valid_libreoffice_executable(
    executable_path: str | Path | None,
) -> bool:
    """Return whether the path points to a valid LibreOffice executable."""
    if executable_path is None:
        return False

    path = Path(executable_path)

    return (
        path.exists()
        and path.is_file()
        and path.name.lower()
        in VALID_LIBREOFFICE_EXECUTABLE_NAMES
    )


def find_libreoffice(
    saved_path: str | Path | None = None,
) -> Path | None:
    """
    Try to find LibreOffice automatically.

    Search order:
    1. previously saved path
    2. Windows PATH
    3. common installation folders
    """
    candidates: list[Path] = []

    if saved_path is not None:
        candidates.append(Path(saved_path))

    path_executable = (
        shutil.which("soffice.exe")
        or shutil.which("soffice.com")
        or shutil.which("soffice")
    )

    if path_executable:
        candidates.append(Path(path_executable))

    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    local_app_data = os.environ.get("LOCALAPPDATA")

    if program_files:
        candidates.append(
            Path(program_files)
            / "LibreOffice"
            / "program"
            / "soffice.exe"
        )

    if program_files_x86:
        candidates.append(
            Path(program_files_x86)
            / "LibreOffice"
            / "program"
            / "soffice.exe"
        )

    if local_app_data:
        candidates.append(
            Path(local_app_data)
            / "Programs"
            / "LibreOffice"
            / "program"
            / "soffice.exe"
        )

    checked_paths: set[str] = set()

    for candidate in candidates:
        normalized_path = str(candidate).lower()

        if normalized_path in checked_paths:
            continue

        checked_paths.add(normalized_path)

        if is_valid_libreoffice_executable(candidate):
            return candidate.resolve()

    return None


def get_default_libreoffice_browse_directory() -> Path:
    """Return a reasonable start folder for manual LibreOffice selection."""
    program_files = os.environ.get("ProgramFiles")

    if program_files:
        libreoffice_directory = (
            Path(program_files)
            / "LibreOffice"
            / "program"
        )

        if libreoffice_directory.exists():
            return libreoffice_directory

        return Path(program_files)

    return Path.home()
