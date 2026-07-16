from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import uuid4

from app.i18n import translate
from app.settings import (
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    DEFAULT_OFFICE_ENGINE,
    DEFAULT_PDF_DPI,
)
from utils.format_utils import (
    get_available_output_formats,
    get_display_format,
    is_supported_file,
)
from utils.input_validation import validate_input_file_for_queue


class ConversionStatus(Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def display_label(self) -> str:
        return {
            ConversionStatus.PENDING: translate("ConversionStatus", "Pending"),
            ConversionStatus.CONVERTING: translate("ConversionStatus", "Converting"),
            ConversionStatus.SUCCESS: translate("ConversionStatus", "Success"),
            ConversionStatus.FAILED: translate("ConversionStatus", "Error"),
            ConversionStatus.CANCELLED: translate("ConversionStatus", "Cancelled"),
        }[self]


@dataclass
class ConversionItem:
    input_path: Path
    input_format: str
    output_format: str
    output_directory: Path
    unique_id: str = field(
        default_factory=lambda: uuid4().hex
    )
    status: ConversionStatus = ConversionStatus.PENDING
    progress: int = 0
    result_path: Path | None = None
    error_message: str | None = None
    quality: int = DEFAULT_IMAGE_QUALITY
    dpi: int = DEFAULT_PDF_DPI
    page_selection: str | None = None
    multi_page_output_mode: str = DEFAULT_MULTI_PAGE_OUTPUT_MODE
    office_engine: str = DEFAULT_OFFICE_ENGINE
    status_message: str | None = None

    @property
    def available_output_formats(self) -> list[str]:
        return get_available_output_formats(self.input_path)

    @property
    def can_run_again(self) -> bool:
        return self.status in {
            ConversionStatus.PENDING,
            ConversionStatus.FAILED,
            ConversionStatus.CANCELLED,
        }

    def mark_pending_for_run(
        self,
        output_directory: Path,
    ) -> None:
        self.output_directory = output_directory
        self.status = ConversionStatus.PENDING
        self.progress = 0
        self.result_path = None
        self.error_message = None
        self.status_message = None

    def set_status(
        self,
        status: ConversionStatus,
        message: str | None = None,
    ) -> None:
        self.status = status
        self.status_message = message


@dataclass
class AddFilesResult:
    added_items: list[ConversionItem]
    unsupported_paths: list[Path]
    duplicate_paths: list[Path]


def normalize_input_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve()).casefold()


def create_conversion_item(
    input_path: str | Path,
    output_directory: str | Path,
    office_engine: str = DEFAULT_OFFICE_ENGINE,
    quality: int = DEFAULT_IMAGE_QUALITY,
    dpi: int = DEFAULT_PDF_DPI,
    multi_page_output_mode: str = DEFAULT_MULTI_PAGE_OUTPUT_MODE,
) -> ConversionItem:
    path = Path(input_path)
    output_formats = get_available_output_formats(path)

    if not output_formats:
        raise ValueError(
            translate(
                "ConversionItem",
                "The selected format is currently not supported.",
            )
        )

    return ConversionItem(
        input_path=path,
        input_format=get_display_format(path),
        output_format=output_formats[0],
        output_directory=Path(output_directory),
        quality=quality,
        dpi=dpi,
        multi_page_output_mode=multi_page_output_mode,
        office_engine=office_engine,
    )


def build_unique_supported_items(
    file_paths: list[str | Path],
    existing_items: list[ConversionItem],
    output_directory: str | Path,
    office_engine: str = DEFAULT_OFFICE_ENGINE,
    quality: int = DEFAULT_IMAGE_QUALITY,
    dpi: int = DEFAULT_PDF_DPI,
    multi_page_output_mode: str = DEFAULT_MULTI_PAGE_OUTPUT_MODE,
) -> AddFilesResult:
    known_paths = {
        normalize_input_path(item.input_path)
        for item in existing_items
    }

    added_items: list[ConversionItem] = []
    unsupported_paths: list[Path] = []
    duplicate_paths: list[Path] = []

    for file_path in file_paths:
        path = Path(file_path)

        try:
            validate_input_file_for_queue(path)
        except Exception:
            unsupported_paths.append(path)
            continue

        if not is_supported_file(path):
            unsupported_paths.append(path)
            continue

        normalized_path = normalize_input_path(path)

        if normalized_path in known_paths:
            duplicate_paths.append(path)
            continue

        item = create_conversion_item(
            input_path=path,
            output_directory=output_directory,
            office_engine=office_engine,
            quality=quality,
            dpi=dpi,
            multi_page_output_mode=multi_page_output_mode,
        )
        added_items.append(item)
        known_paths.add(normalized_path)

    return AddFilesResult(
        added_items=added_items,
        unsupported_paths=unsupported_paths,
        duplicate_paths=duplicate_paths,
    )
