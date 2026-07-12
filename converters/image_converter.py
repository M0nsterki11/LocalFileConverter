from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.constants import IMAGE_EXTENSIONS
from utils.file_utils import generate_unique_output_path


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


class ImageConversionError(Exception):
    """Greška nastala tijekom konverzije slike."""


OUTPUT_EXTENSIONS = {
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


def convert_image(
    input_file: str | Path,
    output_directory: str | Path,
    output_format: str,
    quality: int = 90,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    """
    Pretvara JPG, PNG i WEBP slike.

    Originalna datoteka se nikada ne mijenja.
    """
    input_path = Path(input_file)
    output_path = Path(output_directory)
    normalized_format = output_format.upper()

    if not input_path.exists():
        raise ImageConversionError(
            f"Ulazna datoteka ne postoji:\n{input_path}"
        )

    if not input_path.is_file():
        raise ImageConversionError(
            "Odabrana putanja nije datoteka."
        )

    if input_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ImageConversionError(
            f"Format {input_path.suffix} nije podržana slika."
        )

    if normalized_format not in OUTPUT_EXTENSIONS:
        raise ImageConversionError(
            f"Izlazni format {normalized_format} nije podržan."
        )

    quality = max(1, min(100, int(quality)))

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ImageConversionError(
            f"Nije moguće stvoriti izlaznu mapu:\n{error}"
        ) from error

    result_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_path,
        output_extension=OUTPUT_EXTENSIONS[normalized_format],
    )

    try:
        _emit_status(
            status_callback,
            f"Otvaranje datoteke {input_path.name}...",
        )
        _emit_progress(progress_callback, 10)

        with Image.open(input_path) as source_image:
            source_image.load()

            # Ispravlja rotaciju fotografija snimljenih mobitelom.
            image = ImageOps.exif_transpose(source_image)

            _emit_status(
                status_callback,
                f"Priprema slike za {normalized_format} format...",
            )
            _emit_progress(progress_callback, 35)

            prepared_image = _prepare_image(
                image=image,
                output_format=normalized_format,
            )

            _emit_status(
                status_callback,
                f"Spremanje datoteke {result_path.name}...",
            )
            _emit_progress(progress_callback, 70)

            _save_image(
                image=prepared_image,
                output_path=result_path,
                output_format=normalized_format,
                quality=quality,
            )

        if not result_path.exists():
            raise ImageConversionError(
                "Konverzija je završila, ali izlazna datoteka nije pronađena."
            )

        _emit_progress(progress_callback, 100)
        _emit_status(status_callback, "Konverzija je završena.")

        return result_path

    except UnidentifiedImageError as error:
        raise ImageConversionError(
            "Datoteka nije valjana slika ili je oštećena."
        ) from error

    except PermissionError as error:
        raise ImageConversionError(
            "Nema dozvole za čitanje ili spremanje datoteke."
        ) from error

    except ImageConversionError:
        raise

    except OSError as error:
        raise ImageConversionError(
            f"Slika se nije mogla konvertirati:\n{error}"
        ) from error


def _prepare_image(
    image: Image.Image,
    output_format: str,
) -> Image.Image:
    """
    Priprema način boja ovisno o izlaznom formatu.

    JPG ne podržava transparentnost, pa se transparentna pozadina
    zamjenjuje bijelom pozadinom.
    """
    if output_format == "JPG":
        return _prepare_for_jpeg(image)

    if output_format == "PNG":
        if image.mode == "CMYK":
            return image.convert("RGB")

        return image.copy()

    if output_format == "WEBP":
        if _has_transparency(image):
            return image.convert("RGBA")

        return image.convert("RGB")

    raise ImageConversionError(
        f"Nepoznat izlazni format: {output_format}"
    )


def _prepare_for_jpeg(image: Image.Image) -> Image.Image:
    """Pretvara sliku u RGB i uklanja transparentnost."""
    if _has_transparency(image):
        rgba_image = image.convert("RGBA")

        white_background = Image.new(
            mode="RGB",
            size=rgba_image.size,
            color=(255, 255, 255),
        )

        white_background.paste(
            rgba_image,
            mask=rgba_image.getchannel("A"),
        )

        return white_background

    return image.convert("RGB")


def _has_transparency(image: Image.Image) -> bool:
    """Provjerava sadrži li slika transparentne piksele."""
    if image.mode in {"RGBA", "LA"}:
        return True

    if image.mode == "P" and "transparency" in image.info:
        return True

    return False


def _save_image(
    image: Image.Image,
    output_path: Path,
    output_format: str,
    quality: int,
) -> None:
    """Sprema pripremljenu sliku u traženom formatu."""
    if output_format == "JPG":
        image.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True,
        )
        return

    if output_format == "WEBP":
        image.save(
            output_path,
            format="WEBP",
            quality=quality,
            method=6,
        )
        return

    if output_format == "PNG":
        image.save(
            output_path,
            format="PNG",
            optimize=True,
        )
        return

    raise ImageConversionError(
        f"Spremanje formata {output_format} nije podržano."
    )


def _emit_progress(
    callback: ProgressCallback | None,
    value: int,
) -> None:
    if callback is not None:
        callback(value)


def _emit_status(
    callback: StatusCallback | None,
    message: str,
) -> None:
    if callback is not None:
        callback(message)