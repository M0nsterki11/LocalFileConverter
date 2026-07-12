from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_NAME, FILE_DIALOG_FILTER
from utils.file_utils import (
    get_default_output_directory,
    open_directory,
)
from utils.format_utils import (
    get_available_output_formats,
    get_display_format,
    is_supported_file,
)


class DropArea(QFrame):
    """Područje u koje korisnik može povući datoteku."""

    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(180)

        self.title_label = QLabel("Povuci datoteku ovdje")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.description_label = QLabel(
            "Podržani formati: JPG, PNG, WEBP, PDF, DOCX, PPTX i XLSX"
        )
        self.description_label.setObjectName("dropDescription")
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue

            file_path = Path(url.toLocalFile())

            if file_path.is_file():
                self.file_dropped.emit(str(file_path))
                event.acceptProposedAction()
                return

        event.ignore()

    def _set_dragging_state(self, dragging: bool) -> None:
        self.setProperty("dragging", dragging)

        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.selected_file: Path | None = None
        self.output_directory = get_default_output_directory()

        self.setWindowTitle(APP_NAME)
        self.resize(900, 720)
        self.setMinimumSize(720, 600)

        self._build_ui()
        self._connect_signals()
        self._update_output_directory_label()
        self._update_controls()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(18)

        # Naslov
        title_label = QLabel(APP_NAME.upper())
        title_label.setObjectName("mainTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_label = QLabel(
            "Pretvaranje datoteka lokalno, bez slanja podataka na internet"
        )
        subtitle_label.setObjectName("subtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        # Drag-and-drop područje
        self.drop_area = DropArea()
        main_layout.addWidget(self.drop_area)

        self.select_file_button = QPushButton("Odaberi datoteku")
        self.select_file_button.setObjectName("secondaryButton")
        self.select_file_button.setMinimumHeight(42)

        select_button_layout = QHBoxLayout()
        select_button_layout.addStretch()
        select_button_layout.addWidget(self.select_file_button)
        select_button_layout.addStretch()

        main_layout.addLayout(select_button_layout)

        # Podaci o datoteci
        file_group = QGroupBox("Odabrana datoteka")
        file_layout = QGridLayout(file_group)
        file_layout.setHorizontalSpacing(16)
        file_layout.setVerticalSpacing(10)

        self.file_name_label = QLabel("Nije odabrana")
        self.file_name_label.setObjectName("valueLabel")
        self.file_name_label.setWordWrap(True)

        self.file_path_label = QLabel("—")
        self.file_path_label.setObjectName("pathLabel")
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.input_format_label = QLabel("—")
        self.input_format_label.setObjectName("valueLabel")

        file_layout.addWidget(QLabel("Naziv:"), 0, 0)
        file_layout.addWidget(self.file_name_label, 0, 1)

        file_layout.addWidget(QLabel("Putanja:"), 1, 0)
        file_layout.addWidget(self.file_path_label, 1, 1)

        file_layout.addWidget(QLabel("Ulazni format:"), 2, 0)
        file_layout.addWidget(self.input_format_label, 2, 1)

        file_layout.setColumnStretch(1, 1)

        main_layout.addWidget(file_group)

        # Postavke konverzije
        conversion_group = QGroupBox("Postavke konverzije")
        conversion_layout = QGridLayout(conversion_group)
        conversion_layout.setHorizontalSpacing(16)
        conversion_layout.setVerticalSpacing(12)

        self.output_format_combo = QComboBox()
        self.output_format_combo.setMinimumHeight(38)
        self.output_format_combo.setPlaceholderText("Odaberi izlazni format")

        self.output_directory_label = QLabel()
        self.output_directory_label.setObjectName("pathLabel")
        self.output_directory_label.setWordWrap(True)
        self.output_directory_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.select_output_button = QPushButton("Promijeni mapu")
        self.select_output_button.setMinimumHeight(38)

        conversion_layout.addWidget(QLabel("Izlazni format:"), 0, 0)
        conversion_layout.addWidget(self.output_format_combo, 0, 1, 1, 2)

        conversion_layout.addWidget(QLabel("Izlazna mapa:"), 1, 0)
        conversion_layout.addWidget(self.output_directory_label, 1, 1)
        conversion_layout.addWidget(self.select_output_button, 1, 2)

        conversion_layout.setColumnStretch(1, 1)

        main_layout.addWidget(conversion_group)

        # Convert gumb
        self.convert_button = QPushButton("CONVERT")
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setMinimumHeight(50)

        main_layout.addWidget(self.convert_button)

        # Napredak i status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.status_label = QLabel("Status: Odaberi datoteku za početak.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

        # Otvaranje izlazne mape
        self.open_output_button = QPushButton("Otvori izlaznu mapu")
        self.open_output_button.setMinimumHeight(40)

        open_folder_layout = QHBoxLayout()
        open_folder_layout.addStretch()
        open_folder_layout.addWidget(self.open_output_button)
        open_folder_layout.addStretch()

        main_layout.addLayout(open_folder_layout)

    def _connect_signals(self) -> None:
        self.select_file_button.clicked.connect(self._select_file)
        self.drop_area.file_dropped.connect(self._handle_selected_file)

        self.select_output_button.clicked.connect(
            self._select_output_directory
        )
        self.open_output_button.clicked.connect(
            self._open_output_directory
        )

        self.output_format_combo.currentTextChanged.connect(
            self._update_controls
        )

        self.convert_button.clicked.connect(self._convert_clicked)

    def _select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi datoteku",
            "",
            FILE_DIALOG_FILTER,
        )

        if file_path:
            self._handle_selected_file(file_path)

    def _handle_selected_file(self, file_path: str) -> None:
        path = Path(file_path)

        if not is_supported_file(path):
            QMessageBox.warning(
                self,
                "Nepodržana datoteka",
                (
                    "Odabrana datoteka ne postoji ili njezin format "
                    "trenutačno nije podržan."
                ),
            )
            return

        self.selected_file = path

        self.file_name_label.setText(path.name)
        self.file_path_label.setText(str(path))
        self.input_format_label.setText(get_display_format(path))

        available_formats = get_available_output_formats(path)

        self.output_format_combo.blockSignals(True)
        self.output_format_combo.clear()
        self.output_format_combo.addItems(available_formats)
        self.output_format_combo.blockSignals(False)

        if available_formats:
            self.status_label.setText(
                "Status: Datoteka je spremna za odabir konverzije."
            )
        else:
            self.status_label.setText(
                "Status: Za ovu datoteku nema dostupnih izlaznih formata."
            )

        self.progress_bar.setValue(0)
        self._update_controls()

    def _select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Odaberi izlaznu mapu",
            str(self.output_directory),
        )

        if selected_directory:
            self.output_directory = Path(selected_directory)
            self._update_output_directory_label()

    def _update_output_directory_label(self) -> None:
        self.output_directory_label.setText(str(self.output_directory))

    def _open_output_directory(self) -> None:
        try:
            opened = open_directory(self.output_directory)

            if not opened:
                raise RuntimeError("Windows nije uspio otvoriti mapu.")

        except (OSError, RuntimeError) as error:
            QMessageBox.critical(
                self,
                "Greška pri otvaranju mape",
                str(error),
            )

    def _update_controls(self) -> None:
        conversion_ready = (
            self.selected_file is not None
            and bool(self.output_format_combo.currentText())
        )

        self.convert_button.setEnabled(conversion_ready)

    def _convert_clicked(self) -> None:
        if self.selected_file is None:
            return

        output_format = self.output_format_combo.currentText()
        input_format = get_display_format(self.selected_file)

        self.progress_bar.setValue(0)
        self.status_label.setText(
            "Status: "
            f"{input_format} → {output_format} je odabrano. "
            "Stvarna konverzija bit će spojena u sljedećoj fazi."
        )
