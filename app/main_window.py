from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Local File Converter")
        self.resize(900, 600)
        self.setMinimumSize(700, 450)

        title_label = QLabel("LOCAL FILE CONVERTER")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        font = title_label.font()
        font.setPointSize(22)
        font.setBold(True)
        title_label.setFont(font)

        description_label = QLabel(
            "Lokalno pretvaranje datoteka bez slanja podataka na internet."
        )
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)