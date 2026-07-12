from collections.abc import Callable
from pathlib import Path

from app.constants import (
    IMAGE_EXTENSIONS,
    OFFICE_EXTENSIONS,
)
from converters.base_converter import CancelCheck
from converters.image_converter import convert_image
from converters.office_converter import convert_office_to_pdf
from converters.pdf_converter import (
    convert_image_to_pdf,
    convert_pdf_to_images,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


def run_conversion(
    input_file: str | Path,
    output_directory: str | Path,
    output_format: str,
    quality: int = 90,
    dpi: int = 150,
    page_selection: str | None = None,
    multi_page_output_mode: str = "folder",
    libreoffice_path: str | Path | None = None,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    input_path = Path(input_file)
    normalized_format = output_format.upper()
    extension = input_path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        if normalized_format == "PDF":
            return convert_image_to_pdf(
                input_file=input_path,
                output_directory=output_directory,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )

        return convert_image(
            input_file=input_path,
            output_directory=output_directory,
            output_format=normalized_format,
            quality=quality,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    if extension == ".pdf":
        return convert_pdf_to_images(
            input_file=input_path,
            output_directory=output_directory,
            output_format=normalized_format,
            dpi=dpi,
            quality=quality,
            page_selection=page_selection,
            multi_page_output_mode=multi_page_output_mode,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    if extension in OFFICE_EXTENSIONS:
        if normalized_format != "PDF":
            raise ValueError(
                "Office dokumenti trenutačno se mogu "
                "pretvoriti samo u PDF."
            )

        if libreoffice_path is None:
            raise ValueError(
                "LibreOffice putanja nije postavljena."
            )

        return convert_office_to_pdf(
            input_file=input_path,
            output_directory=output_directory,
            libreoffice_executable=libreoffice_path,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )

    raise ValueError(
        "Odabrani format još nije podržan za konverziju."
    )
