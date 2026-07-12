import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.constants import APP_NAME
from app.main_window import MainWindow

STYLESHEET_PATH = (
    Path(__file__).resolve().parent
    / "resources"
    / "icons"
    / "application_stylesheet.qss"
)


def load_stylesheet(app: QApplication) -> None:
    if not STYLESHEET_PATH.exists():
        return

    try:
        stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")
        app.setStyleSheet(stylesheet)
    except OSError:
        # Aplikacija i dalje radi ako se stil ne uspije učitati.
        pass


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    load_stylesheet(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
