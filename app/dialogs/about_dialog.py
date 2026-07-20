import logging
from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
from utils.resource_utils import get_resource_path
from utils.logging_utils import open_log_directory


logger = logging.getLogger(__name__)


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

        self.license_label = QLabel()
        self.license_label.setObjectName("subtitle")
        self.license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.license_label.setWordWrap(True)

        self.warranty_label = QLabel()
        self.warranty_label.setObjectName("subtitle")
        self.warranty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warranty_label.setWordWrap(True)

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        notice_button_layout = QHBoxLayout()
        notice_button_layout.addStretch()
        self.license_button = QPushButton()
        self.third_party_button = QPushButton()
        self.source_code_button = QPushButton()
        self.license_button.clicked.connect(
            lambda: self._open_local_document("LICENSE", "LICENSE")
        )
        self.third_party_button.clicked.connect(
            lambda: self._open_local_document(
                "THIRD_PARTY_NOTICES.txt",
                "THIRD_PARTY_NOTICES.txt",
            )
        )
        self.source_code_button.clicked.connect(self._open_source_code)
        notice_button_layout.addWidget(self.license_button)
        notice_button_layout.addWidget(self.third_party_button)
        notice_button_layout.addWidget(self.source_code_button)
        notice_button_layout.addStretch()

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
        root_layout.addWidget(self.license_label)
        root_layout.addWidget(self.warranty_label)
        root_layout.addWidget(self.body_label)
        root_layout.addLayout(notice_button_layout)
        root_layout.addLayout(button_layout)

    def retranslate_ui(self, *_args) -> None:
        self.setWindowTitle(self.tr("About {app_name}").format(
            app_name=APP_NAME,
        ))
        self.version_label.setText(self.tr("Version {version}").format(
            version=APP_VERSION,
        ))
        self.license_label.setText(
            self.tr("Licensed under GNU AGPL version 3 only")
        )
        self.warranty_label.setText(self.tr("No warranty"))
        self.body_label.setText(
            self.tr(
                "MyFile Converter processes files locally. "
                "Data is not sent to the internet.\n\n"
                "It supports image conversions, PDF conversions, Office "
                "documents to PDF, and merging multiple images into one PDF.\n\n"
                "The application is built with Python and PySide6. "
                "Microsoft Office or LibreOffice can be used as an external "
                "tool for Office conversion.\n\n"
                "The application stores a local technical log for errors. "
                "The log does not contain document contents, and you can open "
                "or delete it from your user folder.\n\n"
                "Source code: {github_url}\n"
                "GitHub: {github_url}\n"
                "Copyright {year}"
            ).format(
                github_url=GITHUB_REPOSITORY_URL,
                year=date.today().year,
            )
        )
        self.license_button.setText(self.tr("View license"))
        self.third_party_button.setText(self.tr("Third-party notices"))
        self.source_code_button.setText(self.tr("Source code"))
        self.logs_button.setText(self.tr("Open log folder"))
        self.close_button.setText(self.tr("Close"))

    def _open_local_document(self, relative_path: str, label: str) -> None:
        document_path = get_resource_path(relative_path)

        try:
            if not document_path.exists():
                raise FileNotFoundError(document_path)

            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(document_path.resolve()))
            )

            if not opened:
                raise OSError(f"QDesktopServices could not open {document_path}")
        except Exception as error:
            logger.exception("Could not open %s: %s", label, document_path)
            self._show_open_error(error)

    def _open_source_code(self) -> None:
        try:
            opened = QDesktopServices.openUrl(QUrl(GITHUB_REPOSITORY_URL))

            if not opened:
                raise OSError(
                    f"QDesktopServices could not open {GITHUB_REPOSITORY_URL}"
                )
        except Exception as error:
            logger.exception(
                "Could not open source code URL: %s",
                GITHUB_REPOSITORY_URL,
            )
            self._show_open_error(error)

    def _show_open_error(self, _error: Exception) -> None:
        QMessageBox.warning(
            self,
            self.tr("Could not open document"),
            self.tr(
                "The document could not be opened. "
                "Technical details were saved to the log."
            ),
        )
