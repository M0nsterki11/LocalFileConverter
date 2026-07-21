"""Resolve and apply the application's light, dark, or system theme."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from app.settings import validate_theme
from utils.logging_utils import LOGGER_NAME, sanitize_path
from utils.resource_utils import get_resource_path


DEFAULT_THEME_DIRECTORY = get_resource_path("resources/themes")


class ThemeManager:
    """Load QSS resources and apply the selected appearance to Qt."""

    def __init__(
        self,
        theme_directory: Path | None = None,
    ) -> None:
        self.theme_directory = (
            theme_directory
            if theme_directory is not None
            else DEFAULT_THEME_DIRECTORY
        )

    def apply_theme(
        self,
        app: QApplication,
        theme: str,
    ) -> str:
        """Apply a validated theme and return its resolved light/dark value."""
        resolved_theme = self.resolve_theme(app, theme)
        app.setStyleSheet(
            self.build_stylesheet(resolved_theme)
        )
        return resolved_theme

    def resolve_theme(
        self,
        app: QApplication,
        theme: str,
    ) -> str:
        """Resolve a configured theme, including the system preference."""
        validated_theme = validate_theme(theme)

        if validated_theme != "system":
            return validated_theme

        return self.detect_system_theme(app)

    def detect_system_theme(
        self,
        app: QApplication,
    ) -> str:
        """Detect the Qt color scheme, with a palette-based fallback."""
        try:
            color_scheme = app.styleHints().colorScheme()

            if color_scheme == Qt.ColorScheme.Dark:
                return "dark"

            if color_scheme == Qt.ColorScheme.Light:
                return "light"
        except (AttributeError, RuntimeError):
            pass

        window_color = app.palette().color(QPalette.ColorRole.Window)

        if window_color.lightness() < 128:
            return "dark"

        return "light"

    def build_stylesheet(
        self,
        theme: str,
    ) -> str:
        """Combine common QSS with the requested color-specific QSS."""
        resolved_theme = (
            theme
            if theme in {"light", "dark"}
            else "light"
        )

        parts = [
            self.read_qss("common.qss"),
            self.read_qss(f"{resolved_theme}.qss"),
        ]

        return "\n\n".join(
            part
            for part in parts
            if part
        )

    def read_qss(
        self,
        filename: str,
    ) -> str:
        """Read a theme resource, logging and returning empty text on failure."""
        path = self.theme_directory / filename

        try:
            if not path.exists():
                logging.getLogger(LOGGER_NAME).warning(
                    "QSS theme file is missing: %s",
                    sanitize_path(path),
                )
                return ""

            return path.read_text(encoding="utf-8")
        except OSError as error:
            logging.getLogger(LOGGER_NAME).warning(
                "Could not read QSS theme file %s: %s",
                sanitize_path(path),
                error,
            )
            return ""
