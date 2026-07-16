from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from app.exceptions import (
    InsufficientDiskSpaceError,
    OutputDirectoryError,
)
from app.i18n import translate
from utils.file_utils import generate_unique_output_directory


MIN_FREE_SPACE_RESERVE_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class DiskSpaceCheck:
    required_bytes: int
    available_bytes: int
    reserve_bytes: int


def ensure_output_directory_ready(
    output_directory: str | Path,
) -> Path:
    path = Path(output_directory)

    try:
        if path.exists() and not path.is_dir():
            raise OutputDirectoryError(
                _tr("The output path exists, but it is not a folder.")
            )

        path.mkdir(parents=True, exist_ok=True)
    except OutputDirectoryError:
        raise
    except OSError as error:
        raise OutputDirectoryError(
            _tr("Could not create the output folder: {error}").format(
                error=error,
            )
        ) from error

    test_path = path / f".lfc_write_test_{uuid4().hex}.tmp"

    try:
        with test_path.open("xb") as test_file:
            test_file.write(b"ok")
    except PermissionError as error:
        raise OutputDirectoryError(
            _tr("Windows denied write access to the output folder.")
        ) from error
    except OSError as error:
        raise OutputDirectoryError(
            _tr("The output folder is not writable: {error}").format(
                error=error,
            )
        ) from error
    finally:
        try:
            test_path.unlink(missing_ok=True)
        except OSError:
            pass

    return path


def estimate_required_space_bytes(
    input_paths: str | Path | list[str | Path],
    *,
    operation: str,
    output_format: str | None = None,
    dpi: int = 150,
    page_count: int | None = None,
) -> int:
    paths = _normalize_paths(input_paths)
    total_input_bytes = sum(_safe_file_size(path) for path in paths)
    dpi_factor = max(1.0, (max(72, int(dpi)) / 150.0) ** 2)
    page_factor = max(1, int(page_count or 1))
    operation_key = operation.lower()

    if operation_key == "image_to_image":
        return max(total_input_bytes * 4, 1 * 1024 * 1024)

    if operation_key == "image_to_pdf":
        return max(total_input_bytes * 3, 2 * 1024 * 1024)

    if operation_key == "pdf_to_images":
        format_factor = 1.6 if (output_format or "").upper() == "JPG" else 3.0
        page_floor = int(page_factor * 2 * 1024 * 1024 * dpi_factor)
        return max(
            int(total_input_bytes * format_factor * dpi_factor),
            page_floor,
        )

    if operation_key == "office_to_pdf":
        return max(total_input_bytes * 5, 5 * 1024 * 1024)

    if operation_key == "images_to_pdf":
        return max(total_input_bytes * 3, 2 * 1024 * 1024)

    if operation_key == "zip":
        return max(int(total_input_bytes * 1.2), 1 * 1024 * 1024)

    return max(total_input_bytes * 3, 10 * 1024 * 1024)


def ensure_sufficient_disk_space(
    output_directory: str | Path,
    required_bytes: int,
    *,
    reserve_bytes: int = MIN_FREE_SPACE_RESERVE_BYTES,
    usage_provider=shutil.disk_usage,
) -> DiskSpaceCheck:
    output_path = Path(output_directory)

    try:
        usage = usage_provider(output_path)
        available_bytes = int(
            usage.free if hasattr(usage, "free") else usage[2]
        )
    except OSError as error:
        raise OutputDirectoryError(
            _tr("Could not check free disk space: {error}").format(
                error=error,
            )
        ) from error

    total_required = int(required_bytes) + int(reserve_bytes)

    if available_bytes < total_required:
        raise InsufficientDiskSpaceError(
            (
                _tr(
                    "The disk does not have enough free space. "
                    "Required: {required}, available: {available}."
                ).format(
                    required=human_readable_size(total_required),
                    available=human_readable_size(available_bytes),
                )
            ),
            required_bytes=total_required,
            available_bytes=available_bytes,
        )

    return DiskSpaceCheck(
        required_bytes=int(required_bytes),
        available_bytes=available_bytes,
        reserve_bytes=int(reserve_bytes),
    )


def human_readable_size(size_bytes: int) -> str:
    value = float(max(0, int(size_bytes)))

    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} GB"


def get_temporary_output_path(final_path: str | Path) -> Path:
    path = Path(final_path)
    return path.parent / f".{path.name}.{uuid4().hex}.part"


def publish_temporary_file(
    temporary_path: str | Path,
    final_path: str | Path,
) -> Path:
    temp_path = Path(temporary_path)
    requested_final_path = Path(final_path)

    if not temp_path.exists() or not temp_path.is_file():
        raise OutputDirectoryError(
            _tr("The temporary output file was not found.")
        )

    if temp_path.stat().st_size <= 0:
        raise OutputDirectoryError(
            _tr("The temporary output file is empty.")
        )

    final_candidate = _unique_file_candidate(requested_final_path)

    try:
        temp_path.rename(final_candidate)
    except FileExistsError:
        final_candidate = _unique_file_candidate(requested_final_path)
        temp_path.rename(final_candidate)
    except OSError as error:
        raise OutputDirectoryError(
            _tr("Could not save the final file: {error}").format(
                error=error,
            )
        ) from error

    return final_candidate


def publish_temporary_directory(
    temporary_directory: str | Path,
    final_directory: str | Path,
) -> Path:
    temp_path = Path(temporary_directory)
    requested_final_path = Path(final_directory)

    if not temp_path.exists() or not temp_path.is_dir():
        raise OutputDirectoryError(
            _tr("The temporary output folder was not found.")
        )

    final_candidate = generate_unique_output_directory(
        input_file=requested_final_path,
        output_directory=requested_final_path.parent,
        name_suffix="",
    )

    try:
        temp_path.rename(final_candidate)
    except FileExistsError:
        final_candidate = generate_unique_output_directory(
            input_file=requested_final_path,
            output_directory=requested_final_path.parent,
            name_suffix="",
        )
        temp_path.rename(final_candidate)
    except OSError as error:
        raise OutputDirectoryError(
            _tr("Could not save the final folder: {error}").format(
                error=error,
            )
        ) from error

    return final_candidate


def validate_zip_file(zip_path: str | Path) -> None:
    path = Path(zip_path)

    try:
        with ZipFile(path, mode="r") as archive:
            broken_member = archive.testzip()
    except BadZipFile as error:
        raise OutputDirectoryError(
            _tr("The ZIP archive is not readable after saving.")
        ) from error

    if broken_member is not None:
        raise OutputDirectoryError(
            _tr(
                "The ZIP archive contains an invalid file: {file_name}"
            ).format(file_name=broken_member)
        )


def cleanup_temporary_path(path: str | Path | None) -> None:
    if path is None:
        return

    target = Path(path)

    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink(missing_ok=True)
    except OSError:
        pass


def _normalize_paths(
    input_paths: str | Path | list[str | Path],
) -> list[Path]:
    if isinstance(input_paths, (str, Path)):
        return [Path(input_paths)]

    return [Path(path) for path in input_paths]


def _safe_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _unique_file_candidate(requested_path: Path) -> Path:
    candidate = requested_path
    counter = 1

    while candidate.exists():
        candidate = (
            requested_path.parent
            / f"{requested_path.stem}_{counter}{requested_path.suffix}"
        )
        counter += 1

    return candidate


def _tr(source_text: str) -> str:
    return translate("OutputSafety", source_text)
