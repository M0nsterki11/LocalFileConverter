"""Convert Office documents to PDF through headless LibreOffice."""

import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from app.constants import OFFICE_EXTENSIONS
from app.exceptions import ConversionError, DependencyNotFoundError
from app.i18n import translate
from converters.base_converter import (
    CancelCheck,
    ConversionCancelledError,
    check_cancelled,
)
from utils.input_validation import validate_input_file_for_conversion
from utils.file_utils import generate_unique_output_path
from utils.libreoffice_utils import (
    is_valid_libreoffice_executable,
)
from utils.output_safety import (
    cleanup_temporary_path,
    ensure_output_directory_ready,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    get_temporary_output_path,
    publish_temporary_file,
)


ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[str], None]


class OfficeConversionError(ConversionError):
    """Error raised during LibreOffice conversion."""


OFFICE_CONVERSION_TIMEOUT_SECONDS = 15 * 60


def convert_office_to_pdf(
    input_file: str | Path,
    output_directory: str | Path,
    libreoffice_executable: str | Path,
    cancel_check: CancelCheck | None = None,
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> Path:
    """
    Convert DOCX, PPTX, or XLSX to PDF with LibreOffice.

    Every conversion uses a separate temporary LibreOffice profile.
    The original file remains untouched.
    """
    input_path = Path(input_file)
    output_path = ensure_output_directory_ready(output_directory)
    ensure_sufficient_disk_space(
        output_path,
        estimate_required_space_bytes(
            input_path,
            operation="office_to_pdf",
        ),
    )
    soffice_path = Path(libreoffice_executable)

    _validate_conversion_input(
        input_path=input_path,
        soffice_path=soffice_path,
    )

    try:
        output_path.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as error:
        raise OfficeConversionError(
            _tr("Could not create the output folder:\n{error}").format(
                error=error,
            )
        ) from error

    check_cancelled(cancel_check)

    _emit_status(
        status_callback,
        _tr("Preparing LibreOffice conversion..."),
    )
    _emit_progress(progress_callback, 10)

    with (
        # A private profile isolates this process from an already-running
        # LibreOffice instance and avoids profile lock/contention dialogs.
        TemporaryDirectory(
            prefix="lfc_office_output_",
            ignore_cleanup_errors=True,
        ) as temporary_output_directory,
        TemporaryDirectory(
            prefix="lfc_libreoffice_profile_",
            ignore_cleanup_errors=True,
        ) as temporary_profile_directory,
    ):
        temporary_output_path = Path(
            temporary_output_directory
        )
        temporary_profile_path = Path(
            temporary_profile_directory
        )

        command = _build_libreoffice_command(
            soffice_path=soffice_path,
            input_path=input_path,
            temporary_output_path=temporary_output_path,
            temporary_profile_path=temporary_profile_path,
        )

        _emit_status(
            status_callback,
            _tr("Converting file {file_name} to PDF...").format(
                file_name=input_path.name,
            ),
        )
        _emit_progress(progress_callback, 30)

        process = _start_libreoffice_process(command)

        try:
            stdout, stderr = _wait_for_process(
                process=process,
                cancel_check=cancel_check,
            )

        except ConversionCancelledError:
            _stop_process(process)
            raise

        check_cancelled(cancel_check)

        _emit_progress(progress_callback, 80)
        _emit_status(
            status_callback,
            _tr("Checking LibreOffice result..."),
        )

        if process.returncode != 0:
            raise OfficeConversionError(
                _build_process_error_message(
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            )

        generated_pdf = _find_generated_pdf(
            temporary_output_path=temporary_output_path,
            input_path=input_path,
        )

        if generated_pdf is None:
            raise OfficeConversionError(
                _build_missing_result_message(
                    stdout=stdout,
                    stderr=stderr,
                )
            )

        check_cancelled(cancel_check)

        result_path = generate_unique_output_path(
            input_file=input_path,
            output_directory=output_path,
            output_extension=".pdf",
        )
        temporary_result_path = get_temporary_output_path(result_path)

        _emit_status(
            status_callback,
            _tr("Saving file {file_name}...").format(
                file_name=result_path.name,
            ),
        )
        _emit_progress(progress_callback, 90)

        try:
            shutil.move(
                str(generated_pdf),
                str(temporary_result_path),
            )
            result_path = publish_temporary_file(
                temporary_result_path,
                result_path,
            )
        except OSError as error:
            cleanup_temporary_path(temporary_result_path)
            raise OfficeConversionError(
                _tr("Could not save the PDF result:\n{error}").format(
                    error=error,
                )
            ) from error
        except Exception:
            cleanup_temporary_path(temporary_result_path)
            raise

    if not result_path.exists():
        raise OfficeConversionError(
            _tr(
                "LibreOffice finished the conversion, but the PDF result was not found."
            )
        )

    _emit_progress(progress_callback, 100)
    _emit_status(
        status_callback,
        _tr("The Office document was converted to PDF successfully."),
    )

    return result_path


def _validate_conversion_input(
    input_path: Path,
    soffice_path: Path,
) -> None:
    validate_input_file_for_conversion(input_path)

    if not input_path.exists() or not input_path.is_file():
        raise OfficeConversionError(
            _tr("The selected Office document does not exist.")
        )

    if input_path.suffix.lower() not in OFFICE_EXTENSIONS:
        raise OfficeConversionError(
            _tr("Only DOCX, PPTX, and XLSX documents are supported.")
        )

    if not is_valid_libreoffice_executable(soffice_path):
        raise DependencyNotFoundError(
            _tr(
                "LibreOffice was not found. Choose a valid soffice.exe file."
            )
        )


def _build_libreoffice_command(
    soffice_path: Path,
    input_path: Path,
    temporary_output_path: Path,
    temporary_profile_path: Path,
) -> list[str]:
    profile_uri = temporary_profile_path.resolve().as_uri()

    return [
        str(soffice_path),
        f"-env:UserInstallation={profile_uri}",
        "--headless",
        "--nologo",
        "--nodefault",
        "--norestore",
        "--convert-to",
        "pdf",
        "--outdir",
        str(temporary_output_path),
        str(input_path),
    ]


def _start_libreoffice_process(
    command: list[str],
) -> subprocess.Popen[str]:
    creation_flags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    try:
        return subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

    except FileNotFoundError as error:
        raise OfficeConversionError(
            _tr("The LibreOffice executable was not found.")
        ) from error

    except PermissionError as error:
        raise OfficeConversionError(
            _tr("Windows denied permission to start LibreOffice.")
        ) from error

    except OSError as error:
        raise OfficeConversionError(
            _tr("LibreOffice could not be started:\n{error}").format(
                error=error,
            )
        ) from error


def _wait_for_process(
    process: subprocess.Popen[str],
    cancel_check: CancelCheck | None,
) -> tuple[str, str]:
    started_at = time.monotonic()

    while process.poll() is None:
        if cancel_check is not None and cancel_check():
            _stop_process(process)

            raise ConversionCancelledError(
                _tr("The conversion was cancelled by the user.")
            )

        elapsed_seconds = time.monotonic() - started_at

        if elapsed_seconds > OFFICE_CONVERSION_TIMEOUT_SECONDS:
            _stop_process(process)

            raise OfficeConversionError(
                _tr(
                    "LibreOffice conversion took too long and was cancelled automatically."
                )
            )

        time.sleep(0.1)

    stdout, stderr = process.communicate()

    return stdout or "", stderr or ""


def _stop_process(
    process: subprocess.Popen[str],
) -> None:
    """
    Stop LibreOffice and its helper processes.

    On Windows, taskkill /T stops the whole process tree, including
    soffice.bin, which can keep temporary files locked.
    """
    if process.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0,
                ),
            )
        except OSError:
            pass

        try:
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            pass

        # Give Windows a moment to release locked files.
        time.sleep(0.3)
        return

    try:
        process.terminate()
        process.wait(timeout=3)

    except (subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
            process.wait(timeout=3)
        except (subprocess.TimeoutExpired, OSError):
            pass


def _find_generated_pdf(
    temporary_output_path: Path,
    input_path: Path,
) -> Path | None:
    expected_path = (
        temporary_output_path
        / f"{input_path.stem}.pdf"
    )

    if expected_path.exists() and expected_path.is_file():
        return expected_path

    pdf_files = list(
        temporary_output_path.glob("*.pdf")
    )

    if len(pdf_files) == 1:
        return pdf_files[0]

    return None


def _build_process_error_message(
    return_code: int,
    stdout: str,
    stderr: str,
) -> str:
    details = _get_process_details(
        stdout=stdout,
        stderr=stderr,
    )

    message = (
        _tr(
            "LibreOffice could not convert the document. Exit code: {return_code}."
        ).format(return_code=return_code)
    )

    if details:
        message += _tr("\n\nDetails:\n{details}").format(details=details)

    return message


def _build_missing_result_message(
    stdout: str,
    stderr: str,
) -> str:
    details = _get_process_details(
        stdout=stdout,
        stderr=stderr,
    )

    message = (
        _tr(
            "LibreOffice did not create a PDF result. The document may be corrupted, locked, or unsupported."
        )
    )

    if details:
        message += _tr("\n\nDetails:\n{details}").format(details=details)

    return message


def _get_process_details(
    stdout: str,
    stderr: str,
) -> str:
    combined_output = "\n".join(
        part.strip()
        for part in (stdout, stderr)
        if part.strip()
    )

    if not combined_output:
        return ""

    return combined_output[-1500:]


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


def _tr(source_text: str) -> str:
    return translate("OfficeConverter", source_text)
