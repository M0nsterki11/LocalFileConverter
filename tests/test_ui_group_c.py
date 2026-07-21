from __future__ import annotations

from pathlib import Path

from app.i18n import get_translation_manager
from app.main_window import MainWindow
from app.settings import AppSettings


def _window_with_file(
    tmp_path: Path,
    name: str,
    content: bytes = b"content",
) -> MainWindow:
    input_path = tmp_path / name
    input_path.write_bytes(content)
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )
    window._add_files([str(input_path)])
    return window


def test_advanced_options_are_collapsed_until_requested(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window_with_file(
        tmp_path,
        "photo.png",
        b"x" * 2048,
    )

    try:
        window.show()
        qapp.processEvents()

        assert window.advanced_options_button.isVisible()
        assert not window.advanced_options_button.isChecked()
        assert not window.advanced_options_container.isVisible()

        window.advanced_options_button.click()
        qapp.processEvents()

        assert window.advanced_options_container.isVisible()
        assert window.file_group.title() == "File details"
        assert window.file_path_label.text() == str(tmp_path / "photo.png")
        assert window.file_path_label.toolTip() == str(tmp_path / "photo.png")
        assert window.input_format_label.text() == "PNG"
        assert window.file_size_label.text() == "2.0 KB"
    finally:
        window.close()


def test_advanced_options_only_show_relevant_format_settings(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window_with_file(tmp_path, "photo.png")

    try:
        window.show()
        window.advanced_options_button.click()
        qapp.processEvents()
        item = window.items[0]
        card = window.queue_widget._cards_by_id[item.unique_id]

        assert item.output_format == "JPG"
        assert window.conversion_group.isVisible()
        assert window.quality_slider.isVisible()
        assert not window.page_mode_combo.isVisible()

        card.output_combo.setCurrentText("PDF")
        qapp.processEvents()

        assert item.output_format == "PDF"
        assert not window.conversion_group.isVisible()
        assert not window.quality_slider.isVisible()
    finally:
        window.close()


def test_pdf_details_show_page_controls_but_not_image_quality(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window_with_file(tmp_path, "document.pdf")

    try:
        window.show()
        window.advanced_options_button.click()
        qapp.processEvents()

        assert window.conversion_group.isVisible()
        assert window.page_mode_combo.isVisible()
        assert window.dpi_combo.isVisible()
        assert window.multi_page_output_combo.isVisible()
        assert not window.quality_slider.isVisible()

        window.page_mode_combo.setCurrentIndex(1)
        qapp.processEvents()
        assert window.page_range_input.isVisible()
    finally:
        window.close()


def test_card_is_the_visible_convert_to_control(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window_with_file(tmp_path, "photo.png")

    try:
        window.show()
        qapp.processEvents()
        item = window.items[0]
        card = window.queue_widget._cards_by_id[item.unique_id]

        formats = [
            card.output_combo.itemText(index)
            for index in range(card.output_combo.count())
        ]
        assert card.output_caption.text() == "Convert to"
        assert card.output_combo.minimumHeight() >= 40
        assert card.output_combo.minimumWidth() >= 150
        assert 38 <= card.output_combo.height() <= 42
        assert formats == item.available_output_formats
        assert card.output_combo.isVisible()
        assert window.output_format_combo.isHidden()
    finally:
        window.close()


def test_group_c_runtime_translation(qapp, tmp_path: Path) -> None:
    manager = get_translation_manager()
    window = _window_with_file(tmp_path, "photo.png")

    try:
        assert manager.set_language("hr") == "hr"
        window.retranslate_ui()
        qapp.processEvents()
        item = window.items[0]
        card = window.queue_widget._cards_by_id[item.unique_id]

        assert window.advanced_options_button.text() == "Napredne opcije"
        assert window.file_group.title() == "Detalji datoteke"
        assert window.conversion_group.title() == "Opcije formata"
        assert card.output_caption.text() == "Pretvori u"
    finally:
        manager.set_language("en")
        window.close()
