from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from zipfile import ZipFile

import pytest
import pymupdf
from PIL import Image

from app.batch_worker import BatchConversionWorker
from app.conversion_item import ConversionItem, ConversionStatus
from app.exceptions import (
    CorruptedFileError,
    InsufficientDiskSpaceError,
    UnsupportedFormatError,
)
from utils.error_handler import exception_to_error_info
from utils.input_validation import (
    validate_image_file,
    validate_input_file_for_queue,
    validate_pdf_file,
)
from utils.logging_utils import (
    LOGGER_NAME,
    LOG_FILE_NAME,
    cleanup_old_lfc_temp_files,
    sanitize_path,
    setup_logging,
)
from utils.output_safety import (
    cleanup_temporary_path,
    ensure_sufficient_disk_space,
    estimate_required_space_bytes,
    human_readable_size,
    publish_temporary_directory,
    publish_temporary_file,
    validate_zip_file,
)


@pytest.fixture
def isolated_logger():
    logger = logging.getLogger(LOGGER_NAME)
    old_handlers = list(logger.handlers)

    for handler in old_handlers:
        logger.removeHandler(handler)

    yield logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    for handler in old_handlers:
        logger.addHandler(handler)


def _flush_logger(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def test_logging_creates_directory_and_writes_once(
    tmp_path: Path,
    isolated_logger: logging.Logger,
) -> None:
    logger = setup_logging(log_directory=tmp_path)
    setup_logging(log_directory=tmp_path)

    file_handlers = [
        handler
        for handler in logger.handlers
        if handler.__class__.__name__ == "RotatingFileHandler"
    ]

    assert len(file_handlers) == 1

    logger.info("hello log")
    _flush_logger(logger)

    assert (tmp_path / LOG_FILE_NAME).read_text(
        encoding="utf-8"
    ).count("hello log") == 1


def test_logging_fallback_does_not_crash_on_bad_directory(
    tmp_path: Path,
    isolated_logger: logging.Logger,
) -> None:
    bad_directory = tmp_path / "not-a-directory"
    bad_directory.write_text("x", encoding="utf-8")

    logger = setup_logging(log_directory=bad_directory)

    logger.warning("still alive")


def test_sanitize_home_path() -> None:
    path = Path.home() / "Documents" / "secret.pdf"

    assert sanitize_path(path).startswith("~")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FileNotFoundError("missing"), "no longer exists"),
        (PermissionError("denied"), "Windows denied access"),
        (UnsupportedFormatError("bad"), "format is not supported"),
        (CorruptedFileError("Image is corrupted"), "image is corrupted"),
        (CorruptedFileError("PDF is password-protected"), "password"),
        (
            InsufficientDiskSpaceError("disk"),
            "not have enough free space",
        ),
        (RuntimeError("boom"), "unexpected error"),
    ],
)
def test_error_mapping(error: Exception, expected: str) -> None:
    info = exception_to_error_info(error)

    assert expected.casefold() in info.message.casefold()
    assert error.__class__.__name__ in info.technical_detail


def test_publish_temporary_file_does_not_overwrite_existing(
    tmp_path: Path,
) -> None:
    final_path = tmp_path / "result.txt"
    final_path.write_text("old", encoding="utf-8")
    temporary_path = tmp_path / ".result.txt.part"
    temporary_path.write_text("new", encoding="utf-8")

    published_path = publish_temporary_file(
        temporary_path,
        final_path,
    )

    assert final_path.read_text(encoding="utf-8") == "old"
    assert published_path.name == "result_1.txt"
    assert published_path.read_text(encoding="utf-8") == "new"


def test_cleanup_temporary_path_removes_part_file(
    tmp_path: Path,
) -> None:
    temporary_path = tmp_path / "broken.part"
    temporary_path.write_text("partial", encoding="utf-8")

    cleanup_temporary_path(temporary_path)

    assert not temporary_path.exists()


def test_zip_validation_and_directory_publish(tmp_path: Path) -> None:
    zip_path = tmp_path / "ok.zip"

    with ZipFile(zip_path, "w") as archive:
        archive.writestr("file.txt", "ok")

    validate_zip_file(zip_path)

    temporary_directory = tmp_path / "lfc_result"
    temporary_directory.mkdir()
    (temporary_directory / "page.png").write_bytes(b"png")

    published_directory = publish_temporary_directory(
        temporary_directory,
        tmp_path / "pages",
    )

    assert (published_directory / "page.png").exists()


def test_disk_space_check_and_human_readable_size(tmp_path: Path) -> None:
    assert human_readable_size(1024) == "1.0 KB"
    assert (
        estimate_required_space_bytes(
            tmp_path / "missing.pdf",
            operation="pdf_to_images",
            dpi=300,
            page_count=2,
        )
        > 0
    )

    ensure_sufficient_disk_space(
        tmp_path,
        10,
        reserve_bytes=0,
        usage_provider=lambda path: (100, 50, 50),
    )

    with pytest.raises(InsufficientDiskSpaceError):
        ensure_sufficient_disk_space(
            tmp_path,
            20,
            reserve_bytes=0,
            usage_provider=lambda path: (100, 90, 10),
        )


def test_input_validation_rejects_invalid_files(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        validate_input_file_for_queue(tmp_path / "missing.jpg")

    with pytest.raises(Exception):
        validate_input_file_for_queue(tmp_path)

    empty_file = tmp_path / "empty.jpg"
    empty_file.write_bytes(b"")

    with pytest.raises(Exception):
        validate_input_file_for_queue(empty_file)

    unsupported_file = tmp_path / "file.txt"
    unsupported_file.write_text("x", encoding="utf-8")

    with pytest.raises(Exception):
        validate_input_file_for_queue(unsupported_file)


def test_corrupted_image_and_pdf_are_rejected(tmp_path: Path) -> None:
    bad_image = tmp_path / "bad.png"
    bad_image.write_bytes(b"not an image")
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a pdf")

    with pytest.raises(CorruptedFileError):
        validate_image_file(bad_image)

    with pytest.raises(CorruptedFileError):
        validate_pdf_file(bad_pdf)


def test_batch_failure_logs_traceback_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_logger: logging.Logger,
) -> None:
    logger = setup_logging(log_directory=tmp_path / "logs")
    bad_item = ConversionItem(
        input_path=tmp_path / "bad.jpg",
        input_format="JPG",
        output_format="PNG",
        output_directory=tmp_path,
    )
    good_item = ConversionItem(
        input_path=tmp_path / "good.jpg",
        input_format="JPG",
        output_format="PNG",
        output_directory=tmp_path,
    )

    def fake_run_conversion(**kwargs):
        input_file = Path(kwargs["input_file"])

        if input_file.name == "bad.jpg":
            raise ValueError("broken file")

        result_path = tmp_path / "good.png"
        result_path.write_bytes(b"ok")
        return result_path

    monkeypatch.setattr(
        "app.batch_worker.run_conversion",
        fake_run_conversion,
    )

    worker = BatchConversionWorker([bad_item, good_item])
    worker.run()
    _flush_logger(logger)

    log_text = (tmp_path / "logs" / LOG_FILE_NAME).read_text(
        encoding="utf-8"
    )

    assert bad_item.status == ConversionStatus.FAILED
    assert good_item.status == ConversionStatus.SUCCESS
    assert "Traceback" in log_text
    assert "broken file" in log_text


def test_temp_cleanup_only_removes_old_lfc_entries(tmp_path: Path) -> None:
    old_lfc = tmp_path / "lfc_old.tmp"
    fresh_lfc = tmp_path / "lfc_fresh.tmp"
    other_file = tmp_path / "other_old.tmp"

    for path in (old_lfc, fresh_lfc, other_file):
        path.write_text("x", encoding="utf-8")

    old_time = time.time() - 48 * 60 * 60
    os.utime(old_lfc, (old_time, old_time))
    os.utime(other_file, (old_time, old_time))

    removed_count = cleanup_old_lfc_temp_files(
        temp_directory=tmp_path,
        max_age_seconds=24 * 60 * 60,
    )

    assert removed_count == 1
    assert not old_lfc.exists()
    assert fresh_lfc.exists()
    assert other_file.exists()


def test_valid_image_validation_passes(tmp_path: Path) -> None:
    image_path = tmp_path / "ok.png"
    image = Image.new("RGB", (10, 10), (255, 0, 0))
    image.save(image_path)

    assert validate_image_file(image_path) == image_path
