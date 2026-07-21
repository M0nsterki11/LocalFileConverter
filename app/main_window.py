"""Main window and top-level workflow coordination for the desktop app."""

from pathlib import Path
import time

from PySide6.QtCore import QPoint, QSize, QThread, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
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
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.batch_conversion_worker import BatchConversionWorker
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
from app.dialogs.about_dialog import AboutDialog
from app.dialogs.error_dialog import ErrorDetailsDialog
from app.dialogs.merge_images_dialog import MergeImagesDialog
from app.dialogs.settings_dialog import SettingsDialog
from app.icon_provider import get_app_icon, get_icon
from app.i18n import get_translation_manager
from app.settings import (
    AppSettings,
    get_window_geometry,
    get_window_state,
    get_saved_libreoffice_path,
    load_app_settings,
    save_app_settings,
    save_last_file_dialog_directory,
    save_libreoffice_path,
    save_window_geometry,
)
from app.theme_manager import ThemeManager
from app.widgets.file_drop_area import FileDropArea
from app.widgets.conversion_queue_widget import ConversionQueueWidget
from utils.file_utils import (
    open_directory,
)
from utils.error_handler import exception_to_error_info
from utils.format_utils import get_file_extension
from utils.libreoffice_utils import (
    find_libreoffice,
    get_default_libreoffice_browse_directory,
    is_valid_libreoffice_executable,
)
from utils.output_safety import (
    ensure_output_directory_ready,
    human_readable_size,
)


MAIN_CONTENT_MAX_WIDTH = 1200


class MainWindow(QMainWindow):
    """Coordinate the conversion queue, settings, dialogs, and worker thread."""

    def __init__(
        self,
        app_settings: AppSettings | None = None,
        theme_manager: ThemeManager | None = None,
    ) -> None:
        super().__init__()

        self.app_settings = (
            app_settings
            if app_settings is not None
            else load_app_settings()
        )
        self.theme_manager = (
            theme_manager
            if theme_manager is not None
            else ThemeManager()
        )
        self.items: list[ConversionItem] = []
        self.active_item_id: str | None = None
        self.output_directory = (
            self.app_settings.default_output_directory
        )

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
        self._batch_started_at: float | None = None
        self._closing_after_cancel = False
        self._batch_feedback_visible = False

        self.setWindowTitle(APP_NAME)
        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.resize(1080, 780)
        self.setMinimumSize(760, 560)

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self.retranslate_ui()
        get_translation_manager().language_changed.connect(
            self.retranslate_ui
        )
        self._update_output_directory_label()
        self._refresh_libreoffice_ui()
        self._load_active_item(None)
        self._restore_window_placement()
        self._update_controls()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
        )

        content_widget = QWidget()
        content_widget.setObjectName("mainContent")
        content_widget.setMaximumWidth(MAIN_CONTENT_MAX_WIDTH)
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area)

        self.main_scroll_area = scroll_area
        self.main_content_widget = content_widget

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        self.title_label = QLabel()
        self.title_label.setObjectName("mainTitle")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitle")
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.subtitle_label.setWordWrap(True)

        self.header_widget = QWidget()
        self.header_widget.setObjectName("appHeader")
        header_layout = QVBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 8, 0, 2)
        header_layout.setSpacing(4)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)
        main_layout.addWidget(self.header_widget)

        self.drop_area = FileDropArea()
        main_layout.addWidget(
            self.drop_area,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        list_button_layout = QGridLayout()
        list_button_layout.setHorizontalSpacing(10)
        list_button_layout.setVerticalSpacing(10)

        self.add_files_button = QPushButton()
        self.add_files_button.setMinimumHeight(40)
        self.remove_selected_button = QPushButton()
        self.remove_selected_button.setMinimumHeight(40)
        self.clear_list_button = QPushButton()
        self.clear_list_button.setMinimumHeight(40)
        self.retry_failed_button = QPushButton()
        self.retry_failed_button.setMinimumHeight(40)
        self.merge_images_button = QPushButton()
        self.merge_images_button.setMinimumHeight(40)
        self.settings_button = QPushButton()
        self.settings_button.setMinimumHeight(40)

        self.add_files_button.setProperty("actionRole", "primary")
        self.merge_images_button.setProperty("actionRole", "primary")

        self.list_button_layout = list_button_layout
        self.list_action_buttons = (
            self.add_files_button,
            self.merge_images_button,
            self.clear_list_button,
            self.settings_button,
            self.remove_selected_button,
            self.retry_failed_button,
        )
        self._list_action_columns = 0
        self._list_action_layout_key = None
        self._update_list_button_grid(self.width())

        main_layout.addLayout(list_button_layout)

        self.queue_group = QGroupBox()
        queue_layout = QVBoxLayout(self.queue_group)
        self.empty_queue_label = QLabel()
        self.empty_queue_label.setObjectName("emptyStateLabel")
        self.empty_queue_label.setWordWrap(True)
        self.queue_widget = ConversionQueueWidget()
        queue_layout.addWidget(self.empty_queue_label)
        queue_layout.addWidget(self.queue_widget)
        main_layout.addWidget(self.queue_group)

        self.advanced_options_button = QPushButton()
        self.advanced_options_button.setObjectName(
            "advancedOptionsButton"
        )
        self.advanced_options_button.setCheckable(True)
        self.advanced_options_button.setMinimumHeight(38)
        self.advanced_options_button.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        main_layout.addWidget(
            self.advanced_options_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        self.advanced_options_container = QWidget()
        self.advanced_options_container.setObjectName(
            "advancedOptionsContainer"
        )
        advanced_options_layout = QVBoxLayout(
            self.advanced_options_container
        )
        advanced_options_layout.setContentsMargins(0, 0, 0, 0)
        advanced_options_layout.setSpacing(12)
        self.advanced_options_container.hide()
        main_layout.addWidget(self.advanced_options_container)

        self.file_group = QGroupBox()
        file_layout = QGridLayout(self.file_group)
        file_layout.setHorizontalSpacing(16)
        file_layout.setVerticalSpacing(10)

        self.file_path_label = QLabel("-")
        self.file_path_label.setObjectName("pathLabel")
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.file_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.input_format_label = QLabel("-")
        self.input_format_label.setObjectName("valueLabel")

        self.file_path_title_label = QLabel()
        self.input_format_title_label = QLabel()
        self.file_size_title_label = QLabel()
        self.file_size_label = QLabel("-")
        self.file_size_label.setObjectName("valueLabel")

        file_layout.addWidget(self.file_path_title_label, 0, 0)
        file_layout.addWidget(self.file_path_label, 0, 1)
        file_layout.addWidget(self.input_format_title_label, 1, 0)
        file_layout.addWidget(self.input_format_label, 1, 1)
        file_layout.addWidget(self.file_size_title_label, 2, 0)
        file_layout.addWidget(self.file_size_label, 2, 1)
        file_layout.setColumnStretch(1, 1)
        advanced_options_layout.addWidget(self.file_group)

        self.conversion_group = QGroupBox()
        conversion_layout = QGridLayout(self.conversion_group)
        conversion_layout.setHorizontalSpacing(16)
        conversion_layout.setVerticalSpacing(12)

        # The queue card is the visible format selector. This synchronized
        # control keeps the existing item-settings signal flow intact.
        self.output_format_label = QLabel(self.conversion_group)
        self.output_format_combo = QComboBox(self.conversion_group)
        self.output_format_combo.setMinimumHeight(38)
        self.output_format_label.hide()
        self.output_format_combo.hide()

        self.quality_label = QLabel()
        self.quality_slider = QSlider(
            Qt.Orientation.Horizontal
        )
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(
            self.app_settings.default_image_quality
        )
        self.quality_slider.setSingleStep(1)
        self.quality_slider.setPageStep(5)

        self.quality_value_label = QLabel(
            f"{self.app_settings.default_image_quality}%"
        )
        self.quality_value_label.setMinimumWidth(45)
        self.quality_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.page_mode_label = QLabel()
        self.page_mode_combo = QComboBox()
        self.page_mode_combo.addItem(
            "",
            userData="all",
        )
        self.page_mode_combo.addItem(
            "",
            userData="selected",
        )
        self.page_mode_combo.setMinimumHeight(38)

        self.page_range_input = QLineEdit()
        self.page_range_input.setMinimumHeight(38)

        self.multi_page_output_label = QLabel()
        self.multi_page_output_combo = QComboBox()
        self.multi_page_output_combo.addItem(
            "",
            userData="folder",
        )
        self.multi_page_output_combo.addItem(
            "",
            userData="zip",
        )
        self._set_combo_to_user_data(
            self.multi_page_output_combo,
            self.app_settings.default_multi_page_output_mode,
        )
        self.multi_page_output_combo.setMinimumHeight(38)

        self.dpi_label = QLabel()
        self.dpi_combo = QComboBox()
        self.dpi_combo.addItem("96 DPI", userData=96)
        self.dpi_combo.addItem("150 DPI", userData=150)
        self.dpi_combo.addItem("200 DPI", userData=200)
        self.dpi_combo.addItem("300 DPI", userData=300)
        self._set_combo_to_user_data(
            self.dpi_combo,
            self.app_settings.default_pdf_dpi,
        )
        self.dpi_combo.setMinimumHeight(38)

        self.output_directory_title_label = QLabel()
        self.output_directory_title_label.setObjectName(
            "outputFolderCaption"
        )
        self.output_directory_label = QLabel()
        self.output_directory_label.setObjectName(
            "pathLabel"
        )
        self.output_directory_label.setWordWrap(True)
        self.output_directory_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.output_directory_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.select_output_button = QPushButton()
        self.select_output_button.setMinimumHeight(38)

        conversion_layout.addWidget(
            self.quality_label,
            0,
            0,
        )
        conversion_layout.addWidget(
            self.quality_slider,
            0,
            1,
        )
        conversion_layout.addWidget(
            self.quality_value_label,
            0,
            2,
        )
        conversion_layout.addWidget(
            self.page_mode_label,
            1,
            0,
        )
        conversion_layout.addWidget(
            self.page_mode_combo,
            1,
            1,
        )
        conversion_layout.addWidget(
            self.page_range_input,
            1,
            2,
        )
        conversion_layout.addWidget(
            self.multi_page_output_label,
            2,
            0,
        )
        conversion_layout.addWidget(
            self.multi_page_output_combo,
            2,
            1,
            1,
            2,
        )
        conversion_layout.addWidget(
            self.dpi_label,
            3,
            0,
        )
        conversion_layout.addWidget(
            self.dpi_combo,
            3,
            1,
            1,
            2,
        )
        conversion_layout.setColumnStretch(1, 1)
        advanced_options_layout.addWidget(self.conversion_group)

        self.output_group = QGroupBox()
        self.output_group.setObjectName("outputCard")
        output_layout = QGridLayout(self.output_group)
        output_layout.setHorizontalSpacing(16)
        output_layout.setVerticalSpacing(10)
        output_layout.addWidget(
            self.output_directory_title_label,
            0,
            0,
        )
        output_layout.addWidget(
            self.output_directory_label,
            0,
            1,
        )
        output_layout.addWidget(
            self.select_output_button,
            0,
            2,
        )
        output_layout.setColumnStretch(1, 1)
        main_layout.addWidget(self.output_group)

        self.libreoffice_group = QGroupBox()
        libreoffice_layout = QGridLayout(
            self.libreoffice_group
        )
        libreoffice_layout.setHorizontalSpacing(12)
        libreoffice_layout.setVerticalSpacing(10)

        self.libreoffice_path_input = QLineEdit()
        self.libreoffice_path_input.setReadOnly(True)
        self.libreoffice_path_input.setMinimumHeight(38)

        self.detect_libreoffice_button = QPushButton()
        self.detect_libreoffice_button.setMinimumHeight(38)

        self.select_libreoffice_button = QPushButton()
        self.select_libreoffice_button.setMinimumHeight(38)

        self.libreoffice_description = QLabel()
        self.libreoffice_description.setObjectName(
            "dropDescription"
        )
        self.libreoffice_description.setWordWrap(True)

        self.libreoffice_program_label = QLabel()
        libreoffice_layout.addWidget(
            self.libreoffice_program_label,
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
            self.libreoffice_description,
            2,
            0,
            1,
            3,
        )
        libreoffice_layout.setColumnStretch(1, 1)
        main_layout.addWidget(self.libreoffice_group)

        self.conversion_action_container = QWidget()
        self.conversion_action_container.setObjectName(
            "conversionActionContainer"
        )
        conversion_action_layout = QVBoxLayout(
            self.conversion_action_container
        )
        conversion_action_layout.setContentsMargins(0, 0, 0, 0)
        conversion_action_layout.setSpacing(8)

        self.status_panel = QFrame()
        self.status_panel.setObjectName("statusCard")
        status_panel_layout = QHBoxLayout(self.status_panel)
        status_panel_layout.setContentsMargins(14, 10, 14, 10)

        self.idle_status_label = QLabel()
        self.idle_status_label.setObjectName("idleStatusLabel")
        self.idle_status_label.setWordWrap(True)
        status_panel_layout.addWidget(self.idle_status_label)
        conversion_action_layout.addWidget(self.status_panel)

        self.convert_button = QPushButton()
        self.convert_button.setObjectName("convertButton")
        self.convert_button.setMinimumHeight(56)
        conversion_action_layout.addWidget(self.convert_button)
        main_layout.addWidget(self.conversion_action_container)

        self.progress_group = QGroupBox()
        progress_layout = QVBoxLayout(self.progress_group)
        progress_layout.setSpacing(10)

        progress_header_layout = QHBoxLayout()
        self.progress_summary_label = QLabel()
        self.progress_summary_label.setObjectName(
            "progressSummaryLabel"
        )
        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName(
            "progressPercentLabel"
        )
        self.progress_percent_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        progress_header_layout.addWidget(
            self.progress_summary_label,
            stretch=1,
        )
        progress_header_layout.addWidget(
            self.progress_percent_label
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.current_file_label = QLabel()
        self.current_file_label.setObjectName("currentFileLabel")
        self.current_file_label.setWordWrap(True)

        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.setMaximumWidth(210)
        self.cancel_button.setEnabled(False)

        self.status_label = QLabel()
        self.status_label.setObjectName("progressStatusLabel")
        self.status_label.setWordWrap(True)

        cancel_layout = QHBoxLayout()
        cancel_layout.addStretch()
        cancel_layout.addWidget(self.cancel_button)

        progress_layout.addLayout(progress_header_layout)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.current_file_label)
        progress_layout.addWidget(self.status_label)
        progress_layout.addLayout(cancel_layout)
        self.progress_group.hide()
        main_layout.addWidget(self.progress_group)

        self.open_output_button = QPushButton()
        self.open_output_button.setMinimumHeight(40)

        open_folder_layout = QHBoxLayout()
        open_folder_layout.addStretch()
        open_folder_layout.addWidget(
            self.open_output_button
        )
        open_folder_layout.addStretch()
        main_layout.addLayout(open_folder_layout)

        self._apply_icons_and_tooltips()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        self.file_menu = menu_bar.addMenu("")
        self.tools_menu = menu_bar.addMenu("")
        self.help_menu = menu_bar.addMenu("")

        self.add_files_action = QAction(
            get_icon(self, "add"),
            "",
            self,
        )
        self.add_files_action.setShortcut(QKeySequence("Ctrl+O"))
        self.add_files_action.triggered.connect(self._select_files)

        self.change_output_action = QAction(
            get_icon(self, "folder"),
            "",
            self,
        )
        self.change_output_action.triggered.connect(
            self._select_output_directory
        )

        self.exit_action = QAction(
            get_icon(self, "exit"),
            "",
            self,
        )
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.exit_action.triggered.connect(self.close)

        self.merge_images_action = QAction(
            get_icon(self, "merge"),
            "",
            self,
        )
        self.merge_images_action.triggered.connect(
            self._open_merge_images_dialog
        )

        self.settings_action = QAction(
            get_icon(self, "settings"),
            "",
            self,
        )
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(
            self._open_settings_dialog
        )

        self.about_action = QAction(
            get_icon(self, "about"),
            "",
            self,
        )
        self.about_action.setShortcut(QKeySequence("F1"))
        self.about_action.triggered.connect(self._open_about_dialog)

        self.file_menu.addAction(self.add_files_action)
        self.file_menu.addAction(self.change_output_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        self.tools_menu.addAction(self.merge_images_action)
        self.tools_menu.addAction(self.settings_action)

        self.help_menu.addAction(self.about_action)

    def _apply_icons_and_tooltips(self) -> None:
        icon_assignments = (
            (self.add_files_button, "add"),
            (self.remove_selected_button, "remove"),
            (self.clear_list_button, "clear"),
            (self.retry_failed_button, "convert"),
            (self.merge_images_button, "merge"),
            (self.settings_button, "settings"),
            (self.convert_button, "convert"),
            (self.cancel_button, "cancel"),
            (self.open_output_button, "folder"),
            (self.select_output_button, "folder"),
        )

        for button, icon_name in icon_assignments:
            button.setIcon(get_icon(button, icon_name))
            button.setIconSize(QSize(18, 18))

        action_assignments = (
            ("add_files_action", "add"),
            ("change_output_action", "folder"),
            ("exit_action", "exit"),
            ("merge_images_action", "merge"),
            ("settings_action", "settings"),
            ("about_action", "about"),
        )

        for attribute_name, icon_name in action_assignments:
            action = getattr(self, attribute_name, None)

            if action is not None:
                action.setIcon(get_icon(self, icon_name))

        self.drop_area.refresh_icons()
        self.queue_widget.refresh_icons()
        self._update_advanced_options_icon()

    def retranslate_ui(self, *_args) -> None:
        self.setWindowTitle(APP_NAME)
        self.title_label.setText(APP_NAME)
        self.subtitle_label.setText(
            self.tr("Convert files locally, without sending data to the internet")
        )

        self.add_files_button.setText(self.tr("Add files"))
        self.remove_selected_button.setText(self.tr("Remove selected"))
        self.clear_list_button.setText(self.tr("Clear all"))
        self.retry_failed_button.setText(self.tr("Retry failed"))
        self.merge_images_button.setText(self.tr("Merge images into one PDF"))
        self.settings_button.setText(self.tr("Settings"))

        self.queue_group.setTitle(self.tr("Files"))
        self.empty_queue_label.setText(
            self.tr("The list is empty. Add files or drop them into the application.")
        )
        self.advanced_options_button.setText(self.tr("Advanced options"))
        self.advanced_options_button.setToolTip(
            self.tr("Show or hide details and format-specific settings.")
        )
        self.file_group.setTitle(self.tr("File details"))
        self.file_path_title_label.setText(self.tr("Full path:"))
        self.input_format_title_label.setText(self.tr("Input format:"))
        self.file_size_title_label.setText(self.tr("Size:"))
        self.conversion_group.setTitle(self.tr("Format options"))
        self.quality_label.setText(self.tr("Quality:"))
        self.page_mode_label.setText(self.tr("PDF pages:"))
        self.page_mode_combo.setItemText(0, self.tr("All pages"))
        self.page_mode_combo.setItemText(1, self.tr("Selected pages"))
        self.page_range_input.setPlaceholderText(self.tr("Example: 1,3-5,8"))
        self.multi_page_output_label.setText(self.tr("Multiple PDF pages:"))
        self.multi_page_output_combo.setItemText(
            0,
            self.tr("Plain folder (default)"),
        )
        self.multi_page_output_combo.setItemText(1, self.tr("ZIP archive"))
        self.dpi_label.setText(self.tr("PDF DPI:"))
        self.output_group.setTitle(self.tr("Output"))
        self.output_directory_title_label.setText(self.tr("Output folder:"))
        self.select_output_button.setText(self.tr("Change folder"))

        self.libreoffice_group.setTitle(self.tr("Office conversion"))
        self.libreoffice_program_label.setText(self.tr("Program:"))
        self.detect_libreoffice_button.setText(self.tr("Detect automatically"))
        self.select_libreoffice_button.setText(self.tr("Choose soffice.exe"))
        self.libreoffice_description.setText(
            self.tr(
                "Office documents can be converted using Microsoft Office or "
                "LibreOffice. The LibreOffice path is saved for fallback use."
            )
        )

        self._update_convert_button_text()
        self.cancel_button.setText(self.tr("Cancel conversion"))
        self.progress_group.setTitle(self.tr("Progress"))
        self.open_output_button.setText(self.tr("Open output folder"))

        self.file_menu.setTitle(self.tr("File"))
        self.tools_menu.setTitle(self.tr("Tools"))
        self.help_menu.setTitle(self.tr("Help"))
        self.add_files_action.setText(self.tr("Add files"))
        self.change_output_action.setText(self.tr("Change output folder"))
        self.exit_action.setText(self.tr("Exit"))
        self.merge_images_action.setText(self.tr("Merge images into one PDF"))
        self.settings_action.setText(self.tr("Settings"))
        self.about_action.setText(self.tr("About"))

        self.quality_slider.setToolTip(
            self.tr("JPG/WEBP output quality for the selected item.")
        )
        self.dpi_combo.setToolTip(
            self.tr("Higher DPI creates more detailed images and larger files.")
        )
        self.multi_page_output_combo.setToolTip(
            self.tr(
                "Plain folder or ZIP for PDFs with multiple pages. Above 100 MB, ZIP is created automatically."
            )
        )
        self.cancel_button.setToolTip(
            self.tr("Safely cancels the active batch conversion.")
        )
        self.merge_images_button.setToolTip(
            self.tr(
                "Merges selected images into one PDF, separately from batch conversion."
            )
        )
        self.retry_failed_button.setToolTip(
            self.tr("Returns failed items to the queue for another run.")
        )
        self.remove_selected_button.setToolTip(
            self.tr("Removes selected items while batch conversion is not active.")
        )
        self.libreoffice_path_input.setToolTip(
            self.tr("Path to the LibreOffice soffice.exe program.")
        )

        self.drop_area.retranslate_ui()
        self.queue_widget.retranslate_ui()

        if not self.is_converting and not self.items:
            self._set_status_message(
                self.tr("Status: Add files to start.")
            )

        if self.libreoffice_path is None:
            self.libreoffice_path_input.setPlaceholderText(
                self.tr("LibreOffice was not found")
            )

    def _connect_signals(self) -> None:
        self.add_files_button.clicked.connect(
            self._select_files
        )
        self.drop_area.choose_files_requested.connect(
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
        self.settings_button.clicked.connect(
            self._open_settings_dialog
        )
        self.queue_widget.selection_changed.connect(
            self._queue_selection_changed
        )
        self.queue_widget.selection_state_changed.connect(
            self._update_controls
        )
        self.queue_widget.output_format_changed.connect(
            self._queue_output_format_changed
        )
        self.queue_widget.remove_requested.connect(
            self._remove_item_by_id
        )
        self.advanced_options_button.toggled.connect(
            self._toggle_advanced_options
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
            self.tr("Choose files"),
            str(self.app_settings.last_file_dialog_directory),
            self.tr(FILE_DIALOG_FILTER),
        )

        if file_paths:
            save_last_file_dialog_directory(file_paths[0])
            self.app_settings.last_file_dialog_directory = (
                Path(file_paths[0]).parent
            )

        self._add_files(file_paths)

    def _add_files(self, file_paths: list[str]) -> None:
        if self.is_converting or not file_paths:
            return

        result = build_unique_supported_items(
            file_paths=file_paths,
            existing_items=self.items,
            output_directory=self.output_directory,
            office_engine=self.app_settings.default_office_engine,
            quality=self.app_settings.default_image_quality,
            dpi=self.app_settings.default_pdf_dpi,
            multi_page_output_mode=(
                self.app_settings.default_multi_page_output_mode
            ),
        )

        self.items.extend(result.added_items)
        self.queue_widget.set_items(self.items)
        self._refresh_drop_area()

        if result.added_items:
            self.queue_widget.set_current_item_id(
                result.added_items[0].unique_id
            )
            self._set_status_message(
                self.tr("Status: Added items: {count}").format(
                    count=len(result.added_items),
                )
            )

        skipped_count = (
            len(result.unsupported_paths)
            + len(result.duplicate_paths)
        )

        if skipped_count:
            QMessageBox.information(
                self,
                self.tr("Some files were skipped"),
                (
                    self.tr(
                        "Skipped items: {skipped}\n"
                        "Unsupported: {unsupported}\n"
                        "Duplicates: {duplicates}"
                    ).format(
                        skipped=skipped_count,
                        unsupported=len(result.unsupported_paths),
                        duplicates=len(result.duplicate_paths),
                    )
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
        self._refresh_drop_area()
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
        self._refresh_drop_area()
        self._load_active_item(self.queue_widget.current_item_id())
        self._update_controls()

    def _clear_items(self) -> None:
        if self.is_converting:
            return

        self.items.clear()
        self.queue_widget.set_items(self.items)
        self._refresh_drop_area()
        self._load_active_item(None)
        self.progress_bar.setValue(0)
        self._set_status_message(
            self.tr("Status: The list was cleared.")
        )
        self._update_controls()

    def _retry_failed_items(self) -> None:
        if self.is_converting:
            return

        for item in self.items:
            if item.status == ConversionStatus.FAILED:
                item.mark_pending_for_run(self.output_directory)
                self.queue_widget.update_item(item)

        self._update_controls()

    def _refresh_drop_area(self) -> None:
        self.drop_area.set_files(
            [item.input_path for item in self.items]
        )

    def _update_list_button_grid(self, available_width: int) -> None:
        column_count = 2 if available_width < 900 else 3
        contextual_buttons = {
            self.remove_selected_button,
            self.retry_failed_button,
        }

        for button in self.list_action_buttons:
            if button not in contextual_buttons:
                button.setVisible(True)

        visible_buttons = tuple(
            button
            for button in self.list_action_buttons
            if (
                button not in contextual_buttons
                or not button.isHidden()
            )
        )
        layout_key = (
            column_count,
            tuple(id(button) for button in visible_buttons),
        )

        if layout_key == self._list_action_layout_key:
            return

        for button in self.list_action_buttons:
            self.list_button_layout.removeWidget(button)

        for index, button in enumerate(visible_buttons):
            self.list_button_layout.addWidget(
                button,
                index // column_count,
                index % column_count,
            )

        for column in range(3):
            self.list_button_layout.setColumnStretch(
                column,
                1 if column < column_count else 0,
            )

        self._list_action_columns = column_count
        self._list_action_layout_key = layout_key

    def _open_merge_images_dialog(self) -> None:
        dialog = MergeImagesDialog(
            output_directory=self.output_directory,
            parent=self,
        )
        dialog.exec()

    def _open_settings_dialog(self) -> None:
        if self.is_converting:
            QMessageBox.information(
                self,
                self.tr("Conversion is running"),
                self.tr(
                    "Settings cannot be changed while batch conversion is running."
                ),
            )
            return

        dialog = SettingsDialog(
            app_settings=self.app_settings,
            libreoffice_path=self.libreoffice_path,
            parent=self,
        )

        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        self.app_settings = dialog.app_settings
        self.libreoffice_path = dialog.libreoffice_path
        save_app_settings(self.app_settings)

        app = QApplication.instance()

        if isinstance(app, QApplication):
            self.theme_manager.apply_theme(
                app,
                self.app_settings.theme,
            )
            self._apply_icons_and_tooltips()

        self.output_directory = (
            self.app_settings.default_output_directory
        )
        self._update_output_directory_label()

        for item in self.items:
            if item.status == ConversionStatus.PENDING:
                item.output_directory = self.output_directory

        self._refresh_libreoffice_ui()
        self._set_status_message(
            self.tr("Status: Settings were saved.")
        )

    def _open_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def _load_active_item(
        self,
        item_id: str | None,
    ) -> None:
        item = self._item_by_id(item_id) if item_id else None
        self.active_item_id = item.unique_id if item else None
        self._loading_item_controls = True

        if item is None:
            self.file_path_label.setText("-")
            self.file_path_label.setToolTip("")
            self.input_format_label.setText("-")
            self.file_size_label.setText("-")
            self.output_format_combo.clear()
            self.quality_slider.setValue(
                self.app_settings.default_image_quality
            )
            self.page_mode_combo.setCurrentIndex(0)
            self.page_range_input.clear()
            self.quality_value_label.setText(
                f"{self.app_settings.default_image_quality}%"
            )
            self._set_combo_to_user_data(
                self.dpi_combo,
                self.app_settings.default_pdf_dpi,
            )
            self._set_combo_to_user_data(
                self.multi_page_output_combo,
                self.app_settings.default_multi_page_output_mode,
            )
        else:
            self.file_path_label.setText(str(item.input_path))
            self.file_path_label.setToolTip(str(item.input_path))
            self.input_format_label.setText(item.input_format)
            try:
                file_size = human_readable_size(
                    item.input_path.stat().st_size
                )
            except OSError:
                file_size = "-"
            self.file_size_label.setText(file_size)

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

    def _toggle_advanced_options(self, expanded: bool) -> None:
        has_active = self._active_item() is not None
        self.advanced_options_container.setVisible(
            expanded and has_active
        )
        self._update_advanced_options_icon()

    def _update_advanced_options_icon(self) -> None:
        icon_name = (
            "up" if self.advanced_options_button.isChecked() else "down"
        )
        self.advanced_options_button.setIcon(
            get_icon(self.advanced_options_button, icon_name)
        )
        self.advanced_options_button.setIconSize(QSize(18, 18))

    def _select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Choose output folder"),
            str(self.output_directory),
        )

        if not selected_directory:
            return

        self.output_directory = Path(selected_directory)
        self.app_settings.default_output_directory = (
            self.output_directory
        )
        save_app_settings(self.app_settings)
        self._update_output_directory_label()

        for item in self.items:
            if item.status == ConversionStatus.PENDING:
                item.output_directory = self.output_directory

        self._set_status_message(
            self.tr("Status: Output folder was changed.")
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
                    self.tr("Windows could not open the folder.")
                )

        except (OSError, RuntimeError) as error:
            QMessageBox.critical(
                self,
                self.tr("Folder open error"),
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
            item.dpi = int(
                self.dpi_combo.currentData()
                or self.app_settings.default_pdf_dpi
            )

    def _multi_page_output_changed(self) -> None:
        if self._loading_item_controls:
            return

        item = self._active_item()

        if item is not None:
            item.multi_page_output_mode = str(
                self.multi_page_output_combo.currentData()
                or self.app_settings.default_multi_page_output_mode
            )

    def _detect_libreoffice(self) -> None:
        detected_path = find_libreoffice()

        if detected_path is None:
            QMessageBox.warning(
                self,
                self.tr("LibreOffice was not found"),
                (
                    self.tr(
                        "LibreOffice was not detected automatically. "
                        "Install LibreOffice or manually choose soffice.exe."
                    )
                ),
            )
            return

        self.libreoffice_path = detected_path
        save_libreoffice_path(detected_path)
        self._refresh_libreoffice_ui()
        self._set_status_message(
            self.tr("Status: LibreOffice was found successfully.")
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
            self.tr("Choose LibreOffice soffice.exe"),
            str(start_directory),
            (
                self.tr(
                    "LibreOffice executable (soffice.exe);;"
                    "Executables (*.exe);;"
                    "All files (*.*)"
                )
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
                self.tr("Invalid LibreOffice file"),
                (
                    self.tr(
                        "Choose soffice.exe from the LibreOffice program folder.\n\n"
                        "The usual path is:\n"
                        r"C:\Program Files\LibreOffice\program\soffice.exe"
                    )
                ),
            )
            return

        self.libreoffice_path = selected_path.resolve()
        save_libreoffice_path(self.libreoffice_path)
        self._refresh_libreoffice_ui()
        self._set_status_message(
            self.tr("Status: LibreOffice path was saved.")
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
                self.tr("LibreOffice was not found")
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
        self.conversion_group.setVisible(
            item is not None and (quality_visible or pdf_input)
        )
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
        self.empty_queue_label.setVisible(not has_items)
        self.queue_widget.setVisible(has_items)
        if not has_active and self.advanced_options_button.isChecked():
            self.advanced_options_button.setChecked(False)
        self.advanced_options_button.setVisible(has_active)
        self.advanced_options_container.setVisible(
            has_active and self.advanced_options_button.isChecked()
        )
        self.remove_selected_button.setVisible(bool(selected_ids))
        self.remove_selected_button.setEnabled(
            not self.is_converting and bool(selected_ids)
        )
        self.clear_list_button.setEnabled(
            not self.is_converting and has_items
        )
        self.retry_failed_button.setEnabled(
            not self.is_converting and bool(failed_items)
        )
        self.retry_failed_button.setVisible(bool(failed_items))
        self.merge_images_button.setEnabled(not self.is_converting)
        self.settings_button.setEnabled(not self.is_converting)
        self.convert_button.setEnabled(
            not self.is_converting and bool(runnable_items)
        )
        self.cancel_button.setEnabled(self.is_converting)
        self._update_convert_button_text(len(runnable_items))
        self._update_feedback_visibility()

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
        self._update_list_button_grid(self.width())

        if hasattr(self, "add_files_action"):
            self.add_files_action.setEnabled(not self.is_converting)
            self.change_output_action.setEnabled(
                not self.is_converting
            )
            self.merge_images_action.setEnabled(
                not self.is_converting
            )
            self.settings_action.setEnabled(not self.is_converting)

    def _start_batch(self) -> None:
        if self.is_converting:
            return

        runnable_items = self._runnable_items()

        if not runnable_items:
            self._set_status_message(
                self.tr("Status: There are no items ready for processing.")
            )
            return

        try:
            ensure_output_directory_ready(self.output_directory)
        except Exception as error:
            ErrorDetailsDialog(
                exception_to_error_info(error),
                parent=self,
            ).exec()
            return

        for item in runnable_items:
            item.mark_pending_for_run(self.output_directory)
            self.queue_widget.update_item(item)

        self.cancel_requested = False
        self._batch_started_at = time.monotonic()
        self._batch_item_ids = [
            item.unique_id
            for item in runnable_items
        ]
        self.progress_bar.setValue(0)
        self.current_file_label.setText(self.tr("Preparing files..."))
        self.current_file_label.setToolTip("")
        self._update_batch_progress()
        self._set_status_message(
            self.tr("Status: Starting batch conversion..."),
            batch=True,
        )
        self._set_conversion_running(True)

        self.batch_thread = QThread(self)
        self.batch_worker = BatchConversionWorker(
            items=runnable_items,
            libreoffice_path=self.libreoffice_path,
        )
        self.batch_worker.moveToThread(self.batch_thread)

        # Qt owns deletion through the event loop: batch completion stops the
        # thread, then deleteLater releases both objects in their proper thread.
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
        self._set_status_message(
            self.tr("Status: Cancelling batch conversion..."),
            batch=True,
        )
        # The UI remains responsive while the worker reaches its next safe
        # cancellation checkpoint and removes any unpublished output.
        self.batch_worker.cancel()

    def _batch_started(self) -> None:
        self._set_status_message(
            self.tr("Status: Batch conversion has started."),
            batch=True,
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
        self.current_file_label.setText(
            self.tr("Current file: {file_name}").format(
                file_name=item.input_path.name,
            )
        )
        self.current_file_label.setToolTip(str(item.input_path))
        self._set_status_message(
            self.tr("Status: Converting {file_name}...").format(
                file_name=item.input_path.name,
            ),
            batch=True,
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
            self._set_status_message(
                self.tr("Status: {file_name}: {message}").format(
                    file_name=item.input_path.name,
                    message=message,
                ),
                batch=True,
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
        item.status_message = self.tr("Conversion is finished.")
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
            or self.tr("Conversion was cancelled.")
        )
        item.status_message = item.error_message
        self.queue_widget.update_item(item)
        self._update_batch_progress()

    def _batch_cancelled(self) -> None:
        self._set_status_message(
            self.tr("Status: Batch conversion was cancelled."),
            batch=True,
        )

    def _batch_finished(
        self,
        success_count: int,
        failed_count: int,
        cancelled_count: int,
    ) -> None:
        self.cancel_requested = False
        duration_seconds = (
            time.monotonic() - self._batch_started_at
            if self._batch_started_at is not None
            else 0.0
        )
        self.progress_bar.setValue(100)
        total_count = success_count + failed_count + cancelled_count
        self.progress_summary_label.setText(
            self.tr("Processed {completed} of {total} files").format(
                completed=total_count,
                total=total_count,
            )
        )
        self.progress_percent_label.setText("100%")
        self.current_file_label.setText(self.tr("Batch complete"))
        self.current_file_label.setToolTip("")
        self._set_status_message(
            self.tr(
                "Conversion finished:\n"
                "- Successful: {success_count}\n"
                "- Failed: {failed_count}\n"
                "- Cancelled: {cancelled_count}\n"
                "- Duration: {duration_seconds:.1f} s"
            ).format(
                success_count=success_count,
                failed_count=failed_count,
                cancelled_count=cancelled_count,
                duration_seconds=duration_seconds,
            ),
            batch=True,
        )

        if (
            self.app_settings.show_batch_summary
            and not self._closing_after_cancel
        ):
            QMessageBox.information(
                self,
                self.tr("Conversion summary"),
                (
                    self.tr(
                        "Conversion finished:\n"
                        "- Successful: {success_count}\n"
                        "- Failed: {failed_count}\n"
                        "- Cancelled: {cancelled_count}"
                    ).format(
                        success_count=success_count,
                        failed_count=failed_count,
                        cancelled_count=cancelled_count,
                    )
                ),
            )

        if (
            self.app_settings.open_output_after_success
            and success_count > 0
            and not self._closing_after_cancel
        ):
            self._open_output_directory()

        self._set_conversion_running(False)

    def _thread_finished(self) -> None:
        self.cancel_requested = False
        self.batch_worker = None
        self.batch_thread = None
        self._batch_item_ids = []
        self._batch_started_at = None
        self._set_conversion_running(False)

        if self._closing_after_cancel:
            self._closing_after_cancel = False
            QTimer.singleShot(0, self.close)

    def _set_conversion_running(
        self,
        running: bool,
    ) -> None:
        self.is_converting = running
        self._update_controls()

    def _set_status_message(
        self,
        message: str,
        *,
        batch: bool = False,
    ) -> None:
        self.status_label.setText(message)
        self.idle_status_label.setText(message)

        if batch:
            self._batch_feedback_visible = True
        elif not self.is_converting:
            self._batch_feedback_visible = False

        self._update_feedback_visibility()

    def _update_feedback_visibility(self) -> None:
        show_progress = (
            self.is_converting or self._batch_feedback_visible
        )
        self.progress_group.setVisible(show_progress)
        self.status_panel.setVisible(not show_progress)
        self.idle_status_label.setVisible(not show_progress)
        self.convert_button.setVisible(not self.is_converting)
        self.cancel_button.setVisible(self.is_converting)

    def _update_convert_button_text(
        self,
        runnable_count: int | None = None,
    ) -> None:
        count = (
            len(self._runnable_items())
            if runnable_count is None
            else runnable_count
        )

        if count == 1:
            text = self.tr("Convert 1 file")
        elif count > 1:
            text = self.tr("Convert {count} files").format(
                count=count
            )
        else:
            text = self.tr("Convert files")

        self.convert_button.setText(text)

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
        progress = int(total_progress / len(batch_items))
        completed_count = sum(
            item.status
            in {
                ConversionStatus.SUCCESS,
                ConversionStatus.FAILED,
                ConversionStatus.CANCELLED,
            }
            for item in batch_items
        )
        self.progress_bar.setValue(progress)
        self.progress_percent_label.setText(f"{progress}%")
        self.progress_summary_label.setText(
            self.tr("Processed {completed} of {total} files").format(
                completed=completed_count,
                total=len(batch_items),
            )
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

    def _restore_window_placement(self) -> None:
        geometry = get_window_geometry()
        state = get_window_state()

        if geometry is not None:
            self.restoreGeometry(geometry)

        if state is not None:
            self.restoreState(state)

        self._ensure_window_on_screen()

    def _ensure_window_on_screen(self) -> None:
        app = QApplication.instance()

        if not isinstance(app, QApplication):
            return

        frame_geometry = self.frameGeometry()
        screen = app.screenAt(frame_geometry.center())

        if screen is not None:
            return

        primary_screen = app.primaryScreen()

        if primary_screen is None:
            return

        available_geometry = primary_screen.availableGeometry()
        self.move(
            available_geometry.topLeft()
            + QPoint(40, 40)
        )

    def closeEvent(self, event) -> None:
        if self.is_converting:
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Icon.Question)
            message_box.setWindowTitle(self.tr("Conversion is running"))
            message_box.setText(
                self.tr(
                    "Conversion is running. Do you want to cancel it and close the application?"
                )
            )
            continue_button = message_box.addButton(
                self.tr("Continue conversion"),
                QMessageBox.ButtonRole.RejectRole,
            )
            stop_button = message_box.addButton(
                self.tr("Cancel and close"),
                QMessageBox.ButtonRole.DestructiveRole,
            )
            message_box.setDefaultButton(continue_button)
            message_box.exec()

            if message_box.clickedButton() == stop_button:
                self._closing_after_cancel = True
                self._set_status_message(
                    self.tr(
                        "Status: Cancelling conversion and closing the application..."
                    ),
                    batch=True,
                )
                self._cancel_conversion()

            event.ignore()
            return

        save_window_geometry(
            self.saveGeometry(),
            self.saveState(),
        )
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        if hasattr(self, "list_button_layout"):
            self._update_list_button_grid(event.size().width())
