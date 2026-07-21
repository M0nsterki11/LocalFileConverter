"""Card-based queue widgets for viewing and selecting conversion items."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.constants import IMAGE_EXTENSIONS, OFFICE_EXTENSIONS, PDF_EXTENSION
from app.conversion_item import ConversionItem, ConversionStatus
from app.icon_provider import get_icon
from utils.output_safety import human_readable_size


QUEUE_VISIBLE_CARD_LIMIT = 3


class ElidedLabel(QLabel):
    """Display one elided line while retaining the complete tooltip text."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._full_text = ""
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.setMinimumWidth(0)
        self.set_full_text(text)

    def set_full_text(
        self,
        text: str,
        tooltip: str | None = None,
    ) -> None:
        """Set display text and preserve its complete value in a tooltip."""
        self._full_text = text
        self.setToolTip(tooltip if tooltip is not None else text)
        self._update_elided_text()

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        available_width = max(0, self.contentsRect().width())
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )
        )


class ConversionItemCard(QFrame):
    """Present one conversion request and its interactive queue controls."""

    activated = Signal(str)
    selection_toggled = Signal(str, bool)
    output_format_changed = Signal(str, str)
    remove_requested = Signal(str)

    def __init__(self, item: ConversionItem) -> None:
        super().__init__()
        self.item_id = item.unique_id
        self._updating = False
        self.setObjectName("conversionItemCard")
        self.setProperty("selected", False)
        self.setProperty("active", False)
        self.setMinimumHeight(120)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.selection_checkbox = QCheckBox()
        self.selection_checkbox.setObjectName("queueItemCheckbox")
        self.selection_checkbox.toggled.connect(
            self._selection_changed
        )

        self.icon_label = QLabel()
        self.icon_label.setObjectName("queueItemIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(44, 44)

        self.name_label = ElidedLabel()
        self.name_label.setObjectName("queueItemName")

        self.metadata_label = QLabel()
        self.metadata_label.setObjectName("queueItemMetadata")

        self.result_label = ElidedLabel()
        self.result_label.setObjectName("queueItemResult")

        self.output_caption = QLabel()
        self.output_caption.setObjectName("queueItemCaption")
        self.output_combo = QComboBox()
        self.output_combo.setObjectName("queueItemOutputCombo")
        self.output_combo.setMinimumWidth(150)
        self.output_combo.setMinimumHeight(40)
        self.output_combo.currentTextChanged.connect(
            self._output_format_selected
        )

        self.status_caption = QLabel()
        self.status_caption.setObjectName("queueItemCaption")
        self.status_label = QLabel()
        self.status_label.setObjectName("queueItemStatus")

        self.remove_button = QPushButton()
        self.remove_button.setObjectName("itemRemoveButton")
        self.remove_button.setIcon(
            get_icon(self.remove_button, "remove")
        )
        self.remove_button.setIconSize(QSize(18, 18))
        self.remove_button.setFixedSize(38, 38)
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(self.item_id)
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("itemProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)
        layout.addWidget(
            self.selection_checkbox,
            0,
            0,
            3,
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(
            self.icon_label,
            0,
            1,
            3,
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.name_label, 0, 2)
        layout.addWidget(self.metadata_label, 1, 2)
        layout.addWidget(self.result_label, 2, 2, 1, 3)
        layout.addWidget(self.output_caption, 0, 3)
        layout.addWidget(self.output_combo, 1, 3)
        layout.addWidget(self.status_caption, 0, 4)
        layout.addWidget(self.status_label, 1, 4)
        layout.addWidget(
            self.remove_button,
            0,
            5,
            2,
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        layout.addWidget(self.progress_bar, 3, 2, 1, 3)
        layout.setColumnStretch(2, 1)
        layout.setColumnMinimumWidth(3, 150)
        layout.setColumnMinimumWidth(4, 106)

        for widget in (
            self.icon_label,
            self.name_label,
            self.metadata_label,
            self.result_label,
            self.output_caption,
            self.status_caption,
            self.status_label,
            self.progress_bar,
        ):
            widget.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )

        self.retranslate_ui()
        self.update_item(item)

    def retranslate_ui(self) -> None:
        """Refresh static labels after a runtime language change."""
        self.output_caption.setText(self.tr("Convert to"))
        self.status_caption.setText(self.tr("Status"))
        self.selection_checkbox.setToolTip(
            self.tr("Select item for bulk actions")
        )
        self.selection_checkbox.setAccessibleName(
            self.tr("Select item")
        )
        self.remove_button.setToolTip(self.tr("Remove item"))
        self.remove_button.setAccessibleName(self.tr("Remove item"))

    def update_item(self, item: ConversionItem) -> None:
        """Refresh all data-driven controls from a conversion item."""
        self.item_id = item.unique_id
        self._input_path = item.input_path
        self._updating = True
        self.name_label.set_full_text(
            item.input_path.name,
            tooltip=str(item.input_path),
        )
        self.metadata_label.setText(self._metadata_text(item))
        self._set_file_icon(item.input_path)

        available_formats = item.available_output_formats
        if [
            self.output_combo.itemText(index)
            for index in range(self.output_combo.count())
        ] != available_formats:
            self.output_combo.clear()
            self.output_combo.addItems(available_formats)

        self.output_combo.setCurrentText(item.output_format)
        self.status_label.setText(item.status.display_label)
        self.status_label.setProperty("status", item.status.value)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        result_text = _result_text(item)
        self.result_label.set_full_text(
            result_text,
            tooltip=_result_detail(item),
        )
        self.result_label.setVisible(bool(result_text))

        self.progress_bar.setValue(item.progress)
        self.progress_bar.setVisible(
            item.status == ConversionStatus.CONVERTING
        )
        self._updating = False

    def refresh_icons(self) -> None:
        """Re-render card icons after the application theme changes."""
        self.remove_button.setIcon(
            get_icon(self.remove_button, "remove")
        )
        self._set_file_icon(self._input_path)

    def is_selected(self) -> bool:
        """Return whether this item is checked for a bulk action."""
        return self.selection_checkbox.isChecked()

    def set_selected(self, selected: bool) -> None:
        """Set checkbox selection without emitting a user action."""
        previous = self.selection_checkbox.blockSignals(True)
        self.selection_checkbox.setChecked(selected)
        self.selection_checkbox.blockSignals(previous)
        self._apply_boolean_property("selected", selected)

    def set_active(self, active: bool) -> None:
        """Visually identify the item shown in the advanced options panel."""
        self._apply_boolean_property("active", active)

    def set_locked(self, locked: bool) -> None:
        """Disable queue editing controls while conversion is active."""
        self.selection_checkbox.setEnabled(not locked)
        self.output_combo.setEnabled(not locked)
        self.remove_button.setEnabled(not locked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.item_id)

        super().mousePressEvent(event)

    def _selection_changed(self, selected: bool) -> None:
        self._apply_boolean_property("selected", selected)
        self.selection_toggled.emit(self.item_id, selected)

    def _output_format_selected(self, output_format: str) -> None:
        if not self._updating and output_format:
            self.output_format_changed.emit(
                self.item_id,
                output_format,
            )

    def _set_file_icon(self, path: Path) -> None:
        icon = get_icon(
            self.icon_label,
            _icon_name_for_path(path),
        )
        self.icon_label.setPixmap(icon.pixmap(QSize(36, 36)))

    def _apply_boolean_property(self, name: str, enabled: bool) -> None:
        if self.property(name) == enabled:
            return

        self.setProperty(name, enabled)
        self.style().unpolish(self)
        self.style().polish(self)

    @staticmethod
    def _metadata_text(item: ConversionItem) -> str:
        details = [item.input_format]

        try:
            details.append(
                human_readable_size(item.input_path.stat().st_size)
            )
        except OSError:
            pass

        return " | ".join(details)


class ConversionQueueWidget(QWidget):
    """Manage conversion item cards while preserving the queue UI contract."""

    selection_changed = Signal(str)
    selection_state_changed = Signal()
    output_format_changed = Signal(str, str)
    remove_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._updating = False
        self._items_by_id: dict[str, ConversionItem] = {}
        self._cards_by_id: dict[str, ConversionItemCard] = {}
        self._current_item_id: str | None = None
        self._locked = False

        self.items_container = QWidget()
        self.items_container.setObjectName("queueItemsContainer")
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(2, 2, 2, 2)
        self.items_layout.setSpacing(10)
        self.items_layout.addStretch()

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("queueScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setWidget(self.items_container)
        self.scroll_area.setFixedHeight(124)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def retranslate_ui(self) -> None:
        """Refresh card labels after a runtime language change."""
        for card in self._cards_by_id.values():
            card.retranslate_ui()
            item = self._items_by_id.get(card.item_id)

            if item is not None:
                card.update_item(item)

        self._update_scroll_area_height()

    def refresh_icons(self) -> None:
        """Re-render all visible card icons for the active theme."""
        for card in self._cards_by_id.values():
            card.refresh_icons()

    def set_items(
        self,
        items: list[ConversionItem],
    ) -> None:
        """Replace cards while preserving active and checked item IDs."""
        selected_ids = set(self.selected_item_ids())
        current_item_id = self._current_item_id
        self._updating = True

        for card in self._cards_by_id.values():
            self.items_layout.removeWidget(card)
            card.deleteLater()

        self._items_by_id = {
            item.unique_id: item
            for item in items
        }
        self._cards_by_id = {}

        for item in items:
            card = ConversionItemCard(item)
            card.activated.connect(self.set_current_item_id)
            card.selection_toggled.connect(
                self._card_selection_toggled
            )
            card.output_format_changed.connect(
                self.output_format_changed.emit
            )
            card.remove_requested.connect(self.remove_requested.emit)
            card.set_selected(item.unique_id in selected_ids)
            card.set_locked(self._locked)
            self.items_layout.insertWidget(
                self.items_layout.count() - 1,
                card,
            )
            self._cards_by_id[item.unique_id] = card

        self._current_item_id = None
        self._updating = False

        if current_item_id in self._cards_by_id:
            self.set_current_item_id(current_item_id)
        elif items:
            self.set_current_item_id(items[0].unique_id)

        self._update_scroll_area_height()
        self.selection_state_changed.emit()

    def update_item(
        self,
        item: ConversionItem,
    ) -> None:
        """Refresh the card associated with one conversion item."""
        self._items_by_id[item.unique_id] = item
        card = self._cards_by_id.get(item.unique_id)

        if card is not None:
            card.update_item(item)
            self._update_scroll_area_height()

    def _update_scroll_area_height(self) -> None:
        cards = list(self._cards_by_id.values())
        visible_cards = cards[:QUEUE_VISIBLE_CARD_LIMIT]

        if not visible_cards:
            self.items_container.setMinimumHeight(0)
            self.scroll_area.setFixedHeight(124)
            return

        self.items_layout.activate()
        margins = self.items_layout.contentsMargins()
        card_heights = [
            max(card.minimumHeight(), card.sizeHint().height())
            for card in cards
        ]
        content_height = (
            margins.top()
            + sum(card_heights)
            + self.items_layout.spacing() * (len(cards) - 1)
            + margins.bottom()
        )
        self.items_container.setMinimumHeight(content_height)
        visible_count = len(visible_cards)
        self.scroll_area.setFixedHeight(
            margins.top()
            + sum(card_heights[:visible_count])
            + self.items_layout.spacing() * (visible_count - 1)
            + margins.bottom()
        )

    def selected_item_ids(self) -> list[str]:
        """Return identifiers explicitly checked for bulk actions."""
        return [
            item_id
            for item_id, card in self._cards_by_id.items()
            if card.is_selected()
        ]

    def current_item_id(self) -> str | None:
        """Return the item currently shown in the details controls."""
        return self._current_item_id

    def set_current_item_id(
        self,
        item_id: str,
    ) -> None:
        """Activate a card without changing its bulk-selection checkbox."""
        if item_id not in self._cards_by_id:
            return

        changed = item_id != self._current_item_id
        self._current_item_id = item_id

        for card_id, card in self._cards_by_id.items():
            card.set_active(card_id == item_id)

        self.scroll_area.ensureWidgetVisible(
            self._cards_by_id[item_id],
            16,
            16,
        )

        if changed and not self._updating:
            self.selection_changed.emit(item_id)

    def set_item_selected(
        self,
        item_id: str,
        selected: bool,
    ) -> None:
        """Set an item's bulk-selection state programmatically."""
        card = self._cards_by_id.get(item_id)

        if card is None:
            return

        card.set_selected(selected)
        self.selection_state_changed.emit()

    def set_locked(
        self,
        locked: bool,
    ) -> None:
        """Prevent card editing while a batch is running."""
        self._locked = locked

        for card in self._cards_by_id.values():
            card.set_locked(locked)

    def _card_selection_toggled(
        self,
        item_id: str,
        selected: bool,
    ) -> None:
        if self._updating:
            return

        if selected:
            self.set_current_item_id(item_id)

        self.selection_state_changed.emit()


def _icon_name_for_path(path: Path) -> str:
    extension = path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension == PDF_EXTENSION:
        return "pdf"

    if extension in OFFICE_EXTENSIONS:
        return "office"

    return "file"


def _result_text(item: ConversionItem) -> str:
    if item.result_path is not None:
        return item.result_path.name

    if item.error_message:
        return _short_message(item.error_message)

    if item.status_message:
        return _short_message(item.status_message)

    return ""


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
