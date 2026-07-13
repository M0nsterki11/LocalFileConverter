from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QStyle, QWidget

from utils.resource_utils import get_resource_path


ICON_DIRECTORY = get_resource_path("resources/icons")
APP_ICON_PATH = get_resource_path("resources/app_icon.ico")

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
}


def get_icon(
    widget: QWidget,
    name: str,
) -> QIcon:
    for extension in (".svg", ".png", ".ico"):
        icon_path = ICON_DIRECTORY / f"{name}{extension}"

        if icon_path.exists():
            icon = QIcon(str(icon_path))

            if not icon.isNull():
                return icon

    fallback = FALLBACK_ICONS.get(name)

    if fallback is not None:
        return widget.style().standardIcon(fallback)

    return QIcon()


def get_app_icon() -> QIcon:
    if APP_ICON_PATH.exists():
        icon = QIcon(str(APP_ICON_PATH))

        if not icon.isNull():
            return icon

    return QIcon()
