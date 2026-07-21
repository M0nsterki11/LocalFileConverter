from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QSignalSpy

from app.main_window import MAIN_CONTENT_MAX_WIDTH, MainWindow
from app.settings import AppSettings
from app.widgets.file_drop_area import FileDropArea


def test_main_content_is_centered_and_responsive(qapp, tmp_path: Path) -> None:
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )

    try:
        window.theme_manager.apply_theme(qapp, "dark")
        window.resize(1920, 900)
        window.show()
        qapp.processEvents()

        viewport_width = window.main_scroll_area.viewport().width()
        content_width = window.main_content_widget.width()
        left_margin = window.main_content_widget.x()
        right_margin = viewport_width - left_margin - content_width

        assert content_width == MAIN_CONTENT_MAX_WIDTH
        assert abs(left_margin - right_margin) <= 1
        assert window._list_action_columns == 3

        window.resize(760, 700)
        qapp.processEvents()

        viewport_width = window.main_scroll_area.viewport().width()
        assert window.main_content_widget.width() <= viewport_width
        assert not window.main_scroll_area.horizontalScrollBar().isVisible()
        assert window.drop_area.width() < window.main_content_widget.width()
        assert window._list_action_columns == 2
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_drop_area_summarizes_files_and_emits_choose_request(
    qapp,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "example.png"
    first_path.write_bytes(b"x" * 2048)
    second_path = tmp_path / "document.pdf"
    second_path.write_bytes(b"pdf")
    drop_area = FileDropArea()
    choose_spy = QSignalSpy(drop_area.choose_files_requested)

    try:
        drop_area.show()
        qapp.processEvents()
        assert drop_area.title_label.text() == "Drop files here"
        assert not drop_area.icon_label.pixmap().isNull()

        drop_area.choose_files_button.click()
        assert choose_spy.count() == 1

        drop_area.set_files([first_path])
        assert drop_area.title_label.text() == first_path.name
        assert drop_area.metadata_label.text() == "PNG | 2.0 KB"
        assert drop_area.metadata_label.isVisible()

        drop_area.set_files([first_path, second_path])
        assert drop_area.title_label.text() == "2 files added"
        assert not drop_area.metadata_label.isVisible()
    finally:
        drop_area.close()


def test_drop_area_preserves_local_file_drop_signal(
    qapp,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.jpg"
    first_path.write_bytes(b"first")
    second_path = tmp_path / "second.png"
    second_path.write_bytes(b"second")
    drop_area = FileDropArea()
    drop_spy = QSignalSpy(drop_area.files_dropped)
    mime_data = QMimeData()
    mime_data.setUrls(
        [
            QUrl.fromLocalFile(str(first_path)),
            QUrl.fromLocalFile(str(second_path)),
        ]
    )
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    drop_area.dropEvent(event)

    assert event.isAccepted()
    assert drop_spy.count() == 1
    assert drop_spy.at(0)[0] == [str(first_path), str(second_path)]


def test_main_window_keeps_drop_summary_in_sync(
    qapp,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.png"
    first_path.write_bytes(b"first")
    second_path = tmp_path / "second.jpg"
    second_path.write_bytes(b"second")
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )

    try:
        window._add_files([str(first_path)])
        assert window.drop_area.title_label.text() == first_path.name

        window._add_files([str(second_path)])
        assert window.drop_area.title_label.text() == "2 files added"

        window.resize(760, 820)
        window.show()
        qapp.processEvents()
        assert not window.main_scroll_area.horizontalScrollBar().isVisible()

        window._clear_items()
        assert window.drop_area.title_label.text() == "Drop files here"
    finally:
        window.close()
