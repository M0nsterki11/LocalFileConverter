from pathlib import Path

import pytest
import pymupdf
from PIL import Image

from app.batch_worker import BatchConversionWorker
from app.conversion_item import (
    ConversionItem,
    ConversionStatus,
    build_unique_supported_items,
)
from converters.base_converter import ConversionCancelledError
from converters.pdf_converter import convert_images_to_pdf
from utils.format_utils import get_available_output_formats


def _write_rgb_image(
    path: Path,
    color: tuple[int, int, int],
) -> None:
    image = Image.new("RGB", (40, 30), color)
    image.save(path)


def _render_page_center(
    pdf_path: Path,
    page_index: int,
) -> tuple[int, int, int]:
    with pymupdf.open(pdf_path) as document:
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(
            colorspace=pymupdf.csRGB,
            alpha=False,
        )

    center_x = pixmap.width // 2
    center_y = pixmap.height // 2
    offset = (center_y * pixmap.width + center_x) * pixmap.n
    return tuple(pixmap.samples[offset:offset + 3])


def test_build_unique_supported_items_skips_duplicates(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "image.jpg"
    _write_rgb_image(image_path, (255, 0, 0))

    result = build_unique_supported_items(
        file_paths=[image_path, image_path],
        existing_items=[],
        output_directory=tmp_path,
    )

    assert len(result.added_items) == 1
    assert result.added_items[0].input_path == image_path
    assert result.duplicate_paths == [image_path]
    assert result.unsupported_paths == []


def test_output_format_mapping_for_supported_inputs() -> None:
    assert get_available_output_formats("photo.jpg") == [
        "PNG",
        "WEBP",
        "PDF",
    ]
    assert get_available_output_formats("document.pdf") == [
        "PNG",
        "JPG",
    ]
    assert get_available_output_formats("slides.pptx") == ["PDF"]


def test_conversion_item_status_reset_for_rerun(
    tmp_path: Path,
) -> None:
    item = ConversionItem(
        input_path=tmp_path / "bad.jpg",
        input_format="JPG",
        output_format="PNG",
        output_directory=tmp_path,
        status=ConversionStatus.FAILED,
        progress=40,
        result_path=tmp_path / "old.png",
        error_message="old error",
    )

    item.mark_pending_for_run(tmp_path / "new")

    assert item.status == ConversionStatus.PENDING
    assert item.progress == 0
    assert item.result_path is None
    assert item.error_message is None
    assert item.output_directory == tmp_path / "new"


def test_batch_worker_continues_after_item_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    assert bad_item.status == ConversionStatus.FAILED
    assert "unexpected error" in bad_item.error_message
    assert good_item.status == ConversionStatus.SUCCESS
    assert good_item.result_path == tmp_path / "good.png"


def test_convert_images_to_pdf_keeps_page_order(
    tmp_path: Path,
) -> None:
    red_path = tmp_path / "red.png"
    blue_path = tmp_path / "blue.png"
    _write_rgb_image(red_path, (255, 0, 0))
    _write_rgb_image(blue_path, (0, 0, 255))

    result_path = convert_images_to_pdf(
        input_files=[red_path, blue_path],
        output_directory=tmp_path,
        output_filename="combined.pdf",
    )

    with pymupdf.open(result_path) as document:
        assert document.page_count == 2

    first_pixel = _render_page_center(result_path, 0)
    second_pixel = _render_page_center(result_path, 1)

    assert first_pixel[0] > 200
    assert second_pixel[2] > 200


def test_convert_images_to_pdf_handles_transparent_png(
    tmp_path: Path,
) -> None:
    transparent_path = tmp_path / "transparent.png"
    blue_path = tmp_path / "blue.png"
    transparent_image = Image.new("RGBA", (40, 30), (0, 0, 0, 0))
    transparent_image.save(transparent_path)
    _write_rgb_image(blue_path, (0, 0, 255))

    result_path = convert_images_to_pdf(
        input_files=[transparent_path, blue_path],
        output_directory=tmp_path,
        output_filename="transparent.pdf",
    )

    center_pixel = _render_page_center(result_path, 0)

    assert center_pixel[0] > 240
    assert center_pixel[1] > 240
    assert center_pixel[2] > 240


def test_convert_images_to_pdf_uses_unique_filename(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    _write_rgb_image(first_path, (255, 0, 0))
    _write_rgb_image(second_path, (0, 255, 0))
    (tmp_path / "combined.pdf").write_bytes(b"existing")

    result_path = convert_images_to_pdf(
        input_files=[first_path, second_path],
        output_directory=tmp_path,
        output_filename="combined.pdf",
    )

    assert result_path.name == "combined_1.pdf"


def test_cancelled_multi_image_pdf_deletes_partial_result(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    _write_rgb_image(first_path, (255, 0, 0))
    _write_rgb_image(second_path, (0, 255, 0))
    calls = 0

    def cancel_after_save() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 4

    with pytest.raises(ConversionCancelledError):
        convert_images_to_pdf(
            input_files=[first_path, second_path],
            output_directory=tmp_path,
            output_filename="combined.pdf",
            cancel_check=cancel_after_save,
        )

    assert not (tmp_path / "combined.pdf").exists()
