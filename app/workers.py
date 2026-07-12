import shutil
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.conversion_execution import run_conversion
from converters.base_converter import (
    ConversionCancelledError,
    check_cancelled,
)


class ConversionWorker(QObject):
    """Izvodi konverziju izvan glavnog UI threada."""

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
        quality: int = 90,
        dpi: int = 150,
        page_selection: str | None = None,
        multi_page_output_mode: str = "folder",
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
        result_path: Path | None = None

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

            self.conversion_finished.emit(str(result_path))

        except ConversionCancelledError as error:
            if result_path is not None:
                self._remove_cancelled_result(result_path)

            self.conversion_cancelled.emit(str(error))

        except Exception as error:
            self.conversion_failed.emit(str(error))

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
