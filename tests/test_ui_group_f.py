from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ElementTree

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton

from app.icon_provider import SVG_COLOR_TOKEN, UI_ICON_NAMES, get_icon
from app.main_window import MainWindow
from app.settings import AppSettings
from app.theme_manager import ThemeManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_DIRECTORY = PROJECT_ROOT / "resources" / "icons"


def _average_luminance(icon) -> float:
    image = icon.pixmap(QSize(24, 24)).toImage()
    luminance_values = []

    for y_position in range(image.height()):
        for x_position in range(image.width()):
            color = image.pixelColor(x_position, y_position)

            if color.alpha() >= 128:
                luminance_values.append(
                    0.2126 * color.red()
                    + 0.7152 * color.green()
                    + 0.0722 * color.blue()
                )

    assert luminance_values
    return sum(luminance_values) / len(luminance_values)


def test_monochrome_svg_icon_set_is_complete_and_consistent() -> None:
    svg_paths = {
        path.stem: path
        for path in ICON_DIRECTORY.glob("*.svg")
    }

    assert set(svg_paths) == set(UI_ICON_NAMES)

    for path in svg_paths.values():
        svg_text = path.read_text(encoding="utf-8")
        root = ElementTree.fromstring(svg_text)

        assert root.tag.endswith("svg")
        assert root.attrib["viewBox"] == "0 0 24 24"
        assert root.attrib["fill"] == "none"
        assert root.attrib["stroke"] == SVG_COLOR_TOKEN
        assert root.attrib["stroke-width"] == "1.8"
        assert "<text" not in svg_text


def test_svg_icons_follow_light_dark_and_primary_button_colors(qapp) -> None:
    manager = ThemeManager()
    secondary_button = QPushButton()
    primary_button = QPushButton()
    primary_button.setObjectName("convertButton")

    try:
        manager.apply_theme(qapp, "light")
        secondary_button.ensurePolished()
        primary_button.ensurePolished()
        light_secondary = _average_luminance(
            get_icon(secondary_button, "settings")
        )
        light_primary = _average_luminance(
            get_icon(primary_button, "convert")
        )

        manager.apply_theme(qapp, "dark")

        for button in (secondary_button, primary_button):
            button.style().unpolish(button)
            button.style().polish(button)

        dark_secondary = _average_luminance(
            get_icon(secondary_button, "settings")
        )
        dark_primary = _average_luminance(
            get_icon(primary_button, "convert")
        )

        assert light_secondary < 100
        assert dark_secondary > 200
        assert light_primary > 240
        assert dark_primary > 240
    finally:
        secondary_button.close()
        primary_button.close()
        qapp.setStyleSheet("")


def test_main_workflow_controls_use_bundled_icons(
    qapp,
    tmp_path: Path,
) -> None:
    ThemeManager().apply_theme(qapp, "light")
    input_path = tmp_path / "presentation.pptx"
    input_path.write_bytes(b"content")
    window = MainWindow(
        AppSettings(default_output_directory=tmp_path)
    )

    try:
        window._add_files([str(input_path)])
        window.show()
        qapp.processEvents()

        buttons = (
            window.add_files_button,
            window.remove_selected_button,
            window.clear_list_button,
            window.retry_failed_button,
            window.merge_images_button,
            window.settings_button,
            window.convert_button,
            window.cancel_button,
            window.open_output_button,
            window.select_output_button,
            window.advanced_options_button,
            window.drop_area.choose_files_button,
        )
        actions = (
            window.add_files_action,
            window.change_output_action,
            window.exit_action,
            window.merge_images_action,
            window.settings_action,
            window.about_action,
        )
        card = window.queue_widget._cards_by_id[
            window.items[0].unique_id
        ]

        assert all(not button.icon().isNull() for button in buttons)
        assert all(not action.icon().isNull() for action in actions)
        assert not window.drop_area.icon_label.pixmap().isNull()
        assert not card.icon_label.pixmap().isNull()
        assert not card.remove_button.icon().isNull()
        assert window.add_files_button.iconSize() == QSize(18, 18)
        assert window.convert_button.iconSize() == QSize(18, 18)
        assert card.remove_button.iconSize() == QSize(18, 18)

        light_icon_luminance = _average_luminance(
            window.settings_button.icon()
        )
        ThemeManager().apply_theme(qapp, "dark")
        window._apply_icons_and_tooltips()

        assert light_icon_luminance < 100
        assert _average_luminance(
            window.settings_button.icon()
        ) > 200
    finally:
        window.close()
        qapp.setStyleSheet("")


def test_ui_icons_are_covered_by_release_resource_verification() -> None:
    spec_text = (PROJECT_ROOT / "MyFileConverter.spec").read_text(
        encoding="utf-8"
    )
    build_verifier = (
        PROJECT_ROOT / "scripts" / "verify_build.py"
    ).read_text(encoding="utf-8")
    installer_verifier = (
        PROJECT_ROOT / "scripts" / "verify_installer.py"
    ).read_text(encoding="utf-8")

    assert 'datas.append((str(resources_path), "resources"))' in spec_text
    assert "UI_ICON_NAMES" in build_verifier
    assert 'resource_root / "icons"' in build_verifier
    assert "UI_ICON_NAMES" in installer_verifier
    assert "_check_bundle_ui_icons" in installer_verifier
