from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_REPOSITORY_URL,
)
from app.icon_provider import get_app_icon
from utils.logging_utils import open_log_directory


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"O aplikaciji {APP_NAME}")
        self.setMinimumWidth(460)

        app_icon = get_app_icon()

        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        title_label = QLabel(APP_NAME)
        title_label.setObjectName("mainTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_label = QLabel(f"Verzija {APP_VERSION}")
        version_label.setObjectName("subtitle")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_label = QLabel(
            "Local File Converter obradu datoteka izvodi lokalno. "
            "Podaci se ne šalju na internet.\n\n"
            "Podržane su konverzije slika, PDF-a, Office dokumenata "
            "u PDF te spajanje više slika u jedan PDF.\n\n"
            "Aplikacija je napravljena u Pythonu i PySide6. "
            "LibreOffice se koristi kao vanjski alat kada je odabran "
            "ili potreban za Office konverziju.\n\n"
            "Aplikacija sprema lokalni tehnicki log za greske. "
            "Log ne sadrzi sadrzaj dokumenata i mozes ga otvoriti "
            "ili obrisati iz svoje korisnicke mape.\n\n"
            f"GitHub: {GITHUB_REPOSITORY_URL}\n"
            f"Copyright {date.today().year}"
        )
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        logs_button = QPushButton("Otvori mapu s logovima")
        logs_button.clicked.connect(open_log_directory)
        close_button = QPushButton("Zatvori")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(logs_button)
        button_layout.addWidget(close_button)

        root_layout.addWidget(title_label)
        root_layout.addWidget(version_label)
        root_layout.addWidget(body_label)
        root_layout.addLayout(button_layout)
