import logging
import shutil
import time
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.conversion_execution import run_conversion
from app.conversion_item import (
    ConversionItem,
    ConversionStatus,
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


class BatchConversionWorker(QObject):
    batch_started = Signal()
    item_started = Signal(str)
    item_progress = Signal(str, int)
    item_status_changed = Signal(str, str)
    item_finished = Signal(str, str)
    item_failed = Signal(str, str)
    item_cancelled = Signal(str)
    batch_finished = Signal(int, int, int)
    batch_cancelled = Signal()

    def __init__(
        self,
        items: list[ConversionItem],
        libreoffice_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.items = items
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
        success_count = 0
        failed_count = 0
        cancelled_count = 0
        batch_started_at = time.monotonic()

        self.batch_started.emit()
        logger.info("Batch conversion started items=%d", len(self.items))

        for item in self.items:
            if not item.can_run_again:
                continue

            if self.is_cancelled():
                cancelled_count += self._cancel_pending_items(
                    start_item=item
                )
                break

            result_path: Path | None = None
            item.set_status(ConversionStatus.CONVERTING)
            item.progress = 0
            item.result_path = None
            item.error_message = None

            self.item_started.emit(item.unique_id)
            self.item_progress.emit(item.unique_id, 0)
            item_started_at = time.monotonic()

            try:
                check_cancelled(self.is_cancelled)

                result_path = run_conversion(
                    input_file=item.input_path,
                    output_directory=item.output_directory,
                    output_format=item.output_format,
                    quality=item.quality,
                    dpi=item.dpi,
                    page_selection=item.page_selection,
                    multi_page_output_mode=(
                        item.multi_page_output_mode
                    ),
                    libreoffice_path=self.libreoffice_path,
                    cancel_check=self.is_cancelled,
                    progress_callback=lambda value, item_id=item.unique_id: (
                        self.item_progress.emit(item_id, value)
                    ),
                    status_callback=lambda message, item_id=item.unique_id: (
                        self.item_status_changed.emit(
                            item_id,
                            message,
                        )
                    ),
                )

                check_cancelled(self.is_cancelled)

                item.result_path = result_path
                item.progress = 100
                item.set_status(ConversionStatus.SUCCESS)
                success_count += 1
                logger.info(
                    "Batch item finished input=%s result=%s duration=%.2fs",
                    sanitize_path(item.input_path),
                    sanitize_path(result_path),
                    time.monotonic() - item_started_at,
                )

                self.item_progress.emit(item.unique_id, 100)
                self.item_finished.emit(
                    item.unique_id,
                    str(result_path),
                )

            except ConversionCancelledError:
                if result_path is not None:
                    self._remove_cancelled_result(result_path)

                item.set_status(
                    ConversionStatus.CANCELLED,
                    "Konverziju je prekinuo korisnik.",
                )
                item.error_message = item.status_message
                cancelled_count += 1
                logger.info(
                    "Batch item cancelled input=%s duration=%.2fs",
                    sanitize_path(item.input_path),
                    time.monotonic() - item_started_at,
                )
                self.item_cancelled.emit(item.unique_id)
                cancelled_count += self._cancel_remaining_after(item)
                break

            except Exception as error:
                error_info = exception_to_error_info(error)
                message = error_info.message
                log_exception_safely(
                    logger,
                    "Batch item failed input=%s duration=%.2fs",
                    sanitize_path(item.input_path),
                    time.monotonic() - item_started_at,
                )
                item.set_status(ConversionStatus.FAILED, message)
                item.error_message = message
                item.progress = 0
                failed_count += 1

                self.item_progress.emit(item.unique_id, 0)
                self.item_failed.emit(item.unique_id, message)

        if self.is_cancelled():
            self.batch_cancelled.emit()

        logger.info(
            (
                "Batch conversion finished success=%d failed=%d "
                "cancelled=%d duration=%.2fs"
            ),
            success_count,
            failed_count,
            cancelled_count,
            time.monotonic() - batch_started_at,
        )
        self.batch_finished.emit(
            success_count,
            failed_count,
            cancelled_count,
        )

    def _cancel_pending_items(
        self,
        start_item: ConversionItem,
    ) -> int:
        start_index = self.items.index(start_item)
        cancelled_count = 0

        for item in self.items[start_index:]:
            if item.status != ConversionStatus.PENDING:
                continue

            item.set_status(
                ConversionStatus.CANCELLED,
                "Grupna konverzija je prekinuta prije pokretanja stavke.",
            )
            item.error_message = item.status_message
            self.item_cancelled.emit(item.unique_id)
            cancelled_count += 1

        return cancelled_count

    def _cancel_remaining_after(
        self,
        active_item: ConversionItem,
    ) -> int:
        active_index = self.items.index(active_item)
        cancelled_count = 0

        for item in self.items[active_index + 1:]:
            if item.status != ConversionStatus.PENDING:
                continue

            item.set_status(
                ConversionStatus.CANCELLED,
                "Grupna konverzija je prekinuta prije pokretanja stavke.",
            )
            item.error_message = item.status_message
            self.item_cancelled.emit(item.unique_id)
            cancelled_count += 1

        return cancelled_count

    @staticmethod
    def _remove_cancelled_result(result_path: Path) -> None:
        try:
            if result_path.is_dir():
                shutil.rmtree(result_path, ignore_errors=True)
            elif result_path.exists():
                result_path.unlink(missing_ok=True)
        except OSError:
            pass
