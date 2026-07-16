from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_REPOSITORY_URL,
)
from app.i18n import get_translation_manager
from app.icon_provider import get_app_icon
from utils.logging_utils import open_log_directory


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(460)

        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._build_ui()
        self.retranslate_ui()
        get_translation_manager().language_changed.connect(
            self.retranslate_ui
        )

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("mainTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.version_label = QLabel()
        self.version_label.setObjectName("subtitle")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.logs_button = QPushButton()
        self.logs_button.clicked.connect(open_log_directory)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.logs_button)
        button_layout.addWidget(self.close_button)

        root_layout.addWidget(self.title_label)
        root_layout.addWidget(self.version_label)
        root_layout.addWidget(self.body_label)
        root_layout.addLayout(button_layout)

    def retranslate_ui(self, *_args) -> None:
        self.setWindowTitle(self.tr("About {app_name}").format(
            app_name=APP_NAME,
        ))
        self.version_label.setText(self.tr("Version {version}").format(
            version=APP_VERSION,
        ))
        self.body_label.setText(
            self.tr(
                "Local File Converter processes files locally. "
                "Data is not sent to the internet.\n\n"
                "It supports image conversions, PDF conversions, Office "
                "documents to PDF, and merging multiple images into one PDF.\n\n"
                "The application is built with Python and PySide6. "
                "LibreOffice is used as an external tool when selected or "
                "required for Office conversion.\n\n"
                "The application stores a local technical log for errors. "
                "The log does not contain document contents, and you can open "
                "or delete it from your user folder.\n\n"
                "GitHub: {github_url}\n"
                "Copyright {year}"
            ).format(
                github_url=GITHUB_REPOSITORY_URL,
                year=date.today().year,
            )
        )
        self.logs_button.setText(self.tr("Open log folder"))
        self.close_button.setText(self.tr("Close"))
