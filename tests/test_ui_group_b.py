from __future__ import annotations

from pathlib import Path

from PySide6.QtTest import QSignalSpy

from app.conversion_item import (
    ConversionStatus,
    create_conversion_item,
)
from app.i18n import get_translation_manager
from app.main_window import MainWindow
from app.settings import AppSettings
from app.widgets.conversion_queue_widget import ConversionQueueWidget


def _create_item(
    tmp_path: Path,
    name: str,
    content: bytes = b"content",
):
    input_path = tmp_path / name
    input_path.write_bytes(content)
    return create_conversion_item(input_path, tmp_path)


def test_queue_cards_show_file_data_and_checkbox_selection(
    qapp,
    tmp_path: Path,
) -> None:
    first_item = _create_item(
        tmp_path,
        "first.png",
        b"x" * 2048,
    )
    second_item = _create_item(tmp_path, "second.pdf")
    queue = ConversionQueueWidget()
    selection_spy = QSignalSpy(queue.selection_state_changed)

    try:
        queue.set_items([first_item, second_item])
        queue.resize(760, 360)
        queue.show()
        qapp.processEvents()

        first_card = queue._cards_by_id[first_item.unique_id]
        second_card = queue._cards_by_id[second_item.unique_id]

        assert first_card.name_label.toolTip() == str(first_item.input_path)
        assert first_card.metadata_label.text() == "PNG | 2.0 KB"
        assert first_card.output_combo.minimumWidth() >= 150
        assert queue.current_item_id() == first_item.unique_id
        assert queue.selected_item_ids() == []

        first_card.selection_checkbox.click()
        second_card.selection_checkbox.click()

        assert queue.selected_item_ids() == [
            first_item.unique_id,
            second_item.unique_id,
        ]
        assert first_card.property("selected") is True
        assert second_card.property("selected") is True
        assert selection_spy.count() >= 2
    finally:
        queue.close()


def test_queue_card_preserves_output_and_remove_signals(
    qapp,
    tmp_path: Path,
) -> None:
    item = _create_item(tmp_path, "image.png")
    queue = ConversionQueueWidget()
    output_spy = QSignalSpy(queue.output_format_changed)
    remove_spy = QSignalSpy(queue.remove_requested)

    try:
        queue.set_items([item])
        card = queue._cards_by_id[item.unique_id]
        card.output_combo.setCurrentText("WEBP")
        card.remove_button.click()

        assert output_spy.count() == 1
        assert output_spy.at(0) == [item.unique_id, "WEBP"]
        assert remove_spy.count() == 1
        assert remove_spy.at(0) == [item.unique_id]
    finally:
        queue.close()


def test_queue_card_elides_long_names_and_shows_active_progress(
    qapp,
    tmp_path: Path,
) -> None:
    long_name = f"{'very_long_document_name_' * 5}.png"
    item = _create_item(tmp_path, long_name)
    queue = ConversionQueueWidget()

    try:
        queue.set_items([item])
        queue.resize(680, 300)
        queue.show()
        qapp.processEvents()
        card = queue._cards_by_id[item.unique_id]

        assert card.name_label.toolTip() == str(item.input_path)
        assert card.name_label.text() != item.input_path.name

        item.set_status(ConversionStatus.CONVERTING)
        item.progress = 42
        queue.update_item(item)
        qapp.processEvents()

        assert card.progress_bar.isVisible()
        assert card.progress_bar.value() == 42

        item.set_status(ConversionStatus.FAILED, "Detailed failure")
        item.error_message = "Detailed failure"
        queue.update_item(item)

        assert not card.progress_bar.isVisible()
        assert card.result_label.toolTip() == "Detailed failure"
    finally:
        queue.close()


def test_main_window_contextual_actions_follow_queue_state(
    qapp,
    tmp_path: Path,
) -> None:
    first_item_path = tmp_path / "first.png"
    first_item_path.write_bytes(b"first")
    second_item_path = tmp_path / "second.jpg"
    second_item_path.write_bytes(b"second")
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )

    try:
        window._add_files(
            [str(first_item_path), str(second_item_path)]
        )
        first_item = window.items[0]
        first_card = window.queue_widget._cards_by_id[
            first_item.unique_id
        ]

        assert window.add_files_button.property("actionRole") == "primary"
        assert window.merge_images_button.property("actionRole") == "primary"
        assert window.clear_list_button.text() == "Clear all"
        assert not window.add_files_button.isHidden()
        assert not window.merge_images_button.isHidden()
        assert not window.clear_list_button.isHidden()
        assert not window.settings_button.isHidden()
        assert window.remove_selected_button.isHidden()
        assert window.retry_failed_button.isHidden()

        first_card.selection_checkbox.click()
        assert not window.remove_selected_button.isHidden()
        assert window.remove_selected_button.isEnabled()

        first_item.set_status(ConversionStatus.FAILED, "Failed")
        first_item.error_message = "Failed"
        window.queue_widget.update_item(first_item)
        window._update_controls()
        assert not window.retry_failed_button.isHidden()

        window._remove_selected_items()
        assert len(window.items) == 1
        assert window.items[0].unique_id != first_item.unique_id
        assert window.remove_selected_button.isHidden()
    finally:
        window.close()


def test_queue_card_runtime_translation(qapp, tmp_path: Path) -> None:
    item = _create_item(tmp_path, "image.png")
    queue = ConversionQueueWidget()
    manager = get_translation_manager()

    try:
        queue.set_items([item])
        card = queue._cards_by_id[item.unique_id]
        assert card.output_caption.text() == "Convert to"
        assert manager.set_language("hr") == "hr"
        queue.retranslate_ui()
        assert card.output_caption.text() == "Pretvori u"
        assert card.remove_button.toolTip() == "Ukloni stavku"
    finally:
        manager.set_language("en")
        queue.close()
