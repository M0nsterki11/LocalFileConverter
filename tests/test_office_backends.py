from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import pytest

import app.conversion_execution as conversion_execution
import converters.microsoft_office_converter as microsoft_converter
from app.exceptions import DependencyNotFoundError
from app.conversion_execution import run_conversion
from utils.error_handler import exception_to_error_info


def _write_input(path: Path) -> Path:
    path.write_bytes(b"test document")
    return path


def _write_result(output_directory: str | Path, name: str) -> Path:
    result_path = Path(output_directory) / name
    result_path.write_bytes(b"%PDF-test")
    return result_path


@pytest.mark.parametrize(
    ("extension", "expected_app_name"),
    [
        (".docx", "Microsoft Word"),
        (".pptx", "Microsoft PowerPoint"),
        (".xlsx", "Microsoft Excel"),
    ],
)
def test_matching_microsoft_office_app_is_selected_without_libreoffice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extension: str,
    expected_app_name: str,
) -> None:
    input_path = _write_input(tmp_path / f"input{extension}")
    calls: list[str] = []

    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda candidate: candidate == extension,
    )

    def fake_microsoft_conversion(**kwargs) -> Path:
        application = microsoft_converter.get_microsoft_office_application(
            Path(kwargs["input_file"]).suffix
        )
        assert application is not None
        calls.append(application.display_name)
        return _write_result(kwargs["output_directory"], "result.pdf")

    monkeypatch.setattr(
        conversion_execution,
        "convert_with_microsoft_office",
        fake_microsoft_conversion,
    )
    monkeypatch.setattr(
        conversion_execution,
        "convert_office_to_pdf",
        lambda **_kwargs: pytest.fail("LibreOffice should not be selected"),
    )

    result = run_conversion(input_path, tmp_path, "PDF")

    assert result.name == "result.pdf"
    assert calls == [expected_app_name]


def test_libreoffice_is_selected_when_microsoft_office_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_input(tmp_path / "input.docx")
    soffice_path = _write_input(tmp_path / "soffice.exe")
    calls: list[str] = []

    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda _extension: False,
    )

    def fake_libreoffice_conversion(**kwargs) -> Path:
        calls.append(str(kwargs["libreoffice_executable"]))
        return _write_result(kwargs["output_directory"], "fallback.pdf")

    monkeypatch.setattr(
        conversion_execution,
        "convert_office_to_pdf",
        fake_libreoffice_conversion,
    )

    result = run_conversion(
        input_path,
        tmp_path,
        "PDF",
        libreoffice_path=soffice_path,
    )

    assert result.name == "fallback.pdf"
    assert calls == [str(soffice_path)]


def test_microsoft_office_is_preferred_when_both_backends_are_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_input(tmp_path / "input.pptx")
    soffice_path = _write_input(tmp_path / "soffice.exe")

    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda _extension: True,
    )
    monkeypatch.setattr(
        conversion_execution,
        "convert_with_microsoft_office",
        lambda **kwargs: _write_result(
            kwargs["output_directory"],
            "powerpoint.pdf",
        ),
    )
    monkeypatch.setattr(
        conversion_execution,
        "convert_office_to_pdf",
        lambda **_kwargs: pytest.fail("LibreOffice should not be preferred"),
    )

    result = run_conversion(
        input_path,
        tmp_path,
        "PDF",
        libreoffice_path=soffice_path,
    )

    assert result.name == "powerpoint.pdf"


def test_libreoffice_fallback_runs_after_microsoft_office_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_input(tmp_path / "input.xlsx")
    soffice_path = _write_input(tmp_path / "soffice.exe")
    calls: list[str] = []
    statuses: list[str] = []

    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda _extension: True,
    )

    def fail_microsoft_conversion(**_kwargs) -> Path:
        calls.append("microsoft")
        raise RuntimeError("Excel COM export failed")

    def fake_libreoffice_conversion(**kwargs) -> Path:
        calls.append("libreoffice")
        return _write_result(kwargs["output_directory"], "fallback.pdf")

    monkeypatch.setattr(
        conversion_execution,
        "convert_with_microsoft_office",
        fail_microsoft_conversion,
    )
    monkeypatch.setattr(
        conversion_execution,
        "convert_office_to_pdf",
        fake_libreoffice_conversion,
    )

    result = run_conversion(
        input_path,
        tmp_path,
        "PDF",
        libreoffice_path=soffice_path,
        status_callback=statuses.append,
    )

    assert result.name == "fallback.pdf"
    assert calls == ["microsoft", "libreoffice"]
    assert "Trying LibreOffice" in statuses[-1]


def test_neither_backend_available_returns_clear_dependency_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_input(tmp_path / "input.docx")
    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda _extension: False,
    )

    with pytest.raises(DependencyNotFoundError) as error_info:
        run_conversion(input_path, tmp_path, "PDF")

    display_error = exception_to_error_info(error_info.value)
    assert display_error.message == (
        "Microsoft Office or LibreOffice is required for this conversion."
    )
    assert "soffice.exe" in display_error.suggestion


@pytest.mark.parametrize("export_fails", [False, True])
def test_com_document_and_owned_process_are_cleaned_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    export_fails: bool,
) -> None:
    input_path = _write_input(tmp_path / "input.docx")
    events: list[str] = []

    class FakeDocument:
        def ExportAsFixedFormat(self, **kwargs) -> None:
            events.append("export")

            if export_fails:
                raise RuntimeError("export failed")

            Path(kwargs["OutputFileName"]).write_bytes(b"%PDF-test")

        def Close(self, **_kwargs) -> None:
            events.append("close")

    class FakeDocuments:
        def Open(self, *_args, **_kwargs) -> FakeDocument:
            events.append("open")
            return FakeDocument()

    class FakeApplication:
        Documents = FakeDocuments()

        def Quit(self, **_kwargs) -> None:
            events.append("quit")

    pythoncom_module = ModuleType("pythoncom")
    pythoncom_module.CoInitialize = lambda: events.append("coinitialize")
    pythoncom_module.CoUninitialize = lambda: events.append("couninitialize")
    client_module = ModuleType("win32com.client")
    client_module.DispatchEx = lambda prog_id: (
        events.append(prog_id) or FakeApplication()
    )
    win32com_module = ModuleType("win32com")
    win32com_module.client = client_module

    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom_module)
    monkeypatch.setitem(sys.modules, "win32com", win32com_module)
    monkeypatch.setitem(sys.modules, "win32com.client", client_module)
    monkeypatch.setattr(
        microsoft_converter,
        "_get_application_process_id",
        lambda _application: 4242,
    )
    monkeypatch.setattr(
        microsoft_converter,
        "_ensure_owned_process_exited",
        lambda process_id: events.append(f"process-exit:{process_id}"),
    )

    if export_fails:
        with pytest.raises(microsoft_converter.MicrosoftOfficeConversionError):
            microsoft_converter.convert_with_microsoft_office(
                input_path,
                tmp_path,
            )
    else:
        result = microsoft_converter.convert_with_microsoft_office(
            input_path,
            tmp_path,
        )
        assert result.exists()

    assert events.count("coinitialize") == 1
    assert events.count("couninitialize") == 1
    assert events.count("close") == 1
    assert events.count("quit") == 1
    assert events.count("process-exit:4242") == 1


def test_image_conversion_does_not_probe_office_backends(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _write_input(tmp_path / "input.jpg")

    monkeypatch.setattr(
        conversion_execution,
        "is_microsoft_office_available",
        lambda _extension: pytest.fail("Office detection should not run"),
    )
    monkeypatch.setattr(
        conversion_execution,
        "convert_image",
        lambda **kwargs: _write_result(
            kwargs["output_directory"],
            "image.png",
        ),
    )

    result = run_conversion(input_path, tmp_path, "PNG")

    assert result.name == "image.png"


def test_powerpoint_pdf_export_uses_save_as_pdf_format(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, int]] = []

    class FakePresentation:
        def SaveAs(self, output_name: str, output_format: int) -> None:
            calls.append((output_name, output_format))

    application = microsoft_converter.get_microsoft_office_application(
        ".pptx"
    )
    assert application is not None
    output_path = tmp_path / "slides.pdf"

    microsoft_converter._export_document_to_pdf(
        FakePresentation(),
        application,
        output_path,
    )

    assert calls == [(str(output_path.resolve()), 32)]
