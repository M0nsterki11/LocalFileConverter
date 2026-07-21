from __future__ import annotations

from pathlib import Path

from app.main_window import MainWindow
from app.settings import AppSettings
from app.theme_manager import ThemeManager


def _window(qapp, tmp_path: Path) -> MainWindow:
    ThemeManager().apply_theme(qapp, "light")
    return MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )


def test_header_has_stronger_compact_brand_hierarchy(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window(qapp, tmp_path)

    try:
        window.show()
        qapp.processEvents()

        assert window.header_widget.objectName() == "appHeader"
        assert window.title_label.font().pixelSize() >= 36
        assert window.title_label.font().weight() >= 700
        assert window.header_widget.layout().contentsMargins().top() == 8
        assert window.header_widget.layout().spacing() <= 4
        assert window.subtitle_label.geometry().top() - (
            window.title_label.geometry().bottom() + 1
        ) <= 4
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_output_controls_share_one_subtle_card(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window(qapp, tmp_path)

    try:
        window.resize(760, 850)
        window.show()
        qapp.processEvents()
        output_layout = window.output_group.layout()

        assert window.output_group.objectName() == "outputCard"
        assert window.output_group.title() == "Output"
        assert output_layout.indexOf(
            window.output_directory_title_label
        ) >= 0
        assert output_layout.indexOf(window.output_directory_label) >= 0
        assert output_layout.indexOf(window.select_output_button) >= 0
        assert window.main_scroll_area.horizontalScrollBar().maximum() == 0
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_idle_status_card_preserves_progress_visibility_behavior(
    qapp,
    tmp_path: Path,
) -> None:
    window = _window(qapp, tmp_path)

    try:
        window.show()
        qapp.processEvents()

        assert window.status_panel.objectName() == "statusCard"
        assert window.idle_status_label.parentWidget() is window.status_panel
        assert window.status_panel.isVisible()
        assert window.idle_status_label.text() == "Status: Add files to start."

        window._set_status_message("Status: Working...", batch=True)

        assert not window.status_panel.isVisible()
        assert window.progress_group.isVisible()
        assert window.status_label.text() == "Status: Working..."

        window._set_status_message("Status: Ready.")

        assert window.status_panel.isVisible()
        assert not window.progress_group.isVisible()
        assert window.idle_status_label.text() == "Status: Ready."
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_refinement_cards_have_light_and_dark_theme_rules() -> None:
    for theme in ("light", "dark"):
        stylesheet = ThemeManager().build_stylesheet(theme)

        assert "QGroupBox#outputCard" in stylesheet
        assert "QFrame#statusCard" in stylesheet
        assert "border-radius: 8px;" in stylesheet
