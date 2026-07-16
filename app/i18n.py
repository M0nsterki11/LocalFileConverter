from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QTranslator, Signal

from utils.resource_utils import get_resource_path


DEFAULT_LANGUAGE = "en"
LANGUAGE_KEY = "ui/language"
SUPPORTED_LANGUAGES = {
    "en": "English",
    "hr": "Hrvatski",
}
TRANSLATION_FILES = {
    "hr": "local_file_converter_hr.qm",
}


class TranslationManager(QObject):
    language_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._translator: QTranslator | None = None
        self._language = DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> str:
        requested_language = validate_language(language)
        app = QCoreApplication.instance()

        if app is None:
            self._language = requested_language
            return self._language

        self._remove_translator(app)

        if requested_language == DEFAULT_LANGUAGE:
            self._language = DEFAULT_LANGUAGE
            self.language_changed.emit(self._language)
            return self._language

        translator = QTranslator(self)
        translation_path = get_translation_path(requested_language)

        if translation_path is None or not translation_path.exists():
            logging.getLogger(__name__).warning(
                "Translation file is missing for language '%s'; using English.",
                requested_language,
            )
            self._language = DEFAULT_LANGUAGE
            self.language_changed.emit(self._language)
            return self._language

        if not translator.load(str(translation_path)):
            logging.getLogger(__name__).warning(
                "Could not load translation file %s; using English.",
                translation_path,
            )
            self._language = DEFAULT_LANGUAGE
            self.language_changed.emit(self._language)
            return self._language

        app.installTranslator(translator)
        self._translator = translator
        self._language = requested_language
        self.language_changed.emit(self._language)
        return self._language

    def _remove_translator(self, app: QCoreApplication) -> None:
        if self._translator is not None:
            app.removeTranslator(self._translator)
            self._translator = None


def get_translation_manager() -> TranslationManager:
    global _TRANSLATION_MANAGER

    try:
        return _TRANSLATION_MANAGER
    except NameError:
        _TRANSLATION_MANAGER = TranslationManager()
        return _TRANSLATION_MANAGER


def validate_language(language: object) -> str:
    language_code = str(language or "").strip().lower()

    if language_code in SUPPORTED_LANGUAGES:
        return language_code

    return DEFAULT_LANGUAGE


def get_translation_path(language: str) -> Path | None:
    file_name = TRANSLATION_FILES.get(validate_language(language))

    if not file_name:
        return None

    return get_resource_path(Path("translations") / file_name)


def translate(context: str, source_text: str, n: int = -1) -> str:
    return QCoreApplication.translate(context, source_text, None, n)
