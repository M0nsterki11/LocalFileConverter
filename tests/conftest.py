from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if not isinstance(app, QApplication):
        app = QApplication([])

    yield app
