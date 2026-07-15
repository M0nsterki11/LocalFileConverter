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
        self.setWindowTitle("Postavke")
        self.resize(620, 520)

        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._settings = AppSettings(**app_settings.__dict__)
        self._libreoffice_path = libreoffice_path

        self._build_ui()
        self._connect_signals()
        self._load_settings(self._settings, self._libreoffice_path)

    @property
    def app_settings(self) -> AppSettings:
        return self._collect_settings()

    @property
    def libreoffice_path(self) -> Path | None:
        if is_valid_libreoffice_executable(
            self._libreoffice_path
        ):
            return self._libreoffice_path

        return None

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "Općenito")
        self.tabs.addTab(self._build_images_tab(), "Slike")
        self.tabs.addTab(self._build_pdf_tab(), "PDF")
        self.tabs.addTab(self._build_office_tab(), "Office")
        root_layout.addWidget(self.tabs)

        button_layout = QHBoxLayout()
        self.reset_button = QPushButton("Vrati zadane postavke")
        self.save_button = QPushButton("Spremi")
        self.save_button.setObjectName("convertButton")
        self.cancel_button = QPushButton("Odustani")

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

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Sistemska", "system")
        self.theme_combo.addItem("Svijetla", "light")
        self.theme_combo.addItem("Tamna", "dark")

        self.output_directory_input = QLineEdit()
        self.output_directory_input.setReadOnly(True)
        self.select_output_button = QPushButton("Promijeni")
        self.select_output_button.setIcon(get_icon(self, "folder"))

        self.open_output_checkbox = QCheckBox(
            "Otvori izlaznu mapu nakon uspješne konverzije"
        )
        self.summary_checkbox = QCheckBox(
            "Prikaži završni sažetak grupne konverzije"
        )

        self.open_logs_button = QPushButton("Otvori mapu s logovima")

        layout.addWidget(QLabel("Tema:"), 0, 0)
        layout.addWidget(self.theme_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("Zadana izlazna mapa:"), 1, 0)
        layout.addWidget(self.output_directory_input, 1, 1)
        layout.addWidget(self.select_output_button, 1, 2)
        layout.addWidget(self.open_output_checkbox, 2, 1, 1, 2)
        layout.addWidget(self.summary_checkbox, 3, 1, 1, 2)
        layout.addWidget(self.open_logs_button, 4, 1, 1, 2)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_images_tab(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(10, 100)
        self.quality_spin.setSuffix("%")
        self.quality_spin.setToolTip(
            "Zadana kvaliteta za JPG i WEBP slike."
        )

        layout.addWidget(
            QLabel("Zadana JPG/WEBP kvaliteta:"),
            0,
            0,
        )
        layout.addWidget(self.quality_spin, 0, 1)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_pdf_tab(self) -> QWidget:
        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.dpi_combo = QComboBox()
        for dpi in (96, 150, 200, 300):
            self.dpi_combo.addItem(f"{dpi} DPI", dpi)
        self.dpi_combo.setToolTip(
            "Veci DPI daje detaljnije slike i vece datoteke."
        )

        self.multi_page_mode_combo = QComboBox()
        self.multi_page_mode_combo.addItem("Obična mapa", "folder")
        self.multi_page_mode_combo.addItem("ZIP arhiva", "zip")
        self.multi_page_mode_combo.setToolTip(
            "Automatski ZIP iznad 100 MB ostaje ukljucen."
        )

        layout.addWidget(QLabel("Zadani DPI:"), 0, 0)
        layout.addWidget(self.dpi_combo, 0, 1)
        layout.addWidget(
            QLabel("Više PDF stranica:"),
            1,
            0,
        )
        layout.addWidget(self.multi_page_mode_combo, 1, 1)
        layout.setColumnStretch(1, 1)

        return widget

    def _build_office_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        engine_group = QGroupBox("Office engine")
        engine_layout = QGridLayout(engine_group)

        self.office_engine_combo = QComboBox()
        self.office_engine_combo.addItem("Automatski", "auto")
        self.office_engine_combo.addItem(
            "LibreOffice",
            "libreoffice",
        )
        self.office_engine_combo.setToolTip(
            "Zadani engine za Office dokumente."
        )
        engine_layout.addWidget(QLabel("Zadani engine:"), 0, 0)
        engine_layout.addWidget(self.office_engine_combo, 0, 1)
        engine_layout.setColumnStretch(1, 1)
        layout.addWidget(engine_group)

        libreoffice_group = QGroupBox("LibreOffice")
        libreoffice_layout = QGridLayout(libreoffice_group)
        self.libreoffice_path_input = QLineEdit()
        self.libreoffice_path_input.setReadOnly(True)
        self.libreoffice_path_input.setToolTip(
            "Putanja do soffice.exe za LibreOffice konverzije."
        )
        self.detect_libreoffice_button = QPushButton(
            "Pronađi automatski"
        )
        self.detect_libreoffice_button.setIcon(
            get_icon(self, "settings")
        )
        self.select_libreoffice_button = QPushButton(
            "Odaberi soffice.exe"
        )
        self.select_libreoffice_button.setIcon(
            get_icon(self, "folder")
        )

        libreoffice_layout.addWidget(
            QLabel("Trenutačna putanja:"),
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
        libreoffice_layout.setColumnStretch(1, 1)
        layout.addWidget(libreoffice_group)
        layout.addStretch()

        return widget

    def _connect_signals(self) -> None:
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

    def _load_settings(
        self,
        app_settings: AppSettings,
        libreoffice_path: Path | None,
    ) -> None:
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
        self._refresh_libreoffice_path()

    def _select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Odaberi zadanu izlaznu mapu",
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
                "LibreOffice nije pronađen",
                (
                    "LibreOffice nije automatski pronađen. "
                    "Instaliraj LibreOffice ili ručno odaberi soffice.exe."
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
            "Odaberi LibreOffice soffice.exe",
            str(start_directory),
            (
                "LibreOffice executable (soffice.exe);;"
                "Izvršne datoteke (*.exe);;"
                "Sve datoteke (*.*)"
            ),
        )

        if not executable_path:
            return

        selected_path = Path(executable_path)

        if not is_valid_libreoffice_executable(selected_path):
            QMessageBox.warning(
                self,
                "Neispravna LibreOffice datoteka",
                "Odaberi valjanu soffice.exe datoteku.",
            )
            return

        self._libreoffice_path = selected_path.resolve()
        self._refresh_libreoffice_path()

    def _reset_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Vrati zadane postavke",
            "Zelis vratiti sve postavke u ovom prozoru na zadane vrijednosti?",
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
                last_file_dialog_directory=DEFAULT_OUTPUT_DIRECTORY,
            ),
            None,
        )

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
            last_file_dialog_directory=output_directory,
        )

    def _refresh_libreoffice_path(self) -> None:
        if self._libreoffice_path is None:
            self.libreoffice_path_input.clear()
            self.libreoffice_path_input.setPlaceholderText(
                "LibreOffice nije pronađen"
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
