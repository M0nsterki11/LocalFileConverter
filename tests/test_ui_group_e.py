from __future__ import annotations

from pathlib import Path

from app.constants import APP_NAME
from app.conversion_item import create_conversion_item
from app.main_window import MainWindow
from app.settings import AppSettings
from app.theme_manager import ThemeManager
from app.widgets.conversion_queue_widget import ConversionQueueWidget


def _window_with_file(tmp_path: Path) -> MainWindow:
    input_path = tmp_path / "photo.png"
    input_path.write_bytes(b"content")
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )
    window._add_files([str(input_path)])
    return window


def test_main_sections_use_scoped_unframed_style() -> None:
    stylesheet = ThemeManager().build_stylesheet("light")

    assert "QWidget#mainContent QGroupBox {" in stylesheet
    assert "background-color: transparent;\n    border: none;" in stylesheet
    assert "QWidget#mainContent QGroupBox::title {" in stylesheet
    assert "font-size: 16px;" in stylesheet
    assert "QGroupBox,\nQTableWidget {" in stylesheet
    assert "border: 1px solid #d8dee4;" in stylesheet


def test_group_e_typography_spacing_and_control_sizes(
    qapp,
    tmp_path: Path,
) -> None:
    ThemeManager().apply_theme(qapp, "light")
    window = _window_with_file(tmp_path)

    try:
        window.resize(900, 900)
        window.show()
        qapp.processEvents()
        item = window.items[0]
        card = window.queue_widget._cards_by_id[item.unique_id]
        margins = card.layout().contentsMargins()

        assert window.title_label.text() == APP_NAME
        assert window.title_label.font().pixelSize() >= 30
        assert window.subtitle_label.font().pixelSize() == 14
        assert 38 <= window.add_files_button.height() <= 42
        assert 38 <= window.merge_images_button.height() <= 42
        assert 38 <= card.output_combo.height() <= 42
        assert window.convert_button.height() >= 54
        assert margins.left() == 16
        assert margins.top() == 14
        assert margins.right() == 16
        assert margins.bottom() == 14
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_dark_theme_uses_layered_neutral_surfaces() -> None:
    stylesheet = ThemeManager().build_stylesheet("dark")

    assert "background-color: #181a1f;" in stylesheet
    assert "background-color: #202329;" in stylesheet
    assert "background-color: #23262c;" in stylesheet
    assert "background-color: #121821;" not in stylesheet


def test_queue_height_tracks_up_to_three_visible_cards(
    qapp,
    tmp_path: Path,
) -> None:
    items = []

    for index in range(4):
        path = tmp_path / f"image-{index}.png"
        path.write_bytes(b"content")
        items.append(create_conversion_item(path, tmp_path))

    queue = ConversionQueueWidget()

    try:
        queue.set_items(items[:1])
        queue.show()
        qapp.processEvents()
        one_card_height = queue.scroll_area.height()

        queue.set_items(items)
        qapp.processEvents()
        four_card_height = queue.scroll_area.height()

        assert one_card_height <= 150
        assert four_card_height > one_card_height
        assert four_card_height <= 420
        assert queue.scroll_area.verticalScrollBar().maximum() > 0
    finally:
        queue.close()
