import sys

from PySide6.QtWidgets import QApplication

from app.constants import (
    APP_NAME,
    APP_ORGANIZATION,
)
from app.icon_provider import get_app_icon
from app.main_window import MainWindow
from app.settings import load_app_settings
from app.theme_manager import ThemeManager


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_NAME)

    app_icon = get_app_icon()

    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    app_settings = load_app_settings()
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, app_settings.theme)

    window = MainWindow(
        app_settings=app_settings,
        theme_manager=theme_manager,
    )
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
