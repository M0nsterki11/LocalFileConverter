from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class FileDropArea(QFrame):
    """Podrucje u koje korisnik moze povuci vise datoteka."""

    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)

        self.title_label = QLabel("Povuci datoteke ovdje")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label = QLabel(
            "Podrzani formati: JPG, PNG, WEBP, PDF, DOCX, PPTX i XLSX"
        )
        self.description_label.setObjectName(
            "dropDescription"
        )
        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.description_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addStretch()

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
