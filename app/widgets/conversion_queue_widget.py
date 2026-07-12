from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.conversion_item import ConversionItem
from app.icon_provider import get_icon


class ConversionQueueWidget(QWidget):
    selection_changed = Signal(str)
    output_format_changed = Signal(str, str)
    remove_requested = Signal(str)

    COLUMN_NAME = 0
    COLUMN_INPUT = 1
    COLUMN_OUTPUT = 2
    COLUMN_STATUS = 3
    COLUMN_PROGRESS = 4
    COLUMN_RESULT = 5
    COLUMN_REMOVE = 6

    def __init__(self) -> None:
        super().__init__()
        self._updating = False
        self._items_by_id: dict[str, ConversionItem] = {}
        self._locked = False

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Naziv datoteke",
                "Ulazni format",
                "Izlazni format",
                "Status",
                "Napredak",
                "Rezultat ili greska",
                "Ukloni",
            ]
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(
            self._emit_selection_changed
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            self.COLUMN_NAME,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            self.COLUMN_INPUT,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            self.COLUMN_OUTPUT,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            self.COLUMN_STATUS,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            self.COLUMN_PROGRESS,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            self.COLUMN_RESULT,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            self.COLUMN_REMOVE,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def set_items(
        self,
        items: list[ConversionItem],
    ) -> None:
        current_item_id = self.current_item_id()
        self._items_by_id = {
            item.unique_id: item
            for item in items
        }

        self._updating = True
        self.table.setRowCount(0)

        for item in items:
            self._append_row(item)

        self._updating = False
        self.set_locked(self._locked)

        if current_item_id in self._items_by_id:
            self.set_current_item_id(current_item_id)
        elif items:
            self.set_current_item_id(items[0].unique_id)

    def update_item(
        self,
        item: ConversionItem,
    ) -> None:
        row = self._row_for_item_id(item.unique_id)

        if row is None:
            return

        self._updating = True
        self._set_text(row, self.COLUMN_STATUS, item.status.display_label)
        self._set_text(
            row,
            self.COLUMN_RESULT,
            self._result_text(item),
            self._result_detail(item),
        )

        progress_bar = self.table.cellWidget(
            row,
            self.COLUMN_PROGRESS,
        )
        if isinstance(progress_bar, QProgressBar):
            progress_bar.setValue(item.progress)

        combo = self.table.cellWidget(row, self.COLUMN_OUTPUT)
        if isinstance(combo, QComboBox):
            combo.setCurrentText(item.output_format)
            combo.setEnabled(not self._locked)

        remove_button = self.table.cellWidget(
            row,
            self.COLUMN_REMOVE,
        )
        if isinstance(remove_button, QPushButton):
            remove_button.setEnabled(not self._locked)

        self._updating = False

    def selected_item_ids(self) -> list[str]:
        item_ids: list[str] = []

        for index in self.table.selectionModel().selectedRows():
            item_id = self._item_id_for_row(index.row())

            if item_id is not None:
                item_ids.append(item_id)

        return item_ids

    def current_item_id(self) -> str | None:
        current_row = self.table.currentRow()

        if current_row < 0:
            return None

        return self._item_id_for_row(current_row)

    def set_current_item_id(
        self,
        item_id: str,
    ) -> None:
        row = self._row_for_item_id(item_id)

        if row is None:
            return

        self.table.selectRow(row)
        self.table.setCurrentCell(row, self.COLUMN_NAME)

    def set_locked(
        self,
        locked: bool,
    ) -> None:
        self._locked = locked

        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, self.COLUMN_OUTPUT)

            if isinstance(combo, QComboBox):
                combo.setEnabled(not locked)

            remove_button = self.table.cellWidget(
                row,
                self.COLUMN_REMOVE,
            )

            if isinstance(remove_button, QPushButton):
                remove_button.setEnabled(not locked)

    def _append_row(
        self,
        item: ConversionItem,
    ) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        name_item = self._create_text_item(item.input_path.name)
        name_item.setData(
            Qt.ItemDataRole.UserRole,
            item.unique_id,
        )
        name_item.setToolTip(str(item.input_path))
        self.table.setItem(row, self.COLUMN_NAME, name_item)

        self.table.setItem(
            row,
            self.COLUMN_INPUT,
            self._create_text_item(item.input_format),
        )

        output_combo = QComboBox()
        output_combo.addItems(item.available_output_formats)
        output_combo.setCurrentText(item.output_format)
        output_combo.currentTextChanged.connect(
            lambda value, item_id=item.unique_id: (
                self._handle_output_format_changed(
                    item_id,
                    value,
                )
            )
        )
        self.table.setCellWidget(
            row,
            self.COLUMN_OUTPUT,
            output_combo,
        )

        self.table.setItem(
            row,
            self.COLUMN_STATUS,
            self._create_text_item(item.status.display_label),
        )

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(item.progress)
        progress_bar.setTextVisible(True)
        self.table.setCellWidget(
            row,
            self.COLUMN_PROGRESS,
            progress_bar,
        )

        result_item = self._create_text_item(
            self._result_text(item)
        )
        result_item.setToolTip(self._result_detail(item))
        self.table.setItem(row, self.COLUMN_RESULT, result_item)

        remove_button = QPushButton("Ukloni")
        remove_button.setIcon(get_icon(self, "remove"))
        remove_button.setToolTip(
            "Uklanja ovu stavku dok grupna konverzija nije aktivna."
        )
        remove_button.clicked.connect(
            lambda checked=False, item_id=item.unique_id: (
                self.remove_requested.emit(item_id)
            )
        )
        self.table.setCellWidget(
            row,
            self.COLUMN_REMOVE,
            remove_button,
        )

    def _handle_output_format_changed(
        self,
        item_id: str,
        output_format: str,
    ) -> None:
        if self._updating:
            return

        self.output_format_changed.emit(
            item_id,
            output_format,
        )

    def _emit_selection_changed(self) -> None:
        if self._updating:
            return

        item_id = self.current_item_id()

        if item_id is not None:
            self.selection_changed.emit(item_id)

    def _row_for_item_id(
        self,
        item_id: str,
    ) -> int | None:
        for row in range(self.table.rowCount()):
            if self._item_id_for_row(row) == item_id:
                return row

        return None

    def _item_id_for_row(
        self,
        row: int,
    ) -> str | None:
        item = self.table.item(row, self.COLUMN_NAME)

        if item is None:
            return None

        item_id = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(item_id, str):
            return item_id

        return None

    def _set_text(
        self,
        row: int,
        column: int,
        text: str,
        tooltip: str | None = None,
    ) -> None:
        item = self.table.item(row, column)

        if item is None:
            item = self._create_text_item(text)
            self.table.setItem(row, column, item)
        else:
            item.setText(text)

        item.setToolTip(tooltip if tooltip is not None else text)

    @staticmethod
    def _create_text_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(
            item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
        )
        return item

    @staticmethod
    def _result_text(item: ConversionItem) -> str:
        if item.result_path is not None:
            return item.result_path.name

        if item.error_message:
            return _short_message(item.error_message)

        if item.status_message:
            return _short_message(item.status_message)

        return ""

    @staticmethod
    def _result_detail(item: ConversionItem) -> str:
        if item.result_path is not None:
            return str(item.result_path)

        if item.error_message:
            return item.error_message

        if item.status_message:
            return item.status_message

        return ""


def _short_message(message: str) -> str:
    first_line = message.strip().splitlines()[0] if message.strip() else ""

    if len(first_line) <= 120:
        return first_line

    return f"{first_line[:117]}..."
