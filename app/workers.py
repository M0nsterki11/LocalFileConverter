import shutil
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.constants import IMAGE_EXTENSIONS
from converters.base_converter import (
    ConversionCancelledError,
    check_cancelled,
)
from converters.image_converter import convert_image
from converters.pdf_converter import (
    convert_image_to_pdf,
    convert_pdf_to_images,
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
    ) -> None:
        super().__init__()

        self.input_file = Path(input_file)
        self.output_directory = Path(output_directory)
        self.output_format = output_format.upper()
        self.quality = quality
        self.dpi = dpi
        self.page_selection = page_selection
        self.multi_page_output_mode = multi_page_output_mode

        self._cancel_event = Event()

    def cancel(self) -> None:
        """
        Thread-safe zahtjev za prekid.

        Ova metoda samo postavlja Event, pa je sigurno pozvati
        je iz glavnog UI threada.
        """
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @Slot()
    def run(self) -> None:
        result_path: Path | None = None

        try:
            check_cancelled(self.is_cancelled)

            extension = self.input_file.suffix.lower()

            if extension in IMAGE_EXTENSIONS:
                result_path = self._convert_image_input()

            elif extension == ".pdf":
                result_path = convert_pdf_to_images(
                    input_file=self.input_file,
                    output_directory=self.output_directory,
                    output_format=self.output_format,
                    dpi=self.dpi,
                    quality=self.quality,
                    page_selection=self.page_selection,
                    multi_page_output_mode=self.multi_page_output_mode,
                    progress_callback=self.progress_changed.emit,
                    status_callback=self.status_changed.emit,
                    cancel_check=self.is_cancelled,
                )

            else:
                raise ValueError(
                    "Odabrani format još nije podržan za konverziju."
                )

            # Kod konverzija koje se ne mogu zaustaviti usred spremanja,
            # provjeravamo prekid odmah nakon završetka i brišemo rezultat.
            check_cancelled(self.is_cancelled)

            self.conversion_finished.emit(str(result_path))

        except ConversionCancelledError as error:
            if result_path is not None:
                self._remove_cancelled_result(result_path)

            self.conversion_cancelled.emit(str(error))

        except Exception as error:
            self.conversion_failed.emit(str(error))

    def _convert_image_input(self) -> Path:
        if self.output_format == "PDF":
            return convert_image_to_pdf(
                input_file=self.input_file,
                output_directory=self.output_directory,
                progress_callback=self.progress_changed.emit,
                status_callback=self.status_changed.emit,
            )

        return convert_image(
            input_file=self.input_file,
            output_directory=self.output_directory,
            output_format=self.output_format,
            quality=self.quality,
            progress_callback=self.progress_changed.emit,
            status_callback=self.status_changed.emit,
        )

    @staticmethod
    def _remove_cancelled_result(result_path: Path) -> None:
        """Briše rezultat koji je nastao nakon zahtjeva za prekid."""
        try:
            if result_path.is_dir():
                shutil.rmtree(result_path, ignore_errors=True)

            elif result_path.exists():
                result_path.unlink(missing_ok=True)

        except OSError:
            # Prekid konverzije ne smije srušiti aplikaciju
            # ako Windows trenutačno drži rezultat zaključanim.
            pass