"""Start the MyFile Converter desktop application."""

import sys
import traceback

from PySide6.QtWidgets import QApplication

from app.constants import (
    APP_NAME,
    APP_ORGANIZATION,
    APP_SETTINGS_APPLICATION_NAME,
    APP_VERSION,
)
from app.dialogs.error_dialog import ErrorDetailsDialog
from app.icon_provider import get_app_icon
from app.i18n import get_translation_manager, translate
from app.main_window import MainWindow
from app.settings import load_app_settings
from app.theme_manager import ThemeManager
from utils.error_handler import ErrorInfo
from utils.logging_utils import (
    cleanup_old_lfc_temp_files,
    log_exception_safely,
    sanitize_for_log,
    setup_logging,
)


def main() -> int:
    """Initialize application services and enter the Qt event loop."""
    logger = setup_logging()
    logger.info("Starting %s version=%s", APP_NAME, APP_VERSION)
    cleanup_old_lfc_temp_files(logger=logger)

    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_SETTINGS_APPLICATION_NAME)
    _install_global_exception_hook()
    app.aboutToQuit.connect(
        lambda: logger.info("Closing %s version=%s", APP_NAME, APP_VERSION)
    )

    app_icon = get_app_icon()

    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    app_settings = load_app_settings()
    get_translation_manager().set_language(app_settings.language)

    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, app_settings.theme)

    window = MainWindow(
        app_settings=app_settings,
        theme_manager=theme_manager,
    )
    window.show()

    return app.exec()


def _install_global_exception_hook() -> None:
    original_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_traceback)
            return

        details = "".join(
            traceback.format_exception(
                exc_type,
                exc_value,
                exc_traceback,
            )
        )
        logger = setup_logging()
        log_exception_safely(
            logger,
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

        try:
            error_info = ErrorInfo(
                title=translate("Main", "Unexpected error"),
                message=(
                    translate(
                        "Main",
                        "An unexpected error occurred. Details were saved to the log.",
                    )
                ),
                technical_detail=sanitize_for_log(details),
            )
            ErrorDetailsDialog(
                error_info,
                close_button_text=translate("Main", "Close"),
            ).exec()
        except Exception:
            return

    sys.excepthook = handle_exception


if __name__ == "__main__":
    sys.exit(main())
