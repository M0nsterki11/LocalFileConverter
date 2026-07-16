from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    get_translation_manager,
    validate_language,
)
from app.icon_provider import get_app_icon, get_icon
from app.settings import (
    AppSettings,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_MULTI_PAGE_OUTPUT_MODE,
    DEFAULT_OFFICE_ENGINE,
    DEFAULT_OPEN_OUTPUT_AFTER_SUCCESS,
    DEFAULT_OUTPUT_DIRECTORY,
    DEFAULT_PDF_DPI,
    DEFAULT_SHOW_BATCH_SUMMARY,
    DEFAULT_THEME,
    clear_libreoffice_path,
    save_language,
    save_libreoffice_path,
    validate_image_quality,
    validate_multi_page_output_mode,
    validate_office_engine,
    validate_output_directory,
    validate_pdf_dpi,
    validate_theme,
)
from utils.libreoffice_utils import (
    find_libreoffice,
    get_default_libreoffice_browse_directory,
    is_valid_libreoffice_executable,
)
from utils.logging_utils import open_log_directory


class SettingsDialog(QDialog):
    def __init__(
        self,
        app_settings: AppSettings,
        libreoffice_path: Path | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.resize(620, 560)

        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._settings = AppSettings(**app_settings.__dict__)
        self._libreoffice_path = libreoffice_path
        self._loading = False

        self._build_ui()
        self._connect_signals()
        self._load_settings(self._settings, self._libreoffice_path)
        self.retranslate_ui()
        get_translation_manager().language_changed.connect(
            self.retranslate_ui
        )

    @property
    def app_settings(self) -> AppSettings:
        return self._collect_settings()

    @property
    def libreoffice_path(self) -> Path | None:
        if is_valid_libreoffice_executable(self._libreoffice_path):
            return self._libreoffice_path

        return None

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.general_tab = self._build_general_tab()
        self.images_tab = self._build_images_tab()
        self.pdf_tab = self._build_pdf_tab()
        self.office_tab = self._build_office_tab()
        self.tabs.addTab(self.general_tab, "")
        self.tabs.addTab(self.images_tab, "")
        self.tabs.addTab(self.pdf_tab, "")
        self.tabs.addTab(self.office_tab, "")
        root_layout.addWidget(self.tabs)

        button_layout = QHBoxLayout()
        self.reset_button = QPushButton()
        self.save_button = QPushButton()
        self.save_button.setObjectName("convertButton")
        self.cancel_button = QPushButton()

        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        root_layout.addLayout(button_layout)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.language_label = QLabel()
        self.language_combo = QComboBox()
        for code, label in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(label, code)

        self.theme_label = QLabel()
        self.theme_combo = QComboBox()
        for value in ("system", "light", "dark"):
            self.theme_combo.addItem("", value)

        self.output_directory_label = QLabel()
        self.output_directory_input = QLineEdit()
        self.output_directory_input.setReadOnly(True)
        self.select_output_button = QPushButton()
        self.select_output_button.setIcon(get_icon(self, "folder"))

        self.open_output_checkbox = QCheckBox()
        self.summary_checkbox = QCheckBox()
        self.open_logs_button = QPushButton()

        layout.addWidget(self.language_label, 0, 0)
        layout.addWidget(self.language_combo, 0, 1, 1, 2)
        layout.addWidget(self.theme_label, 1, 0)
        layout.addWidget(self.theme_combo, 1, 1, 1, 2)
        layout.addWidget(self.output_directory_label, 2, 0)
        layout.addWidget(self.output_directory_input, 2, 1)
        layout.addWidget(self.select_output_button, 2, 2)
        layout.addWidget(self.open_output_checkbox, 3, 1, 1, 2)
        layout.addWidget(self.summary_checkbox, 4, 1, 1, 2)
        layout.addWidget(self.open_logs_button, 5, 1, 1, 2)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_images_tab(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.quality_label = QLabel()
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(10, 100)
        self.quality_spin.setSuffix("%")

        layout.addWidget(self.quality_label, 0, 0)
        layout.addWidget(self.quality_spin, 0, 1)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_pdf_tab(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.dpi_label = QLabel()
        self.dpi_combo = QComboBox()
        for dpi in (96, 150, 200, 300):
            self.dpi_combo.addItem(f"{dpi} DPI", dpi)

        self.multi_page_mode_label = QLabel()
        self.multi_page_mode_combo = QComboBox()
        self.multi_page_mode_combo.addItem("", "folder")
        self.multi_page_mode_combo.addItem("", "zip")

        layout.addWidget(self.dpi_label, 0, 0)
        layout.addWidget(self.dpi_combo, 0, 1)
        layout.addWidget(self.multi_page_mode_label, 1, 0)
        layout.addWidget(self.multi_page_mode_combo, 1, 1)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_office_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.engine_group = QGroupBox()
        engine_layout = QGridLayout(self.engine_group)

        self.office_engine_label = QLabel()
        self.office_engine_combo = QComboBox()
        self.office_engine_combo.addItem("", "auto")
        self.office_engine_combo.addItem("LibreOffice", "libreoffice")

        engine_layout.addWidget(self.office_engine_label, 0, 0)
        engine_layout.addWidget(self.office_engine_combo, 0, 1)
        engine_layout.setColumnStretch(1, 1)
        layout.addWidget(self.engine_group)

        self.libreoffice_group = QGroupBox()
        libreoffice_layout = QGridLayout(self.libreoffice_group)
        self.libreoffice_path_label = QLabel()
        self.libreoffice_path_input = QLineEdit()
        self.libreoffice_path_input.setReadOnly(True)
        self.detect_libreoffice_button = QPushButton()
        self.detect_libreoffice_button.setIcon(get_icon(self, "settings"))
        self.select_libreoffice_button = QPushButton()
        self.select_libreoffice_button.setIcon(get_icon(self, "folder"))

        libreoffice_layout.addWidget(self.libreoffice_path_label, 0, 0)
        libreoffice_layout.addWidget(
            self.libreoffice_path_input,
            0,
            1,
            1,
            2,
        )
        libreoffice_layout.addWidget(self.detect_libreoffice_button, 1, 1)
        libreoffice_layout.addWidget(self.select_libreoffice_button, 1, 2)
        libreoffice_layout.setColumnStretch(1, 1)
        layout.addWidget(self.libreoffice_group)
        layout.addStretch()

        return widget

    def _connect_signals(self) -> None:
        self.language_combo.currentIndexChanged.connect(
            self._language_changed
        )
        self.select_output_button.clicked.connect(
            self._select_output_directory
        )
        self.detect_libreoffice_button.clicked.connect(
            self._detect_libreoffice
        )
        self.select_libreoffice_button.clicked.connect(
            self._select_libreoffice
        )
        self.reset_button.clicked.connect(self._reset_defaults)
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        self.open_logs_button.clicked.connect(open_log_directory)

    def retranslate_ui(self, *_args) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self.tabs.setTabText(0, self.tr("General"))
        self.tabs.setTabText(1, self.tr("Images"))
        self.tabs.setTabText(2, self.tr("PDF"))
        self.tabs.setTabText(3, self.tr("Office"))

        self.language_label.setText(self.tr("Language:"))
        self.theme_label.setText(self.tr("Theme:"))
        self.output_directory_label.setText(self.tr("Default output folder:"))
        self.select_output_button.setText(self.tr("Change"))
        self.open_output_checkbox.setText(
            self.tr("Open the output folder after a successful conversion")
        )
        self.summary_checkbox.setText(
            self.tr("Show a summary after batch conversion")
        )
        self.open_logs_button.setText(self.tr("Open log folder"))

        self.theme_combo.setItemText(0, self.tr("System"))
        self.theme_combo.setItemText(1, self.tr("Light"))
        self.theme_combo.setItemText(2, self.tr("Dark"))

        self.quality_label.setText(self.tr("Default JPG/WEBP quality:"))
        self.quality_spin.setToolTip(
            self.tr("Default quality for JPG and WEBP images.")
        )

        self.dpi_label.setText(self.tr("Default DPI:"))
        self.dpi_combo.setToolTip(
            self.tr("Higher DPI creates more detailed images and larger files.")
        )
        self.multi_page_mode_label.setText(self.tr("Multiple PDF pages:"))
        self.multi_page_mode_combo.setItemText(0, self.tr("Plain folder"))
        self.multi_page_mode_combo.setItemText(1, self.tr("ZIP archive"))
        self.multi_page_mode_combo.setToolTip(
            self.tr("Automatic ZIP above 100 MB remains enabled.")
        )

        self.engine_group.setTitle(self.tr("Office engine"))
        self.office_engine_label.setText(self.tr("Default engine:"))
        self.office_engine_combo.setItemText(0, self.tr("Automatic"))
        self.office_engine_combo.setItemText(1, "LibreOffice")
        self.office_engine_combo.setToolTip(
            self.tr("Default engine for Office documents.")
        )

        self.libreoffice_group.setTitle("LibreOffice")
        self.libreoffice_path_label.setText(self.tr("Current path:"))
        self.libreoffice_path_input.setToolTip(
            self.tr("Path to soffice.exe for LibreOffice conversions.")
        )
        self.detect_libreoffice_button.setText(self.tr("Detect automatically"))
        self.select_libreoffice_button.setText(self.tr("Choose soffice.exe"))

        self.reset_button.setText(self.tr("Reset defaults"))
        self.save_button.setText(self.tr("Save"))
        self.cancel_button.setText(self.tr("Cancel"))
        self._refresh_libreoffice_path()

    def _load_settings(
        self,
        app_settings: AppSettings,
        libreoffice_path: Path | None,
    ) -> None:
        self._loading = True
        self._set_combo_data(
            self.language_combo,
            validate_language(app_settings.language),
        )
        self._set_combo_data(
            self.theme_combo,
            validate_theme(app_settings.theme),
        )
        self.output_directory_input.setText(
            str(validate_output_directory(
                app_settings.default_output_directory
            ))
        )
        self.open_output_checkbox.setChecked(
            bool(app_settings.open_output_after_success)
        )
        self.summary_checkbox.setChecked(
            bool(app_settings.show_batch_summary)
        )
        self.quality_spin.setValue(
            validate_image_quality(
                app_settings.default_image_quality
            )
        )
        self._set_combo_data(
            self.dpi_combo,
            validate_pdf_dpi(app_settings.default_pdf_dpi),
        )
        self._set_combo_data(
            self.multi_page_mode_combo,
            validate_multi_page_output_mode(
                app_settings.default_multi_page_output_mode
            ),
        )
        self._set_combo_data(
            self.office_engine_combo,
            validate_office_engine(
                app_settings.default_office_engine
            ),
        )
        self._libreoffice_path = (
            libreoffice_path
            if is_valid_libreoffice_executable(libreoffice_path)
            else None
        )
        self._loading = False
        self._refresh_libreoffice_path()

    def _language_changed(self) -> None:
        if self._loading:
            return

        selected_language = validate_language(
            self.language_combo.currentData()
        )
        saved_language = save_language(selected_language)
        self._settings.language = saved_language
        active_language = get_translation_manager().set_language(
            saved_language
        )

        if active_language != selected_language:
            self._loading = True
            self._set_combo_data(self.language_combo, active_language)
            self._loading = False

    def _select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Choose the default output folder"),
            self.output_directory_input.text()
            or str(DEFAULT_OUTPUT_DIRECTORY),
        )

        if selected_directory:
            self.output_directory_input.setText(selected_directory)

    def _detect_libreoffice(self) -> None:
        detected_path = find_libreoffice()

        if detected_path is None:
            QMessageBox.warning(
                self,
                self.tr("LibreOffice was not found"),
                self.tr(
                    "LibreOffice was not detected automatically. "
                    "Install LibreOffice or manually choose soffice.exe."
                ),
            )
            return

        self._libreoffice_path = detected_path
        self._refresh_libreoffice_path()

    def _select_libreoffice(self) -> None:
        start_directory = (
            self._libreoffice_path.parent
            if self._libreoffice_path is not None
            else get_default_libreoffice_browse_directory()
        )
        executable_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose LibreOffice soffice.exe"),
            str(start_directory),
            self.tr(
                "LibreOffice executable (soffice.exe);;"
                "Executables (*.exe);;"
                "All files (*.*)"
            ),
        )

        if not executable_path:
            return

        selected_path = Path(executable_path)

        if not is_valid_libreoffice_executable(selected_path):
            QMessageBox.warning(
                self,
                self.tr("Invalid LibreOffice file"),
                self.tr("Choose a valid soffice.exe file."),
            )
            return

        self._libreoffice_path = selected_path.resolve()
        self._refresh_libreoffice_path()

    def _reset_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            self.tr("Reset defaults"),
            self.tr(
                "Do you want to reset all settings in this window to their defaults?"
            ),
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self._load_settings(
            AppSettings(
                theme=DEFAULT_THEME,
                default_output_directory=DEFAULT_OUTPUT_DIRECTORY,
                open_output_after_success=(
                    DEFAULT_OPEN_OUTPUT_AFTER_SUCCESS
                ),
                show_batch_summary=DEFAULT_SHOW_BATCH_SUMMARY,
                default_image_quality=DEFAULT_IMAGE_QUALITY,
                default_pdf_dpi=DEFAULT_PDF_DPI,
                default_multi_page_output_mode=(
                    DEFAULT_MULTI_PAGE_OUTPUT_MODE
                ),
                default_office_engine=DEFAULT_OFFICE_ENGINE,
                language=DEFAULT_LANGUAGE,
                last_file_dialog_directory=DEFAULT_OUTPUT_DIRECTORY,
            ),
            None,
        )
        save_language(DEFAULT_LANGUAGE)
        get_translation_manager().set_language(DEFAULT_LANGUAGE)

    def _save(self) -> None:
        if self.libreoffice_path is not None:
            save_libreoffice_path(self.libreoffice_path)
        else:
            clear_libreoffice_path()

        self.accept()

    def _collect_settings(self) -> AppSettings:
        output_directory = validate_output_directory(
            self.output_directory_input.text()
        )

        return AppSettings(
            theme=validate_theme(self.theme_combo.currentData()),
            default_output_directory=output_directory,
            open_output_after_success=(
                self.open_output_checkbox.isChecked()
            ),
            show_batch_summary=self.summary_checkbox.isChecked(),
            default_image_quality=validate_image_quality(
                self.quality_spin.value()
            ),
            default_pdf_dpi=validate_pdf_dpi(
                self.dpi_combo.currentData()
            ),
            default_multi_page_output_mode=(
                validate_multi_page_output_mode(
                    self.multi_page_mode_combo.currentData()
                )
            ),
            default_office_engine=validate_office_engine(
                self.office_engine_combo.currentData()
            ),
            language=validate_language(
                self.language_combo.currentData()
            ),
            last_file_dialog_directory=output_directory,
        )

    def _refresh_libreoffice_path(self) -> None:
        if self._libreoffice_path is None:
            self.libreoffice_path_input.clear()
            self.libreoffice_path_input.setPlaceholderText(
                self.tr("LibreOffice was not found")
            )
            return

        self.libreoffice_path_input.setText(
            str(self._libreoffice_path)
        )
        self.libreoffice_path_input.setToolTip(
            str(self._libreoffice_path)
        )

    @staticmethod
    def _set_combo_data(
        combo: QComboBox,
        value,
    ) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
