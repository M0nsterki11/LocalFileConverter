"""Drag-and-drop input widget for local files."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.constants import IMAGE_EXTENSIONS, OFFICE_EXTENSIONS, PDF_EXTENSION
from app.icon_provider import get_icon
from utils.format_utils import get_display_format
from utils.output_safety import human_readable_size


class FileDropArea(QFrame):
    """Card-style area for choosing files and showing a queue summary."""

    files_dropped = Signal(list)
    choose_files_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        self._file_paths: list[Path] = []
        self._current_icon_name = "file"
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self.setMaximumWidth(820)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.icon_label = QLabel()
        self.icon_label.setObjectName("dropIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(56, 56)

        self.title_label = QLabel()
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.title_label.setWordWrap(True)

        self.metadata_label = QLabel()
        self.metadata_label.setObjectName("dropMetadata")
        self.metadata_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metadata_label.setWordWrap(True)

        self.choose_files_button = QPushButton()
        self.choose_files_button.setObjectName("dropChooseButton")
        self.choose_files_button.setIcon(
            get_icon(self.choose_files_button, "add")
        )
        self.choose_files_button.setIconSize(QSize(18, 18))
        self.choose_files_button.setMinimumHeight(40)
        self.choose_files_button.clicked.connect(
            self.choose_files_requested.emit
        )

        self.description_label = QLabel()
        self.description_label.setObjectName(
            "dropDescription"
        )
        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.description_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 26, 32, 26)
        layout.setSpacing(9)
        layout.addWidget(
            self.icon_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(self.title_label)
        layout.addWidget(self.metadata_label)
        layout.addSpacing(3)
        layout.addWidget(
            self.choose_files_button,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addSpacing(2)
        layout.addWidget(self.description_label)
        self.retranslate_ui()

    def sizeHint(self) -> QSize:
        """Return a compact preferred size that may still shrink horizontally."""
        return QSize(760, 230)

    def set_files(self, file_paths: list[str | Path]) -> None:
        """Update the summary without taking ownership of the queue."""
        self._file_paths = [Path(path) for path in file_paths]
        self._refresh_summary()

    def retranslate_ui(self) -> None:
        self.choose_files_button.setText(self.tr("Choose files"))
        self.description_label.setText(
            self.tr("Supported formats: JPG, PNG, WEBP, PDF, DOCX, PPTX and XLSX")
        )
        self._refresh_summary()

    def refresh_icons(self) -> None:
        """Re-render palette-aware icons after a runtime theme change."""
        self.choose_files_button.setIcon(
            get_icon(self.choose_files_button, "add")
        )
        self._set_icon(self._current_icon_name)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_dragging_state(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_dragging_state(False)
        event.accept()

    def dropEvent(self, event) -> None:
        self._set_dragging_state(False)
        file_paths: list[str] = []

        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue

            path = Path(url.toLocalFile())

            if path.is_file():
                file_paths.append(str(path))

        if file_paths:
            self.files_dropped.emit(file_paths)
            event.acceptProposedAction()
            return

        event.ignore()

    def _set_dragging_state(self, dragging: bool) -> None:
        self.setProperty("dragging", dragging)
        self.style().unpolish(self)
        self.style().polish(self)

    def _refresh_summary(self) -> None:
        file_count = len(self._file_paths)

        if file_count == 0:
            self.title_label.setText(self.tr("Drop files here"))
            self.title_label.setToolTip("")
            self.metadata_label.clear()
            self.metadata_label.hide()
            self._set_icon("file")
            return

        if file_count == 1:
            path = self._file_paths[0]
            metadata = [get_display_format(path)]

            try:
                metadata.append(human_readable_size(path.stat().st_size))
            except OSError:
                pass

            self.title_label.setText(path.name)
            self.title_label.setToolTip(str(path))
            self.metadata_label.setText(" | ".join(metadata))
            self.metadata_label.show()
            self._set_icon(self._icon_name_for_path(path))
            return

        self.title_label.setToolTip("")
        self.title_label.setText(
            self.tr("{count} files added").format(count=file_count)
        )
        self.metadata_label.clear()
        self.metadata_label.hide()
        self._set_icon("files")

    def _set_icon(self, name: str) -> None:
        self._current_icon_name = name
        icon = get_icon(self.icon_label, name)
        self.icon_label.setPixmap(icon.pixmap(QSize(48, 48)))

    @staticmethod
    def _icon_name_for_path(path: Path) -> str:
        extension = path.suffix.lower()

        if extension in IMAGE_EXTENSIONS:
            return "image"

        if extension == PDF_EXTENSION:
            return "pdf"

        if extension in OFFICE_EXTENSIONS:
            return "office"

        return "file"
