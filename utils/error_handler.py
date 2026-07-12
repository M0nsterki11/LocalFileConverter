from __future__ import annotations

from dataclasses import dataclass

from app.exceptions import (
    ConversionCancelledError,
    CorruptedFileError,
    DependencyNotFoundError,
    FileLockedError,
    InputFileError,
    InsufficientDiskSpaceError,
    LocalFileConverterError,
    OutputDirectoryError,
    UnsupportedFormatError,
)
from utils.logging_utils import sanitize_for_log


@dataclass(frozen=True)
class ErrorInfo:
    title: str
    message: str
    technical_detail: str
    suggestion: str | None = None


def exception_to_error_info(error: BaseException) -> ErrorInfo:
    technical_detail = _technical_detail(error)
    message_text = str(error)
    lowered = message_text.casefold()

    if isinstance(error, ConversionCancelledError):
        return ErrorInfo(
            title="Konverzija je prekinuta",
            message="Konverziju je prekinuo korisnik.",
            technical_detail=technical_detail,
        )

    if isinstance(error, FileNotFoundError):
        return ErrorInfo(
            title="Datoteka nije pronadena",
            message="Odabrana datoteka vise ne postoji.",
            technical_detail=technical_detail,
            suggestion="Provjeri je li datoteka premjestena ili obrisana.",
        )

    if isinstance(error, PermissionError):
        return ErrorInfo(
            title="Pristup nije dopusten",
            message="Windows nije dopustio pristup datoteci ili izlaznoj mapi.",
            technical_detail=technical_detail,
            suggestion="Zatvori program koji koristi datoteku ili odaberi drugu mapu.",
        )

    if isinstance(error, InsufficientDiskSpaceError):
        return ErrorInfo(
            title="Nema dovoljno prostora",
            message="Na disku nema dovoljno slobodnog prostora za zavrsetak konverzije.",
            technical_detail=technical_detail,
            suggestion="Oslobodi prostor ili odaberi drugu izlaznu mapu.",
        )

    if isinstance(error, UnsupportedFormatError) or "nije podr" in lowered:
        return ErrorInfo(
            title="Nepodrzani format",
            message="Odabrani format nije podrzan.",
            technical_detail=technical_detail,
            suggestion="Odaberi datoteku s podrzanom ekstenzijom.",
        )

    if isinstance(error, FileLockedError) or _looks_locked(lowered):
        return ErrorInfo(
            title="Datoteka je zauzeta",
            message="Datoteku trenutacno koristi drugi program. Zatvori je i pokusaj ponovno.",
            technical_detail=technical_detail,
            suggestion="Zatvori Word, PDF reader, editor slika ili sync alat koji koristi datoteku.",
        )

    if isinstance(error, CorruptedFileError) or _looks_password_pdf(lowered):
        if _looks_password_pdf(lowered):
            return ErrorInfo(
                title="PDF je zakljucan",
                message="PDF je zakljucan lozinkom i ne moze se obraditi.",
                technical_detail=technical_detail,
                suggestion="Otvori PDF, ukloni lozinku i pokusaj ponovno.",
            )

        if _looks_image_error(lowered):
            return ErrorInfo(
                title="Slika nije valjana",
                message="Slika je ostecena ili nije valjana slikovna datoteka.",
                technical_detail=technical_detail,
            )

        return ErrorInfo(
            title="Datoteka nije valjana",
            message="PDF se ne moze otvoriti ili je ostecen.",
            technical_detail=technical_detail,
            suggestion="Provjeri datoteku u izvornom programu i pokusaj ponovno.",
        )

    if isinstance(error, DependencyNotFoundError) or _looks_libreoffice_missing(lowered):
        return ErrorInfo(
            title="LibreOffice nije pronaden",
            message="LibreOffice nije pronaden. Instaliraj ga ili odaberi soffice.exe.",
            technical_detail=technical_detail,
            suggestion="U Postavkama odaberi ispravnu putanju do soffice.exe.",
        )

    if isinstance(error, OutputDirectoryError):
        return ErrorInfo(
            title="Problem s izlaznom mapom",
            message="Izlazna mapa nije dostupna za spremanje rezultata.",
            technical_detail=technical_detail,
            suggestion="Odaberi drugu izlaznu mapu ili provjeri dozvole.",
        )

    if isinstance(error, InputFileError):
        return ErrorInfo(
            title="Problem s ulaznom datotekom",
            message=(
                getattr(error, "user_message", None)
                or "Ulazna datoteka nije dostupna za konverziju."
            ),
            technical_detail=technical_detail,
            suggestion=getattr(error, "suggestion", None),
        )

    if isinstance(error, LocalFileConverterError):
        return ErrorInfo(
            title="Konverzija nije uspjela",
            message=(
                getattr(error, "user_message", None)
                or _short_user_message(message_text)
            ),
            technical_detail=technical_detail,
            suggestion=getattr(error, "suggestion", None),
        )

    return ErrorInfo(
        title="Neocekivana greska",
        message="Konverzija nije uspjela zbog neocekivane greske. Tehnicki detalji spremljeni su u log.",
        technical_detail=technical_detail,
    )


def _technical_detail(error: BaseException) -> str:
    return sanitize_for_log(
        f"{error.__class__.__name__}: {str(error) or '<bez poruke>'}"
    )


def _short_user_message(message: str) -> str:
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    return first_line or "Konverzija nije uspjela."


def _looks_locked(text: str) -> bool:
    return any(
        fragment in text
        for fragment in (
            "being used",
            "permission denied",
            "access is denied",
            "proces ne moze pristupiti",
            "koristi drugi program",
            "winerror 32",
            "winerror 5",
        )
    )


def _looks_password_pdf(text: str) -> bool:
    return "lozink" in text or "password" in text or "needs pass" in text


def _looks_image_error(text: str) -> bool:
    return any(
        fragment in text
        for fragment in (
            "image",
            "slika",
            "cannot identify image",
            "truncated",
        )
    )


def _looks_libreoffice_missing(text: str) -> bool:
    return "libreoffice" in text and (
        "nije prona" in text or "not found" in text
    )
