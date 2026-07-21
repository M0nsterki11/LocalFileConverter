from __future__ import annotations

from pathlib import Path

from app.conversion_item import ConversionStatus
from app.i18n import get_translation_manager
from app.main_window import MainWindow
from app.settings import AppSettings
from app.theme_manager import ThemeManager


def _window_with_files(
    tmp_path: Path,
    *names: str,
) -> MainWindow:
    paths = []

    for name in names:
        path = tmp_path / name
        path.write_bytes(b"content")
        paths.append(str(path))

    window = MainWindow(
        AppSettings(
            default_output_directory=tmp_path,
            show_batch_summary=False,
            open_output_after_success=False,
        )
    )
    window._add_files(paths)
    return window


def test_convert_cta_uses_runnable_item_count(
    qapp,
    tmp_path: Path,
) -> None:
    ThemeManager().apply_theme(qapp, "light")
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )

    try:
        window.show()
        qapp.processEvents()

        assert window.convert_button.isVisible()
        assert not window.convert_button.isEnabled()
        assert window.convert_button.text() == "Convert files"
        assert window.convert_button.minimumHeight() >= 56
        assert window.convert_button.height() >= 54
        assert window.idle_status_label.isVisible()
        assert not window.progress_group.isVisible()
        assert not window.cancel_button.isVisible()

        first_path = tmp_path / "first.png"
        first_path.write_bytes(b"first")
        window._add_files([str(first_path)])
        assert window.convert_button.text() == "Convert 1 file"
        assert window.convert_button.isEnabled()

        second_path = tmp_path / "second.jpg"
        second_path.write_bytes(b"second")
        window._add_files([str(second_path)])
        assert window.convert_button.text() == "Convert 2 files"
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_running_and_completed_batch_feedback_states(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window_with_files(
        tmp_path,
        "first.png",
        "second.jpg",
    )

    try:
        window.show()
        window._batch_item_ids = [
            item.unique_id
            for item in window.items
        ]
        window._set_status_message(
            "Status: Starting batch conversion...",
            batch=True,
        )
        window._set_conversion_running(True)
        window._item_started(window.items[1].unique_id)

        window.items[0].status = ConversionStatus.SUCCESS
        window.items[0].progress = 100
        window._item_progress_changed(
            window.items[1].unique_id,
            50,
        )
        qapp.processEvents()

        assert window.progress_group.isVisible()
        assert not window.idle_status_label.isVisible()
        assert not window.convert_button.isVisible()
        assert window.cancel_button.isVisible()
        assert window.cancel_button.isEnabled()
        assert window.progress_bar.value() == 75
        assert window.progress_percent_label.text() == "75%"
        assert window.progress_summary_label.text() == (
            "Processed 1 of 2 files"
        )
        assert window.current_file_label.text() == (
            "Current file: second.jpg"
        )

        window._batch_finished(1, 1, 0)
        qapp.processEvents()

        assert not window.is_converting
        assert window.progress_group.isVisible()
        assert window.convert_button.isVisible()
        assert not window.cancel_button.isVisible()
        assert window.progress_bar.value() == 100
        assert window.progress_percent_label.text() == "100%"
        assert window.progress_summary_label.text() == (
            "Processed 2 of 2 files"
        )
        assert window.current_file_label.text() == "Batch complete"

        window._set_status_message("Status: Ready.")
        assert not window.progress_group.isVisible()
        assert window.idle_status_label.isVisible()
        assert window.idle_status_label.text() == "Status: Ready."
    finally:
        window.is_converting = False
        window.close()


def test_cancel_remains_connected_to_worker(
    qapp,
    tmp_path: Path,
) -> None:
    class FakeWorker:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    window = _window_with_files(tmp_path, "image.png")
    worker = FakeWorker()

    try:
        window.show()
        window.batch_worker = worker
        window._batch_item_ids = [window.items[0].unique_id]
        window._set_status_message("Running", batch=True)
        window._set_conversion_running(True)
        qapp.processEvents()

        window.cancel_button.click()

        assert worker.cancelled
        assert window.cancel_requested
        assert not window.cancel_button.isEnabled()
        assert window.status_label.text() == (
            "Status: Cancelling batch conversion..."
        )
    finally:
        window.batch_worker = None
        window.is_converting = False
        window.close()


def test_group_d_runtime_translation(qapp, tmp_path: Path) -> None:
    manager = get_translation_manager()
    window = _window_with_files(
        tmp_path,
        "first.png",
        "second.jpg",
    )

    try:
        assert manager.set_language("hr") == "hr"
        window.retranslate_ui()
        window._batch_item_ids = [
            item.unique_id
            for item in window.items
        ]
        window._update_batch_progress()
        qapp.processEvents()

        assert window.convert_button.text() == (
            "Pretvori datoteke (2)"
        )
        assert window.cancel_button.text() == "Prekini konverziju"
        assert window.progress_group.title() == "Napredak"
        assert window.progress_summary_label.text() == (
            "Obrađeno datoteka: 0 od 2"
        )
    finally:
        manager.set_language("en")
        window.close()
