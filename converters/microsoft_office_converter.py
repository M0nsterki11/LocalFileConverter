from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import gc
import logging
import os
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from app.constants import OFFICE_EXTENSIONS
from app.exceptions import ConversionError, DependencyNotFoundError
from app.i18n import translate
from converters.base_converter import (
    CancelCheck,
    ConversionCancelledError,
    check_cancelled,
)
from utils.file_utils import generate_unique_output_path
from utils.input_validation import validate_input_file_for_conversion
from utils.logging_utils import LOGGER_NAME
from utils.output_safety import (
    cleanup_temporary_path,
    ensure_output_directory_ready,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    publish_temporary_file,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]

_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_PROCESS_TERMINATE = 0x0001
_SYNCHRONIZE = 0x00100000
_OFFICE_EXIT_TIMEOUT_MS = 5_000


@dataclass(frozen=True)
class MicrosoftOfficeApplication:
    key: str
    display_name: str
    prog_id: str


MICROSOFT_OFFICE_APPLICATIONS = {
    ".docx": MicrosoftOfficeApplication(
        key="word",
        display_name="Microsoft Word",
        prog_id="Word.Application",
    ),
    ".pptx": MicrosoftOfficeApplication(
        key="powerpoint",
        display_name="Microsoft PowerPoint",
        prog_id="PowerPoint.Application",
    ),
    ".xlsx": MicrosoftOfficeApplication(
        key="excel",
        display_name="Microsoft Excel",
        prog_id="Excel.Application",
    ),
}


class MicrosoftOfficeConversionError(ConversionError):
    """A Microsoft Office desktop application could not convert a document."""


def get_microsoft_office_application(
    extension: str,
) -> MicrosoftOfficeApplication | None:
    return MICROSOFT_OFFICE_APPLICATIONS.get(extension.lower())


def is_microsoft_office_available(extension: str) -> bool:
    """Return whether the matching desktop Office COM server can be launched."""
    office_application = get_microsoft_office_application(extension)

    if office_application is None or os.name != "nt":
        return False

    logger = logging.getLogger(LOGGER_NAME)
    application = None
    process_id: int | None = None

    try:
        with _initialized_com() as client:
            try:
                application = client.DispatchEx(office_application.prog_id)
                process_id = _get_application_process_id(application)
                getattr(application, "Name", None)
                return True
            except Exception as error:
                logger.debug(
                    "%s COM availability check failed: %s",
                    office_application.display_name,
                    error,
                )
                return False
            finally:
                _quit_application(application, office_application)
                application = None
                gc.collect()
                _ensure_owned_process_exited(process_id)
    except DependencyNotFoundError as error:
        logger.debug("Microsoft Office COM support is unavailable: %s", error)
        return False


def convert_with_microsoft_office(
    input_file: str | Path,
    output_directory: str | Path,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    input_path = validate_input_file_for_conversion(input_file)
    office_application = get_microsoft_office_application(
        input_path.suffix.lower()
    )

    if office_application is None:
        raise MicrosoftOfficeConversionError(
            "Unsupported Microsoft Office conversion input: "
            f"{input_path.suffix.lower()}",
            user_message=_tr(
                "Only DOCX, PPTX, and XLSX documents are supported."
            ),
        )

    if input_path.suffix.lower() not in OFFICE_EXTENSIONS:
        raise MicrosoftOfficeConversionError(
            f"Unsupported Microsoft Office input: {input_path.suffix.lower()}"
        )

    output_path = ensure_output_directory_ready(output_directory)
    ensure_sufficient_disk_space(
        output_path,
        estimate_required_space_bytes(
            input_path,
            operation="office_to_pdf",
        ),
    )
    result_path = generate_unique_output_path(
        input_file=input_path,
        output_directory=output_path,
        output_extension=".pdf",
    )
    temporary_result_path = result_path.parent / (
        f".{result_path.stem}.{uuid4().hex}.part.pdf"
    )

    check_cancelled(cancel_check)
    _emit_status(
        status_callback,
        _tr("Preparing {app_name} conversion...").format(
            app_name=office_application.display_name,
        ),
    )
    _emit_progress(progress_callback, 10)

    application = None
    document = None
    process_id: int | None = None

    try:
        with _initialized_com() as client:
            try:
                application = client.DispatchEx(office_application.prog_id)
                process_id = _get_application_process_id(application)
                _configure_application(application)

                check_cancelled(cancel_check)
                _emit_status(
                    status_callback,
                    _tr("Converting file {file_name} with {app_name}...").format(
                        file_name=input_path.name,
                        app_name=office_application.display_name,
                    ),
                )
                _emit_progress(progress_callback, 30)

                document = _open_document(
                    application,
                    office_application,
                    input_path,
                )
                _export_document_to_pdf(
                    document,
                    office_application,
                    temporary_result_path,
                )
                _emit_progress(progress_callback, 85)
                check_cancelled(cancel_check)
            finally:
                _close_document(document, office_application)
                document = None
                _quit_application(application, office_application)
                application = None
                gc.collect()
                _ensure_owned_process_exited(process_id)
    except (DependencyNotFoundError, ConversionCancelledError):
        cleanup_temporary_path(temporary_result_path)
        raise
    except Exception as error:
        cleanup_temporary_path(temporary_result_path)
        raise MicrosoftOfficeConversionError(
            f"{office_application.display_name} COM conversion failed: {error}",
            user_message=_tr(
                "{app_name} could not convert the document."
            ).format(app_name=office_application.display_name),
            suggestion=_tr(
                "Open the document in its Office application to check it, "
                "or use LibreOffice as a fallback."
            ),
        ) from error

    if (
        not temporary_result_path.exists()
        or temporary_result_path.stat().st_size <= 0
    ):
        cleanup_temporary_path(temporary_result_path)
        raise MicrosoftOfficeConversionError(
            f"{office_application.display_name} did not create a PDF result.",
            user_message=_tr(
                "{app_name} did not create a PDF result."
            ).format(app_name=office_application.display_name),
        )

    try:
        check_cancelled(cancel_check)
    except ConversionCancelledError:
        cleanup_temporary_path(temporary_result_path)
        raise
    _emit_status(
        status_callback,
        _tr("Saving file {file_name}...").format(file_name=result_path.name),
    )
    _emit_progress(progress_callback, 90)

    try:
        result_path = publish_temporary_file(
            temporary_result_path,
            result_path,
        )
    except Exception:
        cleanup_temporary_path(temporary_result_path)
        raise

    _emit_progress(progress_callback, 100)
    _emit_status(
        status_callback,
        _tr("The Office document was converted to PDF successfully."),
    )
    return result_path


@contextmanager
def _initialized_com() -> Iterator[Any]:
    try:
        import pythoncom
        import win32com.client
    except ImportError as error:
        raise DependencyNotFoundError(
            f"pywin32 COM support is unavailable: {error}",
            user_message=_tr(
                "Microsoft Office automation is not available in this build."
            ),
        ) from error

    pythoncom.CoInitialize()

    try:
        yield win32com.client
    finally:
        pythoncom.CoUninitialize()


def _configure_application(application: Any) -> None:
    if application is None:
        return

    try:
        application.Visible = False
    except Exception:
        pass

    try:
        application.DisplayAlerts = False
    except Exception:
        pass


def _open_document(
    application: Any,
    office_application: MicrosoftOfficeApplication,
    input_path: Path,
) -> Any:
    input_name = str(input_path.resolve())

    if office_application.key == "word":
        return application.Documents.Open(
            input_name,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )

    if office_application.key == "powerpoint":
        return application.Presentations.Open(
            input_name,
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )

    return application.Workbooks.Open(
        input_name,
        UpdateLinks=0,
        ReadOnly=True,
        IgnoreReadOnlyRecommended=True,
        AddToMru=False,
    )


def _export_document_to_pdf(
    document: Any,
    office_application: MicrosoftOfficeApplication,
    output_path: Path,
) -> None:
    output_name = str(output_path.resolve())

    if office_application.key == "word":
        document.ExportAsFixedFormat(
            OutputFileName=output_name,
            ExportFormat=17,
            OpenAfterExport=False,
        )
        return

    if office_application.key == "powerpoint":
        document.SaveAs(output_name, 32)
        return

    document.ExportAsFixedFormat(
        Type=0,
        Filename=output_name,
        Quality=0,
        IncludeDocProperties=True,
        IgnorePrintAreas=False,
        OpenAfterPublish=False,
    )


def _close_document(
    document: Any,
    office_application: MicrosoftOfficeApplication,
) -> None:
    if document is None:
        return

    try:
        if office_application.key == "word":
            document.Close(SaveChanges=0)
        elif office_application.key == "excel":
            document.Close(SaveChanges=False)
        else:
            document.Close()
    except Exception as error:
        logging.getLogger(LOGGER_NAME).warning(
            "Could not close the %s COM document cleanly: %s",
            office_application.display_name,
            error,
        )


def _quit_application(
    application: Any,
    office_application: MicrosoftOfficeApplication,
) -> None:
    if application is None:
        return

    try:
        if office_application.key == "word":
            application.Quit(SaveChanges=0)
        else:
            application.Quit()
    except Exception as error:
        logging.getLogger(LOGGER_NAME).warning(
            "Could not quit the owned %s COM process cleanly: %s",
            office_application.display_name,
            error,
        )


def _get_application_process_id(application: Any) -> int | None:
    if application is None or os.name != "nt":
        return None

    window_handle = None

    for attribute_name in ("Hwnd", "HWND"):
        try:
            window_handle = int(getattr(application, attribute_name))
        except Exception:
            continue

        if window_handle:
            break

    if not window_handle:
        return None

    process_id = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(
        wintypes.HWND(window_handle),
        ctypes.byref(process_id),
    )
    return int(process_id.value) or None


def _ensure_owned_process_exited(process_id: int | None) -> None:
    if process_id is None or os.name != "nt":
        return

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
        )
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.TerminateProcess.argtypes = (
            wintypes.HANDLE,
            wintypes.UINT,
        )
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

        process_handle = kernel32.OpenProcess(
            _SYNCHRONIZE | _PROCESS_TERMINATE,
            False,
            process_id,
        )

        if not process_handle:
            return

        try:
            wait_result = kernel32.WaitForSingleObject(
                process_handle,
                _OFFICE_EXIT_TIMEOUT_MS,
            )

            if wait_result == _WAIT_TIMEOUT:
                logging.getLogger(LOGGER_NAME).warning(
                    "Owned Microsoft Office process PID %d did not exit after "
                    "Quit; terminating it to prevent an orphan process.",
                    process_id,
                )
                kernel32.TerminateProcess(process_handle, 1)
                kernel32.WaitForSingleObject(process_handle, 2_000)
            elif wait_result != _WAIT_OBJECT_0:
                logging.getLogger(LOGGER_NAME).warning(
                    "Could not verify exit of owned Microsoft Office process "
                    "PID %d.",
                    process_id,
                )
        finally:
            kernel32.CloseHandle(process_handle)
    except Exception as error:
        logging.getLogger(LOGGER_NAME).warning(
            "Could not enforce cleanup of owned Microsoft Office process "
            "PID %d: %s",
            process_id,
            error,
        )


def _emit_progress(callback: ProgressCallback | None, value: int) -> None:
    if callback is not None:
        callback(value)


def _emit_status(callback: StatusCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _tr(source_text: str) -> str:
    return translate("MicrosoftOfficeConverter", source_text)
