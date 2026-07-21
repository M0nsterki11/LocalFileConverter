"""Load and palette-color bundled application icons with Qt fallbacks."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractButton,
    QStyle,
    QStyleOption,
    QStyleOptionButton,
    QWidget,
)

from utils.resource_utils import get_resource_path


ICON_DIRECTORY = get_resource_path("resources/icons")
APP_ICON_PATH = get_resource_path("resources/app_icon.ico")
SVG_COLOR_TOKEN = "#010101"
SVG_RENDER_SIZES = (16, 18, 20, 24, 32, 36, 48, 64)

UI_ICON_NAMES = (
    "add",
    "remove",
    "clear",
    "convert",
    "cancel",
    "settings",
    "folder",
    "merge",
    "up",
    "down",
    "about",
    "exit",
    "file",
    "files",
    "image",
    "pdf",
    "office",
)

FALLBACK_ICONS = {
    "add": QStyle.StandardPixmap.SP_FileDialogNewFolder,
    "remove": QStyle.StandardPixmap.SP_DialogDiscardButton,
    "clear": QStyle.StandardPixmap.SP_TrashIcon,
    "convert": QStyle.StandardPixmap.SP_DialogApplyButton,
    "cancel": QStyle.StandardPixmap.SP_DialogCancelButton,
    "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "folder": QStyle.StandardPixmap.SP_DirOpenIcon,
    "merge": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "up": QStyle.StandardPixmap.SP_ArrowUp,
    "down": QStyle.StandardPixmap.SP_ArrowDown,
    "about": QStyle.StandardPixmap.SP_MessageBoxInformation,
    "exit": QStyle.StandardPixmap.SP_DialogCloseButton,
    "file": QStyle.StandardPixmap.SP_FileIcon,
    "files": QStyle.StandardPixmap.SP_FileDialogListView,
    "image": QStyle.StandardPixmap.SP_FileIcon,
    "pdf": QStyle.StandardPixmap.SP_FileIcon,
    "office": QStyle.StandardPixmap.SP_FileIcon,
}


def get_icon(
    widget: QWidget,
    name: str,
) -> QIcon:
    """Return a named bundled icon colored for the target widget's QSS."""
    for extension in (".svg", ".png", ".ico"):
        icon_path = ICON_DIRECTORY / f"{name}{extension}"

        if icon_path.exists():
            if extension == ".svg":
                icon = _render_svg_icon(
                    str(icon_path),
                    _widget_icon_color(widget).name(),
                )
            else:
                icon = QIcon(str(icon_path))

            if not icon.isNull():
                return icon

    fallback = FALLBACK_ICONS.get(name)

    if fallback is not None:
        return widget.style().standardIcon(fallback)

    return QIcon()


def _widget_icon_color(widget: QWidget) -> QColor:
    """Resolve the effective foreground after QSS selectors are applied."""
    if isinstance(widget, QAbstractButton):
        option = QStyleOptionButton()
        option.initFrom(widget)
        return option.palette.color(QPalette.ColorRole.ButtonText)

    option = QStyleOption()
    option.initFrom(widget)
    return option.palette.color(QPalette.ColorRole.WindowText)


@lru_cache(maxsize=128)
def _render_svg_icon(path: str, color_name: str) -> QIcon:
    """Render one monochrome SVG at common sizes for crisp high-DPI scaling."""
    try:
        svg_data = (
            Path(path)
            .read_bytes()
            .replace(
                SVG_COLOR_TOKEN.encode("ascii"),
                color_name.encode("ascii"),
            )
        )
    except OSError:
        return QIcon()

    renderer = QSvgRenderer(QByteArray(svg_data))

    if not renderer.isValid():
        return QIcon()

    icon = QIcon()

    for size in SVG_RENDER_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)

    return icon


def get_app_icon() -> QIcon:
    """Return the product icon, or a null icon when the resource is absent."""
    if APP_ICON_PATH.exists():
        icon = QIcon(str(APP_ICON_PATH))

        if not icon.isNull():
            return icon

    return QIcon()
