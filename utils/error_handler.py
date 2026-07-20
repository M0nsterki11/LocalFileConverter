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
from app.i18n import translate
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
            title=_tr("Conversion was cancelled"),
            message=_tr("The conversion was cancelled by the user."),
            technical_detail=technical_detail,
        )

    if isinstance(error, FileNotFoundError):
        return ErrorInfo(
            title=_tr("File was not found"),
            message=_tr("The selected file no longer exists."),
            technical_detail=technical_detail,
            suggestion=_tr("Check whether the file was moved or deleted."),
        )

    if isinstance(error, PermissionError):
        return ErrorInfo(
            title=_tr("Access was denied"),
            message=_tr(
                "Windows denied access to the file or output folder."
            ),
            technical_detail=technical_detail,
            suggestion=_tr(
                "Close the program using the file or choose another folder."
            ),
        )

    if isinstance(error, InsufficientDiskSpaceError):
        return ErrorInfo(
            title=_tr("Not enough disk space"),
            message=_tr(
                "The disk does not have enough free space to finish the conversion."
            ),
            technical_detail=technical_detail,
            suggestion=_tr("Free up space or choose another output folder."),
        )

    if isinstance(error, UnsupportedFormatError) or "not supported" in lowered:
        return ErrorInfo(
            title=_tr("Unsupported format"),
            message=_tr("The selected format is not supported."),
            technical_detail=technical_detail,
            suggestion=_tr("Choose a file with a supported extension."),
        )

    if isinstance(error, FileLockedError) or _looks_locked(lowered):
        return ErrorInfo(
            title=_tr("File is in use"),
            message=_tr(
                "The file is currently being used by another program. Close it and try again."
            ),
            technical_detail=technical_detail,
            suggestion=_tr(
                "Close Word, a PDF reader, an image editor, or the sync tool using the file."
            ),
        )

    if isinstance(error, CorruptedFileError) or _looks_password_pdf(lowered):
        if _looks_password_pdf(lowered):
            return ErrorInfo(
                title=_tr("PDF is locked"),
                message=_tr(
                    "The PDF is password-protected and cannot be processed."
                ),
                technical_detail=technical_detail,
                suggestion=_tr(
                    "Open the PDF, remove the password, and try again."
                ),
            )

        if _looks_image_error(lowered):
            return ErrorInfo(
                title=_tr("Image is not valid"),
                message=_tr(
                    "The image is corrupted or is not a valid image file."
                ),
                technical_detail=technical_detail,
            )

        return ErrorInfo(
            title=_tr("File is not valid"),
            message=_tr("The PDF cannot be opened or is corrupted."),
            technical_detail=technical_detail,
            suggestion=_tr(
                "Check the file in the original program and try again."
            ),
        )

    if isinstance(error, DependencyNotFoundError) or _looks_office_dependency_missing(
        lowered
    ):
        return ErrorInfo(
            title=_tr("Office conversion tool was not found"),
            message=(
                getattr(error, "user_message", None)
                or _tr(
                    "Microsoft Office or LibreOffice is required for this conversion."
                )
            ),
            technical_detail=technical_detail,
            suggestion=(
                getattr(error, "suggestion", None)
                or _tr(
                    "Install the matching Microsoft Office desktop application "
                    "or choose soffice.exe in Settings."
                )
            ),
        )

    if isinstance(error, OutputDirectoryError):
        return ErrorInfo(
            title=_tr("Output folder problem"),
            message=_tr(
                "The output folder is not available for saving results."
            ),
            technical_detail=technical_detail,
            suggestion=_tr(
                "Choose another output folder or check permissions."
            ),
        )

    if isinstance(error, InputFileError):
        return ErrorInfo(
            title=_tr("Input file problem"),
            message=(
                getattr(error, "user_message", None)
                or _tr("The input file is not available for conversion.")
            ),
            technical_detail=technical_detail,
            suggestion=getattr(error, "suggestion", None),
        )

    if isinstance(error, LocalFileConverterError):
        return ErrorInfo(
            title=_tr("Conversion failed"),
            message=(
                getattr(error, "user_message", None)
                or _short_user_message(message_text)
            ),
            technical_detail=technical_detail,
            suggestion=getattr(error, "suggestion", None),
        )

    return ErrorInfo(
        title=_tr("Unexpected error"),
        message=_tr(
            "The conversion failed because of an unexpected error. Technical details were saved to the log."
        ),
        technical_detail=technical_detail,
    )


def _tr(source_text: str) -> str:
    return translate("ErrorHandler", source_text)


def _technical_detail(error: BaseException) -> str:
    return sanitize_for_log(
        f"{error.__class__.__name__}: {str(error) or '<no message>'}"
    )


def _short_user_message(message: str) -> str:
    first_line = message.strip().splitlines()[0] if message.strip() else ""
    return first_line or _tr("The conversion failed.")


def _looks_locked(text: str) -> bool:
    return any(
        fragment in text
        for fragment in (
            "being used",
            "permission denied",
            "access is denied",
            "cannot access the file",
            "used by another program",
            "winerror 32",
            "winerror 5",
        )
    )


def _looks_password_pdf(text: str) -> bool:
    return "password" in text or "needs pass" in text or "encrypted" in text


def _looks_image_error(text: str) -> bool:
    return any(
        fragment in text
        for fragment in (
            "image",
            "cannot identify image",
            "truncated",
        )
    )


def _looks_office_dependency_missing(text: str) -> bool:
    dependency_name = "libreoffice" in text or "microsoft office" in text
    return dependency_name and any(
        fragment in text
        for fragment in (
            "not found",
            "missing",
            "required",
            "unavailable",
        )
    )
