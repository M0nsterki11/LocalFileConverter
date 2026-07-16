import logging
import shutil
import time
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.conversion_execution import run_conversion
from app.settings import (
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    DEFAULT_PDF_DPI,
)
from converters.base_converter import (
    ConversionCancelledError,
    check_cancelled,
)
from utils.error_handler import exception_to_error_info
from utils.logging_utils import (
    LOGGER_NAME,
    log_exception_safely,
    sanitize_path,
)


class ConversionWorker(QObject):
    """Run a conversion outside the main UI thread."""

    progress_changed = Signal(int)
    status_changed = Signal(str)

    conversion_finished = Signal(str)
    conversion_failed = Signal(str)
    conversion_cancelled = Signal(str)

    def __init__(
        self,
        input_file: str | Path,
        output_directory: str | Path,
        output_format: str,
        quality: int = DEFAULT_IMAGE_QUALITY,
        dpi: int = DEFAULT_PDF_DPI,
        page_selection: str | None = None,
        multi_page_output_mode: str = DEFAULT_MULTI_PAGE_OUTPUT_MODE,
        libreoffice_path: str | Path | None = None,
    ) -> None:
        super().__init__()

        self.input_file = Path(input_file)
        self.output_directory = Path(output_directory)
        self.output_format = output_format.upper()
        self.quality = quality
        self.dpi = dpi
        self.page_selection = page_selection
        self.multi_page_output_mode = multi_page_output_mode

        self.libreoffice_path = (
            Path(libreoffice_path)
            if libreoffice_path is not None
            else None
        )

        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        result_path: Path | None = None
        started_at = time.monotonic()

        try:
            check_cancelled(self.is_cancelled)

            result_path = run_conversion(
                input_file=self.input_file,
                output_directory=self.output_directory,
                output_format=self.output_format,
                quality=self.quality,
                dpi=self.dpi,
                page_selection=self.page_selection,
                multi_page_output_mode=self.multi_page_output_mode,
                libreoffice_path=self.libreoffice_path,
                cancel_check=self.is_cancelled,
                progress_callback=self.progress_changed.emit,
                status_callback=self.status_changed.emit,
            )

            check_cancelled(self.is_cancelled)

            logger.info(
                "Worker conversion finished input=%s result=%s duration=%.2fs",
                sanitize_path(self.input_file),
                sanitize_path(result_path),
                time.monotonic() - started_at,
            )
            self.conversion_finished.emit(str(result_path))

        except ConversionCancelledError as error:
            if result_path is not None:
                self._remove_cancelled_result(result_path)

            logger.info(
                "Worker conversion cancelled input=%s duration=%.2fs",
                sanitize_path(self.input_file),
                time.monotonic() - started_at,
            )
            self.conversion_cancelled.emit(str(error))

        except Exception as error:
            error_info = exception_to_error_info(error)
            log_exception_safely(
                logger,
                "Worker conversion failed input=%s duration=%.2fs",
                sanitize_path(self.input_file),
                time.monotonic() - started_at,
            )
            self.conversion_failed.emit(error_info.message)

    @staticmethod
    def _remove_cancelled_result(
        result_path: Path,
    ) -> None:
        try:
            if result_path.is_dir():
                shutil.rmtree(
                    result_path,
                    ignore_errors=True,
                )

            elif result_path.exists():
                result_path.unlink(missing_ok=True)

        except OSError:
            pass
