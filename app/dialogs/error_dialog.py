from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.icon_provider import get_app_icon
from utils.error_handler import ErrorInfo
from utils.logging_utils import open_log_directory


class ErrorDetailsDialog(QDialog):
    def __init__(
        self,
        error_info: ErrorInfo,
        close_button_text: str = "U redu",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.error_info = error_info
        self.close_button_text = close_button_text
        self.setWindowTitle(error_info.title)
        self.setMinimumWidth(560)

        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        message_label = QLabel(self.error_info.message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        if self.error_info.suggestion:
            suggestion_label = QLabel(self.error_info.suggestion)
            suggestion_label.setWordWrap(True)
            layout.addWidget(suggestion_label)

        self.details_edit = QTextEdit()
        self.details_edit.setReadOnly(True)
        self.details_edit.setPlainText(self.error_info.technical_detail)
        self.details_edit.setVisible(False)
        self.details_edit.setMinimumHeight(140)
        layout.addWidget(self.details_edit)

        button_layout = QHBoxLayout()
        self.details_button = QPushButton("Tehnicki detalji")
        self.copy_button = QPushButton("Kopiraj detalje")
        self.open_logs_button = QPushButton("Otvori mapu s logovima")
        self.ok_button = QPushButton(self.close_button_text)

        self.details_button.clicked.connect(self._toggle_details)
        self.copy_button.clicked.connect(self._copy_details)
        self.open_logs_button.clicked.connect(open_log_directory)
        self.ok_button.clicked.connect(self.accept)

        button_layout.addWidget(self.details_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.open_logs_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)

    def _toggle_details(self) -> None:
        self.details_edit.setVisible(not self.details_edit.isVisible())

    def _copy_details(self) -> None:
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.error_info.technical_detail)
        except Exception:
            return
