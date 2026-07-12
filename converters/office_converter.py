import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from app.constants import OFFICE_EXTENSIONS
from app.exceptions import ConversionError, DependencyNotFoundError
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
    """Greška nastala tijekom LibreOffice konverzije."""


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
    Pretvara DOCX, PPTX ili XLSX u PDF pomoću LibreOfficea.

    Svaka konverzija koristi zaseban privremeni LibreOffice profil.
    Originalna datoteka ostaje netaknuta.
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
            f"Nije moguće stvoriti izlaznu mapu:\n{error}"
        ) from error

    check_cancelled(cancel_check)

    _emit_status(
        status_callback,
        "Priprema LibreOffice konverzije...",
    )
    _emit_progress(progress_callback, 10)

    with (
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
            f"Pretvaranje datoteke {input_path.name} u PDF...",
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
            "Provjera LibreOffice rezultata...",
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
            f"Spremanje datoteke {result_path.name}...",
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
                f"Nije moguće spremiti PDF rezultat:\n{error}"
            ) from error
        except Exception:
            cleanup_temporary_path(temporary_result_path)
            raise

    if not result_path.exists():
        raise OfficeConversionError(
            "LibreOffice je završio konverziju, "
            "ali PDF rezultat nije pronađen."
        )

    _emit_progress(progress_callback, 100)
    _emit_status(
        status_callback,
        "Office dokument uspješno je pretvoren u PDF.",
    )

    return result_path


def _validate_conversion_input(
    input_path: Path,
    soffice_path: Path,
) -> None:
    validate_input_file_for_conversion(input_path)

    if not input_path.exists() or not input_path.is_file():
        raise OfficeConversionError(
            "Odabrani Office dokument ne postoji."
        )

    if input_path.suffix.lower() not in OFFICE_EXTENSIONS:
        raise OfficeConversionError(
            "Podržani su samo DOCX, PPTX i XLSX dokumenti."
        )

    if not is_valid_libreoffice_executable(soffice_path):
        raise DependencyNotFoundError(
            "LibreOffice nije pronađen. "
            "Odaberi valjanu soffice.exe datoteku."
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
            "LibreOffice izvršna datoteka nije pronađena."
        ) from error

    except PermissionError as error:
        raise OfficeConversionError(
            "Windows nije dopustio pokretanje LibreOfficea."
        ) from error

    except OSError as error:
        raise OfficeConversionError(
            f"LibreOffice se nije mogao pokrenuti:\n{error}"
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
                "Konverziju je prekinuo korisnik."
            )

        elapsed_seconds = time.monotonic() - started_at

        if elapsed_seconds > OFFICE_CONVERSION_TIMEOUT_SECONDS:
            _stop_process(process)

            raise OfficeConversionError(
                "LibreOffice konverzija predugo traje "
                "i automatski je prekinuta."
            )

        time.sleep(0.1)

    stdout, stderr = process.communicate()

    return stdout or "", stderr or ""


def _stop_process(
    process: subprocess.Popen[str],
) -> None:
    """
    Zaustavlja LibreOffice i njegove pomoćne procese.

    Na Windowsu taskkill /T zaustavlja cijelo stablo procesa,
    uključujući soffice.bin koji može držati privremene datoteke.
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

        # Windowsu dajemo trenutak da otpusti zaključane datoteke.
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
        "LibreOffice nije uspio pretvoriti dokument. "
        f"Završni kod: {return_code}."
    )

    if details:
        message += f"\n\nDetalji:\n{details}"

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
        "LibreOffice nije stvorio PDF rezultat. "
        "Dokument može biti oštećen, zaključan ili nepodržan."
    )

    if details:
        message += f"\n\nDetalji:\n{details}"

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
