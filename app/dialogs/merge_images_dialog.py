from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.constants import IMAGE_EXTENSIONS
from app.conversion_item import normalize_input_path
from converters.base_converter import ConversionCancelledError
from converters.pdf_converter import convert_images_to_pdf
from utils.file_utils import get_default_output_directory


class MergeImagesWorker(QObject):
    progress_changed = Signal(int)
    status_changed = Signal(str)
    merge_finished = Signal(str)
    merge_failed = Signal(str)
    merge_cancelled = Signal(str)

    def __init__(
        self,
        image_paths: list[Path],
        output_directory: Path,
        output_filename: str,
    ) -> None:
        super().__init__()
        self.image_paths = image_paths
        self.output_directory = output_directory
        self.output_filename = output_filename
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(self) -> None:
        try:
            result_path = convert_images_to_pdf(
                input_files=self.image_paths,
                output_directory=self.output_directory,
                output_filename=self.output_filename,
                cancel_check=self.is_cancelled,
                progress_callback=self.progress_changed.emit,
                status_callback=self.status_changed.emit,
            )
            self.merge_finished.emit(str(result_path))

        except ConversionCancelledError as error:
            self.merge_cancelled.emit(str(error))

        except Exception as error:
            self.merge_failed.emit(
                str(error) or error.__class__.__name__
            )


class MergeImagesDialog(QDialog):
    def __init__(
        self,
        output_directory: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Spoji slike u jedan PDF")
        self.resize(760, 560)

        self.image_paths: list[Path] = []
        self.output_directory = (
            output_directory
            if output_directory is not None
            else get_default_output_directory()
        )
        self.thread: QThread | None = None
        self.worker: MergeImagesWorker | None = None
        self.is_running = False

        self._build_ui()
        self._connect_signals()
        self._refresh_table()
        self._update_output_directory_label()
        self._update_controls()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            ["Redoslijed", "Slika"]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root_layout.addWidget(self.table)

        list_button_layout = QHBoxLayout()
        self.add_button = QPushButton("Dodaj slike")
        self.move_up_button = QPushButton("Gore")
        self.move_down_button = QPushButton("Dolje")
        self.remove_button = QPushButton("Ukloni")
        self.clear_button = QPushButton("Ocisti listu")

        for button in (
            self.add_button,
            self.move_up_button,
            self.move_down_button,
            self.remove_button,
            self.clear_button,
        ):
            list_button_layout.addWidget(button)

        root_layout.addLayout(list_button_layout)

        options_layout = QGridLayout()
        options_layout.setHorizontalSpacing(12)
        options_layout.setVerticalSpacing(10)

        self.output_directory_label = QLabel()
        self.output_directory_label.setObjectName("pathLabel")
        self.output_directory_label.setWordWrap(True)
        self.select_output_button = QPushButton("Promijeni mapu")

        self.filename_input = QLineEdit("combined.pdf")
        self.filename_input.setMinimumHeight(34)

        options_layout.addWidget(QLabel("Izlazna mapa:"), 0, 0)
        options_layout.addWidget(
            self.output_directory_label,
            0,
            1,
        )
        options_layout.addWidget(
            self.select_output_button,
            0,
            2,
        )
        options_layout.addWidget(QLabel("Naziv PDF-a:"), 1, 0)
        options_layout.addWidget(
            self.filename_input,
            1,
            1,
            1,
            2,
        )
        options_layout.setColumnStretch(1, 1)
        root_layout.addLayout(options_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        root_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(
            "Status: Dodaj najmanje dvije slike."
        )
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.start_button = QPushButton("Spoji u PDF")
        self.start_button.setObjectName("convertButton")
        self.cancel_button = QPushButton("PREKINI")
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setEnabled(False)
        self.close_button = QPushButton("Zatvori")

        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.cancel_button)
        action_layout.addWidget(self.close_button)
        root_layout.addLayout(action_layout)

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self._add_images)
        self.move_up_button.clicked.connect(self._move_selected_up)
        self.move_down_button.clicked.connect(
            self._move_selected_down
        )
        self.remove_button.clicked.connect(
            self._remove_selected
        )
        self.clear_button.clicked.connect(self._clear_images)
        self.select_output_button.clicked.connect(
            self._select_output_directory
        )
        self.start_button.clicked.connect(self._start_merge)
        self.cancel_button.clicked.connect(self._cancel_merge)
        self.close_button.clicked.connect(self.close)
        self.table.itemSelectionChanged.connect(
            self._update_controls
        )

    def _add_images(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Odaberi slike",
            "",
            "Slike (*.jpg *.jpeg *.png *.webp);;Sve datoteke (*.*)",
        )

        if not file_paths:
            return

        known_paths = {
            normalize_input_path(path)
            for path in self.image_paths
        }
        skipped_count = 0

        for file_path in file_paths:
            path = Path(file_path)

            if (
                not path.is_file()
                or path.suffix.lower() not in IMAGE_EXTENSIONS
            ):
                skipped_count += 1
                continue

            normalized_path = normalize_input_path(path)

            if normalized_path in known_paths:
                skipped_count += 1
                continue

            self.image_paths.append(path)
            known_paths.add(normalized_path)

        self._refresh_table()
        self._update_controls()

        if skipped_count:
            QMessageBox.information(
                self,
                "Neke slike su preskocene",
                f"Preskoceno stavki: {skipped_count}",
            )

    def _move_selected_up(self) -> None:
        row = self.table.currentRow()

        if row <= 0:
            return

        self.image_paths[row - 1], self.image_paths[row] = (
            self.image_paths[row],
            self.image_paths[row - 1],
        )
        self._refresh_table()
        self.table.selectRow(row - 1)

    def _move_selected_down(self) -> None:
        row = self.table.currentRow()

        if row < 0 or row >= len(self.image_paths) - 1:
            return

        self.image_paths[row + 1], self.image_paths[row] = (
            self.image_paths[row],
            self.image_paths[row + 1],
        )
        self._refresh_table()
        self.table.selectRow(row + 1)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()

        if row < 0:
            return

        del self.image_paths[row]
        self._refresh_table()

        if self.image_paths:
            self.table.selectRow(min(row, len(self.image_paths) - 1))

        self._update_controls()

    def _clear_images(self) -> None:
        self.image_paths.clear()
        self._refresh_table()
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

    def _start_merge(self) -> None:
        if self.is_running:
            return

        if len(self.image_paths) < 2:
            QMessageBox.warning(
                self,
                "Nedostaju slike",
                "Odaberi najmanje dvije slike.",
            )
            return

        output_filename = self.filename_input.text().strip()

        if not output_filename:
            output_filename = "combined.pdf"

        self.is_running = True
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Pokretanje spajanja...")
        self._update_controls()

        self.thread = QThread(self)
        self.worker = MergeImagesWorker(
            image_paths=list(self.image_paths),
            output_directory=self.output_directory,
            output_filename=output_filename,
        )
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress_changed.connect(
            self.progress_bar.setValue
        )
        self.worker.status_changed.connect(
            self._show_worker_status
        )
        self.worker.merge_finished.connect(self._merge_finished)
        self.worker.merge_failed.connect(self._merge_failed)
        self.worker.merge_cancelled.connect(
            self._merge_cancelled
        )

        self.worker.merge_finished.connect(self.thread.quit)
        self.worker.merge_failed.connect(self.thread.quit)
        self.worker.merge_cancelled.connect(self.thread.quit)
        self.worker.merge_finished.connect(self.worker.deleteLater)
        self.worker.merge_failed.connect(self.worker.deleteLater)
        self.worker.merge_cancelled.connect(
            self.worker.deleteLater
        )
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    def _cancel_merge(self) -> None:
        if self.worker is None:
            return

        self.cancel_button.setEnabled(False)
        self.status_label.setText("Status: Prekid spajanja...")
        self.worker.cancel()

    def _show_worker_status(self, message: str) -> None:
        self.status_label.setText(f"Status: {message}")

    def _merge_finished(self, result_path: str) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText(
            f"Status: Slike su spojene u PDF:\n{result_path}"
        )

    def _merge_failed(self, error_message: str) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Spajanje nije uspjelo.")
        QMessageBox.critical(
            self,
            "Greska spajanja",
            error_message,
        )

    def _merge_cancelled(self, message: str) -> None:
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Status: {message}")

    def _thread_finished(self) -> None:
        self.is_running = False
        self.worker = None
        self.thread = None
        self._update_controls()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)

        for index, path in enumerate(
            self.image_paths,
            start=1,
        ):
            row = self.table.rowCount()
            self.table.insertRow(row)
            order_item = QTableWidgetItem(str(index))
            order_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            self.table.setItem(row, 0, order_item)

            path_item = QTableWidgetItem(path.name)
            path_item.setToolTip(str(path))
            self.table.setItem(row, 1, path_item)

    def _update_output_directory_label(self) -> None:
        self.output_directory_label.setText(
            str(self.output_directory)
        )

    def _update_controls(self) -> None:
        row = self.table.currentRow()
        has_selection = row >= 0

        self.add_button.setEnabled(not self.is_running)
        self.move_up_button.setEnabled(
            not self.is_running and has_selection and row > 0
        )
        self.move_down_button.setEnabled(
            not self.is_running
            and has_selection
            and row < len(self.image_paths) - 1
        )
        self.remove_button.setEnabled(
            not self.is_running and has_selection
        )
        self.clear_button.setEnabled(
            not self.is_running and bool(self.image_paths)
        )
        self.select_output_button.setEnabled(not self.is_running)
        self.filename_input.setEnabled(not self.is_running)
        self.start_button.setEnabled(
            not self.is_running and len(self.image_paths) >= 2
        )
        self.cancel_button.setEnabled(self.is_running)
        self.close_button.setEnabled(not self.is_running)

    def closeEvent(self, event) -> None:
        if self.is_running:
            QMessageBox.information(
                self,
                "Spajanje je u tijeku",
                "Prvo prekini ili pricekaj zavrsetak spajanja.",
            )
            event.ignore()
            return

        event.accept()
