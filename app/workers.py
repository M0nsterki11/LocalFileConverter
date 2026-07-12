from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from converters.image_converter import convert_image


class ImageConversionWorker(QObject):
    """Izvodi konverziju slike izvan glavnog UI threada."""

    progress_changed = Signal(int)
    status_changed = Signal(str)

    conversion_finished = Signal(str)
    conversion_failed = Signal(str)

    def __init__(
        self,
        input_file: str | Path,
        output_directory: str | Path,
        output_format: str,
        quality: int,
    ) -> None:
        super().__init__()

        self.input_file = Path(input_file)
        self.output_directory = Path(output_directory)
        self.output_format = output_format
        self.quality = quality

    @Slot()
    def run(self) -> None:
        try:
            result_path = convert_image(
                input_file=self.input_file,
                output_directory=self.output_directory,
                output_format=self.output_format,
                quality=self.quality,
                progress_callback=self.progress_changed.emit,
                status_callback=self.status_changed.emit,
            )

            self.conversion_finished.emit(str(result_path))

        except Exception as error:
            self.conversion_failed.emit(str(error))