from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
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

from app.batch_worker import BatchConversionWorker
from app.constants import (
    APP_NAME,
    FILE_DIALOG_FILTER,
    OFFICE_EXTENSIONS,
)
from app.conversion_item import (
    ConversionItem,
    ConversionStatus,
    build_unique_supported_items,
)
from app.dialogs.merge_images_dialog import MergeImagesDialog
from app.settings import (
    get_saved_libreoffice_path,
    save_libreoffice_path,
)
from app.widgets.conversion_queue_widget import ConversionQueueWidget
from utils.file_utils import (
    get_default_output_directory,
    open_directory,
)
from utils.format_utils import get_file_extension
from utils.libreoffice_utils import (
    find_libreoffice,
    get_default_libreoffice_browse_directory,
    is_valid_libreoffice_executable,
)


class DropArea(QFrame):
    """Podrucje u koje korisnik moze povuci vise datoteka."""

    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setMinimumHeight(180)

        self.title_label = QLabel("Povuci datoteke ovdje")
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label = QLabel(
            "Podrzani formati: JPG, PNG, WEBP, PDF, "
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.items: list[ConversionItem] = []
        self.active_item_id: str | None = None
        self.output_directory = get_default_output_directory()

        saved_libreoffice_path = get_saved_libreoffice_path()
        self.libreoffice_path = find_libreoffice(
            saved_libreoffice_path
        )

        self.batch_thread: QThread | None = None
        self.batch_worker: BatchConversionWorker | None = None
        self.is_converting = False
        self.cancel_requested = False
        self._loading_item_controls = False
        self._batch_item_ids: list[str] = []

        self.setWindowTitle(APP_NAME)
        self.resize(1100, 840)
        self.setMinimumSize(820, 680)

        self._build_ui()
        self._connect_signals()
        self._update_output_directory_label()
        self._refresh_libreoffice_ui()
        self._load_active_item(None)
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

        list_button_layout = QHBoxLayout()
        list_button_layout.setSpacing(10)

        self.add_files_button = QPushButton("Dodaj datoteke")
        self.add_files_button.setMinimumHeight(40)
        self.remove_selected_button = QPushButton(
            "Ukloni oznacene"
        )
        self.remove_selected_button.setMinimumHeight(40)
        self.clear_list_button = QPushButton("Ocisti listu")
        self.clear_list_button.setMinimumHeight(40)
        self.retry_failed_button = QPushButton(
            "Ponovi neuspjele"
        )
        self.retry_failed_button.setMinimumHeight(40)
        self.merge_images_button = QPushButton(
            "Spoji slike u jedan PDF"
        )
        self.merge_images_button.setMinimumHeight(40)

        for button in (
            self.add_files_button,
            self.remove_selected_button,
            self.clear_list_button,
            self.retry_failed_button,
            self.merge_images_button,
        ):
            list_button_layout.addWidget(button)

        main_layout.addLayout(list_button_layout)

        queue_group = QGroupBox("Red cekanja")
        queue_layout = QVBoxLayout(queue_group)
        self.queue_widget = ConversionQueueWidget()
        queue_layout.addWidget(self.queue_widget)
        main_layout.addWidget(queue_group)

        file_group = QGroupBox("Oznacena stavka")
        file_layout = QGridLayout(file_group)
        file_layout.setHorizontalSpacing(16)
        file_layout.setVerticalSpacing(10)

        self.file_name_label = QLabel("Nije odabrana")
        self.file_name_label.setObjectName("valueLabel")
        self.file_name_label.setWordWrap(True)

        self.file_path_label = QLabel("-")
        self.file_path_label.setObjectName("pathLabel")
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.input_format_label = QLabel("-")
        self.input_format_label.setObjectName("valueLabel")

        file_layout.addWidget(QLabel("Naziv:"), 0, 0)
        file_layout.addWidget(self.file_name_label, 0, 1)
        file_layout.addWidget(QLabel("Putanja:"), 1, 0)
        file_layout.addWidget(self.file_path_label, 1, 1)
        file_layout.addWidget(QLabel("Ulazni format:"), 2, 0)
        file_layout.addWidget(self.input_format_label, 2, 1)
        file_layout.setColumnStretch(1, 1)
        main_layout.addWidget(file_group)

        conversion_group = QGroupBox(
            "Postavke oznacene stavke"
        )
        conversion_layout = QGridLayout(conversion_group)
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
            "Vise PDF stranica:"
        )
        self.multi_page_output_combo = QComboBox()
        self.multi_page_output_combo.addItem(
            "Obicna mapa (zadano)",
            userData="folder",
        )
        self.multi_page_output_combo.addItem(
            "ZIP arhiva",
            userData="zip",
        )
        self.multi_page_output_combo.setMinimumHeight(38)
        self.multi_page_output_combo.setToolTip(
            "Primjenjuje se kada PDF daje vise slika. "
            "Ako obicna mapa prijede 100 MB, rezultat ce "
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

        self.libreoffice_group = QGroupBox(
            "LibreOffice za Office -> PDF"
        )
        libreoffice_layout = QGridLayout(
            self.libreoffice_group
        )
        libreoffice_layout.setHorizontalSpacing(12)
        libreoffice_layout.setVerticalSpacing(10)

        self.libreoffice_path_input = QLineEdit()
        self.libreoffice_path_input.setReadOnly(True)
        self.libreoffice_path_input.setMinimumHeight(38)
        self.libreoffice_path_input.setPlaceholderText(
            "LibreOffice nije pronaden"
        )

        self.detect_libreoffice_button = QPushButton(
            "Pronadi automatski"
        )
        self.detect_libreoffice_button.setMinimumHeight(38)

        self.select_libreoffice_button = QPushButton(
            "Odaberi soffice.exe"
        )
        self.select_libreoffice_button.setMinimumHeight(38)

        libreoffice_description = QLabel(
            "LibreOffice je potreban za DOCX, PPTX i XLSX "
            "konverzije. Putanja se sprema za sljedece pokretanje."
        )
        libreoffice_description.setObjectName(
            "dropDescription"
        )
        libreoffice_description.setWordWrap(True)

        libreoffice_layout.addWidget(
            QLabel("Program:"),
            0,
            0,
        )
        libreoffice_layout.addWidget(
            self.libreoffice_path_input,
            0,
            1,
            1,
            2,
        )
        libreoffice_layout.addWidget(
            self.detect_libreoffice_button,
            1,
            1,
        )
        libreoffice_layout.addWidget(
            self.select_libreoffice_button,
            1,
            2,
        )
        libreoffice_layout.addWidget(
            libreoffice_description,
            2,
            0,
            1,
            3,
        )
        libreoffice_layout.setColumnStretch(1, 1)
        main_layout.addWidget(self.libreoffice_group)

        action_button_layout = QHBoxLayout()
        action_button_layout.setSpacing(12)
        self.convert_button = QPushButton("CONVERT ALL")
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setMinimumHeight(50)

        self.cancel_button = QPushButton("PREKINI")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setMinimumHeight(50)
        self.cancel_button.setEnabled(False)

        action_button_layout.addWidget(
            self.convert_button,
            stretch=3,
        )
        action_button_layout.addWidget(
            self.cancel_button,
            stretch=1,
        )
        main_layout.addLayout(action_button_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.status_label = QLabel(
            "Status: Dodaj datoteke za pocetak."
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
        self.add_files_button.clicked.connect(
            self._select_files
        )
        self.drop_area.files_dropped.connect(self._add_files)
        self.remove_selected_button.clicked.connect(
            self._remove_selected_items
        )
        self.clear_list_button.clicked.connect(
            self._clear_items
        )
        self.retry_failed_button.clicked.connect(
            self._retry_failed_items
        )
        self.merge_images_button.clicked.connect(
            self._open_merge_images_dialog
        )
        self.queue_widget.selection_changed.connect(
            self._queue_selection_changed
        )
        self.queue_widget.output_format_changed.connect(
            self._queue_output_format_changed
        )
        self.queue_widget.remove_requested.connect(
            self._remove_item_by_id
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
            self._page_mode_changed
        )
        self.page_range_input.textChanged.connect(
            self._page_range_changed
        )
        self.dpi_combo.currentIndexChanged.connect(
            self._dpi_changed
        )
        self.multi_page_output_combo.currentIndexChanged.connect(
            self._multi_page_output_changed
        )

        self.convert_button.clicked.connect(self._start_batch)
        self.cancel_button.clicked.connect(
            self._cancel_conversion
        )
        self.detect_libreoffice_button.clicked.connect(
            self._detect_libreoffice
        )
        self.select_libreoffice_button.clicked.connect(
            self._select_libreoffice
        )

    def _select_files(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Odaberi datoteke",
            "",
            FILE_DIALOG_FILTER,
        )

        self._add_files(file_paths)

    def _add_files(self, file_paths: list[str]) -> None:
        if self.is_converting or not file_paths:
            return

        result = build_unique_supported_items(
            file_paths=file_paths,
            existing_items=self.items,
            output_directory=self.output_directory,
        )

        self.items.extend(result.added_items)
        self.queue_widget.set_items(self.items)

        if result.added_items:
            self.queue_widget.set_current_item_id(
                result.added_items[0].unique_id
            )
            self.status_label.setText(
                f"Status: Dodano stavki: {len(result.added_items)}"
            )

        skipped_count = (
            len(result.unsupported_paths)
            + len(result.duplicate_paths)
        )

        if skipped_count:
            QMessageBox.information(
                self,
                "Neke datoteke su preskocene",
                (
                    f"Preskoceno stavki: {skipped_count}\n"
                    f"Nepodrzano: {len(result.unsupported_paths)}\n"
                    f"Duplikati: {len(result.duplicate_paths)}"
                ),
            )

        self._update_controls()

    def _queue_selection_changed(self, item_id: str) -> None:
        self._load_active_item(item_id)

    def _queue_output_format_changed(
        self,
        item_id: str,
        output_format: str,
    ) -> None:
        item = self._item_by_id(item_id)

        if item is None or self.is_converting:
            return

        item.output_format = output_format
        item.status = ConversionStatus.PENDING
        item.result_path = None
        item.error_message = None
        item.progress = 0
        self.queue_widget.update_item(item)

        if item.unique_id == self.active_item_id:
            self._load_active_item(item.unique_id)

        self._update_controls()

    def _remove_selected_items(self) -> None:
        if self.is_converting:
            return

        selected_ids = set(self.queue_widget.selected_item_ids())

        if not selected_ids:
            return

        self.items = [
            item
            for item in self.items
            if item.unique_id not in selected_ids
        ]
        self.queue_widget.set_items(self.items)
        self._load_active_item(self.queue_widget.current_item_id())
        self._update_controls()

    def _remove_item_by_id(self, item_id: str) -> None:
        if self.is_converting:
            return

        self.items = [
            item
            for item in self.items
            if item.unique_id != item_id
        ]
        self.queue_widget.set_items(self.items)
        self._load_active_item(self.queue_widget.current_item_id())
        self._update_controls()

    def _clear_items(self) -> None:
        if self.is_converting:
            return

        self.items.clear()
        self.queue_widget.set_items(self.items)
        self._load_active_item(None)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Lista je ociscena.")
        self._update_controls()

    def _retry_failed_items(self) -> None:
        if self.is_converting:
            return

        for item in self.items:
            if item.status == ConversionStatus.FAILED:
                item.mark_pending_for_run(self.output_directory)
                self.queue_widget.update_item(item)

        self._update_controls()

    def _open_merge_images_dialog(self) -> None:
        dialog = MergeImagesDialog(
            output_directory=self.output_directory,
            parent=self,
        )
        dialog.exec()

    def _load_active_item(
        self,
        item_id: str | None,
    ) -> None:
        item = self._item_by_id(item_id) if item_id else None
        self.active_item_id = item.unique_id if item else None
        self._loading_item_controls = True

        if item is None:
            self.file_name_label.setText("Nije odabrana")
            self.file_path_label.setText("-")
            self.input_format_label.setText("-")
            self.output_format_combo.clear()
            self.quality_slider.setValue(90)
            self.quality_value_label.setText("90%")
            self.page_mode_combo.setCurrentIndex(0)
            self.page_range_input.clear()
            self.dpi_combo.setCurrentIndex(1)
            self.multi_page_output_combo.setCurrentIndex(0)
        else:
            self.file_name_label.setText(item.input_path.name)
            self.file_path_label.setText(str(item.input_path))
            self.input_format_label.setText(item.input_format)

            self.output_format_combo.clear()
            self.output_format_combo.addItems(
                item.available_output_formats
            )
            self.output_format_combo.setCurrentText(
                item.output_format
            )
            self.quality_slider.setValue(item.quality)
            self.quality_value_label.setText(
                f"{item.quality}%"
            )

            if item.page_selection:
                self.page_mode_combo.setCurrentIndex(1)
                self.page_range_input.setText(
                    item.page_selection
                )
            else:
                self.page_mode_combo.setCurrentIndex(0)
                self.page_range_input.clear()

            self._set_combo_to_user_data(
                self.dpi_combo,
                item.dpi,
            )
            self._set_combo_to_user_data(
                self.multi_page_output_combo,
                item.multi_page_output_mode,
            )

        self._loading_item_controls = False
        self._update_context_controls()
        self._update_controls()

    def _select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Odaberi izlaznu mapu",
            str(self.output_directory),
        )

        if not selected_directory:
            return

        self.output_directory = Path(selected_directory)
        self._update_output_directory_label()

        for item in self.items:
            if item.status == ConversionStatus.PENDING:
                item.output_directory = self.output_directory

        self.status_label.setText(
            "Status: Izlazna mapa je promijenjena."
        )

    def _update_output_directory_label(self) -> None:
        self.output_directory_label.setText(
            str(self.output_directory)
        )

    def _open_output_directory(self) -> None:
        try:
            opened = open_directory(self.output_directory)

            if not opened:
                raise RuntimeError(
                    "Windows nije uspio otvoriti mapu."
                )

        except (OSError, RuntimeError) as error:
            QMessageBox.critical(
                self,
                "Greska pri otvaranju mape",
                str(error),
            )

    def _quality_changed(self, value: int) -> None:
        self.quality_value_label.setText(f"{value}%")

        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None:
            item.quality = value

    def _output_format_changed(
        self,
        output_format: str,
    ) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None and output_format:
            item.output_format = output_format
            item.status = ConversionStatus.PENDING
            item.result_path = None
            item.error_message = None
            item.progress = 0
            self.queue_widget.update_item(item)

        self._update_context_controls()
        self._update_controls()

    def _page_mode_changed(self) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None:
            if self.page_mode_combo.currentData() == "selected":
                item.page_selection = (
                    self.page_range_input.text().strip()
                    or None
                )
            else:
                item.page_selection = None

        self._update_context_controls()

    def _page_range_changed(self, value: str) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if (
            item is not None
            and self.page_mode_combo.currentData() == "selected"
        ):
            item.page_selection = value.strip() or None

    def _dpi_changed(self) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None:
            item.dpi = int(self.dpi_combo.currentData() or 150)

    def _multi_page_output_changed(self) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None:
            item.multi_page_output_mode = str(
                self.multi_page_output_combo.currentData()
                or "folder"
            )

    def _detect_libreoffice(self) -> None:
        detected_path = find_libreoffice()

        if detected_path is None:
            QMessageBox.warning(
                self,
                "LibreOffice nije pronaden",
                (
                    "LibreOffice nije automatski pronaden. "
                    "Instaliraj LibreOffice ili rucno odaberi "
                    "datoteku soffice.exe."
                ),
            )
            return

        self.libreoffice_path = detected_path
        save_libreoffice_path(detected_path)
        self._refresh_libreoffice_ui()
        self.status_label.setText(
            "Status: LibreOffice je uspjesno pronaden."
        )

    def _select_libreoffice(self) -> None:
        if self.libreoffice_path is not None:
            start_directory = self.libreoffice_path.parent
        else:
            start_directory = (
                get_default_libreoffice_browse_directory()
            )

        executable_path, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi LibreOffice soffice.exe",
            str(start_directory),
            (
                "LibreOffice executable (soffice.exe);;"
                "Izvrsne datoteke (*.exe);;"
                "Sve datoteke (*.*)"
            ),
        )

        if not executable_path:
            return

        selected_path = Path(executable_path)

        if not is_valid_libreoffice_executable(
            selected_path
        ):
            QMessageBox.warning(
                self,
                "Neispravna LibreOffice datoteka",
                (
                    "Odaberi datoteku soffice.exe iz LibreOffice "
                    "programske mape.\n\n"
                    "Uobicajena putanja je:\n"
                    r"C:\Program Files\LibreOffice\program\soffice.exe"
                ),
            )
            return

        self.libreoffice_path = selected_path.resolve()
        save_libreoffice_path(self.libreoffice_path)
        self._refresh_libreoffice_ui()
        self.status_label.setText(
            "Status: LibreOffice putanja je spremljena."
        )

    def _refresh_libreoffice_ui(self) -> None:
        if is_valid_libreoffice_executable(
            self.libreoffice_path
        ):
            self.libreoffice_path_input.setText(
                str(self.libreoffice_path)
            )
            self.libreoffice_path_input.setToolTip(
                str(self.libreoffice_path)
            )
        else:
            self.libreoffice_path = None
            self.libreoffice_path_input.clear()
            self.libreoffice_path_input.setPlaceholderText(
                "LibreOffice nije pronaden"
            )

        self._update_controls()

    def _update_context_controls(self) -> None:
        item = self._active_item()
        input_extension = (
            get_file_extension(item.input_path)
            if item is not None
            else ""
        )
        output_format = (
            item.output_format
            if item is not None
            else ""
        )

        quality_visible = output_format in {"JPG", "WEBP"}
        pdf_input = input_extension == ".pdf"
        office_input = input_extension in OFFICE_EXTENSIONS
        selected_page_mode = (
            self.page_mode_combo.currentData() == "selected"
        )

        self.quality_label.setVisible(quality_visible)
        self.quality_slider.setVisible(quality_visible)
        self.quality_value_label.setVisible(quality_visible)
        self.page_mode_label.setVisible(pdf_input)
        self.page_mode_combo.setVisible(pdf_input)
        self.page_range_input.setVisible(
            pdf_input and selected_page_mode
        )
        self.dpi_label.setVisible(pdf_input)
        self.dpi_combo.setVisible(pdf_input)
        self.multi_page_output_label.setVisible(pdf_input)
        self.multi_page_output_combo.setVisible(pdf_input)
        self.libreoffice_group.setVisible(office_input)

    def _update_controls(self) -> None:
        has_items = bool(self.items)
        has_active = self._active_item() is not None
        selected_ids = self.queue_widget.selected_item_ids()
        runnable_items = self._runnable_items()
        failed_items = [
            item
            for item in self.items
            if item.status == ConversionStatus.FAILED
        ]

        self.add_files_button.setEnabled(not self.is_converting)
        self.drop_area.setEnabled(not self.is_converting)
        self.remove_selected_button.setEnabled(
            not self.is_converting and bool(selected_ids)
        )
        self.clear_list_button.setEnabled(
            not self.is_converting and has_items
        )
        self.retry_failed_button.setEnabled(
            not self.is_converting and bool(failed_items)
        )
        self.merge_images_button.setEnabled(not self.is_converting)
        self.convert_button.setEnabled(
            not self.is_converting and bool(runnable_items)
        )
        self.cancel_button.setEnabled(self.is_converting)

        settings_enabled = (
            has_active and not self.is_converting
        )
        self.output_format_combo.setEnabled(settings_enabled)
        self.quality_slider.setEnabled(settings_enabled)
        self.page_mode_combo.setEnabled(settings_enabled)
        self.page_range_input.setEnabled(settings_enabled)
        self.dpi_combo.setEnabled(settings_enabled)
        self.multi_page_output_combo.setEnabled(settings_enabled)
        self.select_output_button.setEnabled(not self.is_converting)
        self.detect_libreoffice_button.setEnabled(
            not self.is_converting
        )
        self.select_libreoffice_button.setEnabled(
            not self.is_converting
        )
        self.queue_widget.set_locked(self.is_converting)

    def _start_batch(self) -> None:
        if self.is_converting:
            return

        runnable_items = self._runnable_items()

        if not runnable_items:
            self.status_label.setText(
                "Status: Nema stavki spremnih za obradu."
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
                "Greska izlazne mape",
                (
                    "Nije moguce stvoriti izlaznu mapu:\n"
                    f"{error}"
                ),
            )
            return

        for item in runnable_items:
            item.mark_pending_for_run(self.output_directory)
            self.queue_widget.update_item(item)

        self.cancel_requested = False
        self._batch_item_ids = [
            item.unique_id
            for item in runnable_items
        ]
        self.progress_bar.setValue(0)
        self.status_label.setText(
            "Status: Pokretanje batch konverzije..."
        )
        self._set_conversion_running(True)

        self.batch_thread = QThread(self)
        self.batch_worker = BatchConversionWorker(
            items=runnable_items,
            libreoffice_path=self.libreoffice_path,
        )
        self.batch_worker.moveToThread(self.batch_thread)

        self.batch_thread.started.connect(self.batch_worker.run)
        self.batch_worker.batch_started.connect(
            self._batch_started
        )
        self.batch_worker.item_started.connect(
            self._item_started
        )
        self.batch_worker.item_progress.connect(
            self._item_progress_changed
        )
        self.batch_worker.item_status_changed.connect(
            self._item_status_changed
        )
        self.batch_worker.item_finished.connect(
            self._item_finished
        )
        self.batch_worker.item_failed.connect(
            self._item_failed
        )
        self.batch_worker.item_cancelled.connect(
            self._item_cancelled
        )
        self.batch_worker.batch_cancelled.connect(
            self._batch_cancelled
        )
        self.batch_worker.batch_finished.connect(
            self._batch_finished
        )

        self.batch_worker.batch_finished.connect(
            self.batch_thread.quit
        )
        self.batch_worker.batch_finished.connect(
            self.batch_worker.deleteLater
        )
        self.batch_thread.finished.connect(
            self.batch_thread.deleteLater
        )
        self.batch_thread.finished.connect(
            self._thread_finished
        )
        self.batch_thread.start()

    def _cancel_conversion(self) -> None:
        if self.batch_worker is None or self.cancel_requested:
            return

        self.cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.status_label.setText(
            "Status: Prekid batch konverzije..."
        )
        self.batch_worker.cancel()

    def _batch_started(self) -> None:
        self.status_label.setText(
            "Status: Batch konverzija je pokrenuta."
        )

    def _item_started(self, item_id: str) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.status = ConversionStatus.CONVERTING
        item.progress = 0
        item.error_message = None
        item.result_path = None
        self.queue_widget.update_item(item)
        self.queue_widget.set_current_item_id(item_id)
        self.status_label.setText(
            f"Status: Pretvaranje {item.input_path.name}..."
        )

    def _item_progress_changed(
        self,
        item_id: str,
        progress: int,
    ) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.progress = max(0, min(100, int(progress)))
        self.queue_widget.update_item(item)
        self._update_batch_progress()

    def _item_status_changed(
        self,
        item_id: str,
        message: str,
    ) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.status_message = message
        self.queue_widget.update_item(item)

        if item.unique_id == self.active_item_id:
            self.status_label.setText(
                f"Status: {item.input_path.name}: {message}"
            )

    def _item_finished(
        self,
        item_id: str,
        result_path: str,
    ) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.status = ConversionStatus.SUCCESS
        item.progress = 100
        item.result_path = Path(result_path)
        item.error_message = None
        item.status_message = "Konverzija je zavrsena."
        self.queue_widget.update_item(item)
        self._update_batch_progress()

    def _item_failed(
        self,
        item_id: str,
        error_message: str,
    ) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.status = ConversionStatus.FAILED
        item.progress = 0
        item.error_message = error_message
        item.status_message = error_message
        self.queue_widget.update_item(item)
        self._update_batch_progress()

    def _item_cancelled(self, item_id: str) -> None:
        item = self._item_by_id(item_id)

        if item is None:
            return

        item.status = ConversionStatus.CANCELLED
        item.error_message = (
            item.error_message
            or "Konverzija je prekinuta."
        )
        item.status_message = item.error_message
        self.queue_widget.update_item(item)
        self._update_batch_progress()

    def _batch_cancelled(self) -> None:
        self.status_label.setText(
            "Status: Batch konverzija je prekinuta."
        )

    def _batch_finished(
        self,
        success_count: int,
        failed_count: int,
        cancelled_count: int,
    ) -> None:
        self.cancel_requested = False
        self.progress_bar.setValue(100)
        self.status_label.setText(
            "Konverzija zavrsena:\n"
            f"- Uspjesno: {success_count}\n"
            f"- Neuspjesno: {failed_count}\n"
            f"- Prekinuto: {cancelled_count}"
        )
        self._set_conversion_running(False)

    def _thread_finished(self) -> None:
        self.cancel_requested = False
        self.batch_worker = None
        self.batch_thread = None
        self._batch_item_ids = []
        self._set_conversion_running(False)

    def _set_conversion_running(
        self,
        running: bool,
    ) -> None:
        self.is_converting = running
        self._update_controls()

    def _update_batch_progress(self) -> None:
        if not self._batch_item_ids:
            return

        batch_items = [
            item
            for item in self.items
            if item.unique_id in self._batch_item_ids
        ]

        if not batch_items:
            return

        total_progress = sum(item.progress for item in batch_items)
        self.progress_bar.setValue(
            int(total_progress / len(batch_items))
        )

    def _runnable_items(self) -> list[ConversionItem]:
        runnable_items: list[ConversionItem] = []

        for item in self.items:
            if not item.can_run_again:
                continue

            if item.output_format not in item.available_output_formats:
                continue

            runnable_items.append(item)

        return runnable_items

    def _active_item(self) -> ConversionItem | None:
        if self.active_item_id is None:
            return None

        return self._item_by_id(self.active_item_id)

    def _item_by_id(
        self,
        item_id: str | None,
    ) -> ConversionItem | None:
        if item_id is None:
            return None

        for item in self.items:
            if item.unique_id == item_id:
                return item

        return None

    @staticmethod
    def _set_combo_to_user_data(
        combo: QComboBox,
        value,
    ) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def closeEvent(self, event) -> None:
        if self.is_converting:
            QMessageBox.information(
                self,
                "Konverzija je u tijeku",
                (
                    "Pricekaj da trenutna konverzija zavrsi "
                    "ili je sigurno prekini."
                ),
            )
            event.ignore()
            return

        event.accept()
