from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.constants import (
    APP_NAME,
    FILE_DIALOG_FILTER,
    IMAGE_EXTENSIONS,
)
from app.workers import ConversionWorker
from utils.file_utils import (
    get_default_output_directory,
    open_directory,
)
from utils.format_utils import (
    get_available_output_formats,
    get_display_format,
    get_file_extension,
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
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label = QLabel(
            "Podržani formati: JPG, PNG, WEBP, PDF, "
            "DOCX, PPTX i XLSX"
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

        self.conversion_thread: QThread | None = None
        self.conversion_worker: ConversionWorker | None = None
        self.is_converting = False

        self.setWindowTitle(APP_NAME)
        self.resize(900, 800)
        self.setMinimumSize(720, 620)

        self._build_ui()
        self._connect_signals()
        self._update_output_directory_label()
        self._update_context_controls()
        self._update_controls()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        root_layout.addWidget(scroll_area)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(18)

        title_label = QLabel("LOCAL FILE CONVERTER")
        title_label.setObjectName("mainTitle")
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        subtitle_label = QLabel(
            "Pretvaranje datoteka lokalno, "
            "bez slanja podataka na internet"
        )
        subtitle_label.setObjectName("subtitle")
        subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle_label)

        self.drop_area = DropArea()
        main_layout.addWidget(self.drop_area)

        self.select_file_button = QPushButton(
            "Odaberi datoteku"
        )
        self.select_file_button.setMinimumHeight(42)

        select_button_layout = QHBoxLayout()
        select_button_layout.addStretch()
        select_button_layout.addWidget(
            self.select_file_button
        )
        select_button_layout.addStretch()

        main_layout.addLayout(select_button_layout)

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

        file_layout.addWidget(
            QLabel("Ulazni format:"),
            2,
            0,
        )
        file_layout.addWidget(
            self.input_format_label,
            2,
            1,
        )

        file_layout.setColumnStretch(1, 1)
        main_layout.addWidget(file_group)

        conversion_group = QGroupBox(
            "Postavke konverzije"
        )
        conversion_layout = QGridLayout(
            conversion_group
        )
        conversion_layout.setHorizontalSpacing(16)
        conversion_layout.setVerticalSpacing(12)

        self.output_format_label = QLabel(
            "Izlazni format:"
        )

        self.output_format_combo = QComboBox()
        self.output_format_combo.setMinimumHeight(38)

        self.quality_label = QLabel("Kvaliteta:")

        self.quality_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(90)
        self.quality_slider.setSingleStep(1)
        self.quality_slider.setPageStep(5)

        self.quality_value_label = QLabel("90%")
        self.quality_value_label.setMinimumWidth(45)
        self.quality_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.page_mode_label = QLabel("PDF stranice:")

        self.page_mode_combo = QComboBox()
        self.page_mode_combo.addItem(
            "Sve stranice",
            userData="all",
        )
        self.page_mode_combo.addItem(
            "Odabrane stranice",
            userData="selected",
        )
        self.page_mode_combo.setMinimumHeight(38)

        self.page_range_input = QLineEdit()
        self.page_range_input.setPlaceholderText(
            "Primjer: 1,3-5,8"
        )
        self.page_range_input.setMinimumHeight(38)

        self.multi_page_output_label = QLabel(
            "Više PDF stranica:"
        )

        self.multi_page_output_combo = QComboBox()
        self.multi_page_output_combo.addItem(
            "Obična mapa (zadano)",
            userData="folder",
        )
        self.multi_page_output_combo.addItem(
            "ZIP arhiva",
            userData="zip",
        )
        self.multi_page_output_combo.setCurrentIndex(0)
        self.multi_page_output_combo.setMinimumHeight(38)
        self.multi_page_output_combo.setToolTip(
            "Primjenjuje se kada PDF daje više slika. "
            "Ako obična mapa prijeđe 100 MB, rezultat će "
            "se automatski spremiti kao ZIP."
        )

        self.dpi_label = QLabel("PDF DPI:")

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItem("96 DPI", userData=96)
        self.dpi_combo.addItem("150 DPI", userData=150)
        self.dpi_combo.addItem("200 DPI", userData=200)
        self.dpi_combo.addItem("300 DPI", userData=300)
        self.dpi_combo.setCurrentIndex(1)
        self.dpi_combo.setMinimumHeight(38)

        self.output_directory_title_label = QLabel(
            "Izlazna mapa:"
        )

        self.output_directory_label = QLabel()
        self.output_directory_label.setObjectName(
            "pathLabel"
        )
        self.output_directory_label.setWordWrap(True)
        self.output_directory_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.select_output_button = QPushButton(
            "Promijeni mapu"
        )
        self.select_output_button.setMinimumHeight(38)

        conversion_layout.addWidget(
            self.output_format_label,
            0,
            0,
        )
        conversion_layout.addWidget(
            self.output_format_combo,
            0,
            1,
            1,
            2,
        )

        conversion_layout.addWidget(
            self.quality_label,
            1,
            0,
        )
        conversion_layout.addWidget(
            self.quality_slider,
            1,
            1,
        )
        conversion_layout.addWidget(
            self.quality_value_label,
            1,
            2,
        )

        conversion_layout.addWidget(
            self.page_mode_label,
            2,
            0,
        )
        conversion_layout.addWidget(
            self.page_mode_combo,
            2,
            1,
        )
        conversion_layout.addWidget(
            self.page_range_input,
            2,
            2,
        )

        conversion_layout.addWidget(
            self.multi_page_output_label,
            3,
            0,
        )
        conversion_layout.addWidget(
            self.multi_page_output_combo,
            3,
            1,
            1,
            2,
        )

        conversion_layout.addWidget(
            self.dpi_label,
            4,
            0,
        )
        conversion_layout.addWidget(
            self.dpi_combo,
            4,
            1,
            1,
            2,
        )

        conversion_layout.addWidget(
            self.output_directory_title_label,
            5,
            0,
        )
        conversion_layout.addWidget(
            self.output_directory_label,
            5,
            1,
        )
        conversion_layout.addWidget(
            self.select_output_button,
            5,
            2,
        )

        conversion_layout.setColumnStretch(1, 1)
        main_layout.addWidget(conversion_group)

        self.convert_button = QPushButton("CONVERT")
        self.convert_button.setObjectName(
            "convertButton"
        )
        self.convert_button.setMinimumHeight(50)

        main_layout.addWidget(self.convert_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel(
            "Status: Odaberi datoteku za početak."
        )
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)

        self.open_output_button = QPushButton(
            "Otvori izlaznu mapu"
        )
        self.open_output_button.setMinimumHeight(40)

        open_folder_layout = QHBoxLayout()
        open_folder_layout.addStretch()
        open_folder_layout.addWidget(
            self.open_output_button
        )
        open_folder_layout.addStretch()

        main_layout.addLayout(open_folder_layout)

    def _connect_signals(self) -> None:
        self.select_file_button.clicked.connect(
            self._select_file
        )
        self.drop_area.file_dropped.connect(
            self._handle_selected_file
        )

        self.select_output_button.clicked.connect(
            self._select_output_directory
        )
        self.open_output_button.clicked.connect(
            self._open_output_directory
        )

        self.output_format_combo.currentTextChanged.connect(
            self._output_format_changed
        )

        self.quality_slider.valueChanged.connect(
            self._quality_changed
        )

        self.page_mode_combo.currentIndexChanged.connect(
            self._update_context_controls
        )

        self.convert_button.clicked.connect(
            self._start_conversion
        )

    def _select_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi datoteku",
            "",
            FILE_DIALOG_FILTER,
        )

        if file_path:
            self._handle_selected_file(file_path)

    def _handle_selected_file(
        self,
        file_path: str,
    ) -> None:
        if self.is_converting:
            return

        path = Path(file_path)

        if not is_supported_file(path):
            QMessageBox.warning(
                self,
                "Nepodržana datoteka",
                (
                    "Odabrana datoteka ne postoji ili "
                    "njezin format trenutačno nije podržan."
                ),
            )
            return

        self.selected_file = path

        self.file_name_label.setText(path.name)
        self.file_path_label.setText(str(path))
        self.input_format_label.setText(
            get_display_format(path)
        )

        available_formats = (
            get_available_output_formats(path)
        )

        self.output_format_combo.blockSignals(True)
        self.output_format_combo.clear()
        self.output_format_combo.addItems(
            available_formats
        )
        self.output_format_combo.blockSignals(False)

        self.progress_bar.setValue(0)

        extension = get_file_extension(path)

        if extension in IMAGE_EXTENSIONS:
            self.status_label.setText(
                "Status: Slika je spremna za konverziju."
            )

        elif extension == ".pdf":
            self.status_label.setText(
                "Status: PDF je spreman za konverziju."
            )

        else:
            self.status_label.setText(
                "Status: Office konverzije bit će "
                "implementirane u sljedećoj fazi."
            )

        self._update_context_controls()
        self._update_controls()

    def _select_output_directory(self) -> None:
        selected_directory = (
            QFileDialog.getExistingDirectory(
                self,
                "Odaberi izlaznu mapu",
                str(self.output_directory),
            )
        )

        if selected_directory:
            self.output_directory = Path(
                selected_directory
            )
            self._update_output_directory_label()

    def _update_output_directory_label(self) -> None:
        self.output_directory_label.setText(
            str(self.output_directory)
        )

    def _open_output_directory(self) -> None:
        try:
            opened = open_directory(
                self.output_directory
            )

            if not opened:
                raise RuntimeError(
                    "Windows nije uspio otvoriti mapu."
                )

        except (OSError, RuntimeError) as error:
            QMessageBox.critical(
                self,
                "Greška pri otvaranju mape",
                str(error),
            )

    def _quality_changed(self, value: int) -> None:
        self.quality_value_label.setText(
            f"{value}%"
        )

    def _output_format_changed(
        self,
        output_format: str,
    ) -> None:
        self._update_context_controls()
        self._update_controls()

    def _update_context_controls(self) -> None:
        input_extension = ""

        if self.selected_file is not None:
            input_extension = get_file_extension(
                self.selected_file
            )

        output_format = (
            self.output_format_combo.currentText()
        )

        quality_visible = output_format in {
            "JPG",
            "WEBP",
        }

        self.quality_label.setVisible(quality_visible)
        self.quality_slider.setVisible(quality_visible)
        self.quality_value_label.setVisible(
            quality_visible
        )

        pdf_input = input_extension == ".pdf"

        self.page_mode_label.setVisible(pdf_input)
        self.page_mode_combo.setVisible(pdf_input)
        self.dpi_label.setVisible(pdf_input)
        self.dpi_combo.setVisible(pdf_input)
        self.multi_page_output_label.setVisible(pdf_input)
        self.multi_page_output_combo.setVisible(pdf_input)

        selected_page_mode = (
            self.page_mode_combo.currentData()
            == "selected"
        )

        self.page_range_input.setVisible(
            pdf_input and selected_page_mode
        )

        self._update_controls()

    def _update_controls(self) -> None:
        if self.selected_file is None:
            self.convert_button.setEnabled(False)
            return

        input_extension = get_file_extension(
            self.selected_file
        )
        output_format = (
            self.output_format_combo.currentText()
        )

        image_conversion = (
            input_extension in IMAGE_EXTENSIONS
            and output_format
            in {"JPG", "PNG", "WEBP", "PDF"}
        )

        pdf_conversion = (
            input_extension == ".pdf"
            and output_format in {"JPG", "PNG"}
        )

        conversion_ready = (
            (image_conversion or pdf_conversion)
            and not self.is_converting
        )

        self.convert_button.setEnabled(
            conversion_ready
        )

    def _set_conversion_running(
        self,
        running: bool,
    ) -> None:
        self.is_converting = running

        self.select_file_button.setEnabled(
            not running
        )
        self.drop_area.setEnabled(not running)
        self.output_format_combo.setEnabled(
            not running
        )
        self.select_output_button.setEnabled(
            not running
        )
        self.page_mode_combo.setEnabled(
            not running
        )
        self.page_range_input.setEnabled(
            not running
        )
        self.dpi_combo.setEnabled(not running)
        self.multi_page_output_combo.setEnabled(not running)

        quality_supported = (
            self.output_format_combo.currentText()
            in {"JPG", "WEBP"}
        )

        self.quality_slider.setEnabled(
            not running and quality_supported
        )
        self.quality_value_label.setEnabled(
            not running and quality_supported
        )

        self._update_controls()

    def _start_conversion(self) -> None:
        if (
            self.selected_file is None
            or self.is_converting
        ):
            return

        output_format = (
            self.output_format_combo.currentText()
        )

        if not output_format:
            QMessageBox.warning(
                self,
                "Nedostaje izlazni format",
                "Odaberi izlazni format.",
            )
            return

        page_selection: str | None = None

        if (
            self.selected_file.suffix.lower()
            == ".pdf"
            and self.page_mode_combo.currentData()
            == "selected"
        ):
            page_selection = (
                self.page_range_input.text().strip()
            )

            if not page_selection:
                QMessageBox.warning(
                    self,
                    "Nedostaju stranice",
                    (
                        "Upiši stranice koje želiš "
                        "pretvoriti, primjerice 1,3-5."
                    ),
                )
                return

        try:
            self.output_directory.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as error:
            QMessageBox.critical(
                self,
                "Greška izlazne mape",
                (
                    "Nije moguće stvoriti "
                    f"izlaznu mapu:\n{error}"
                ),
            )
            return

        dpi = int(
            self.dpi_combo.currentData() or 150
        )

        multi_page_output_mode = str(
        self.multi_page_output_combo.currentData()
        or "folder"
        )

        self.progress_bar.setValue(0)
        self.status_label.setText(
            "Status: Pokretanje konverzije..."
        )
        self._set_conversion_running(True)

        self.conversion_thread = QThread(self)

        self.conversion_worker = ConversionWorker(
            input_file=self.selected_file,
            output_directory=self.output_directory,
            output_format=output_format,
            quality=self.quality_slider.value(),
            dpi=dpi,
            page_selection=page_selection,
            multi_page_output_mode=multi_page_output_mode,
        )

        self.conversion_worker.moveToThread(
            self.conversion_thread
        )

        self.conversion_thread.started.connect(
            self.conversion_worker.run
        )

        self.conversion_worker.progress_changed.connect(
            self.progress_bar.setValue
        )
        self.conversion_worker.status_changed.connect(
            self._show_worker_status
        )

        self.conversion_worker.conversion_finished.connect(
            self._conversion_finished
        )
        self.conversion_worker.conversion_failed.connect(
            self._conversion_failed
        )

        self.conversion_worker.conversion_finished.connect(
            self.conversion_thread.quit
        )
        self.conversion_worker.conversion_failed.connect(
            self.conversion_thread.quit
        )

        self.conversion_worker.conversion_finished.connect(
            self.conversion_worker.deleteLater
        )
        self.conversion_worker.conversion_failed.connect(
            self.conversion_worker.deleteLater
        )

        self.conversion_thread.finished.connect(
            self._thread_finished
        )
        self.conversion_thread.finished.connect(
            self.conversion_thread.deleteLater
        )

        self.conversion_thread.start()

    def _show_worker_status(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            f"Status: {message}"
        )

    def _conversion_finished(
        self,
        result_path: str,
    ) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText(
            f"Status: Uspješno spremljeno:\n{result_path}"
        )

        self._set_conversion_running(False)

    def _conversion_failed(
        self,
        error_message: str,
    ) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText(
            "Status: Konverzija nije uspjela."
        )

        self._set_conversion_running(False)

        QMessageBox.critical(
            self,
            "Greška konverzije",
            error_message,
        )

    def _thread_finished(self) -> None:
        self.conversion_worker = None
        self.conversion_thread = None
        self._set_conversion_running(False)

    def closeEvent(self, event) -> None:
        if self.is_converting:
            QMessageBox.information(
                self,
                "Konverzija je u tijeku",
                (
                    "Pričekaj da trenutačna "
                    "konverzija završi."
                ),
            )
            event.ignore()
            return

        event.accept()