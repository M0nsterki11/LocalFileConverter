"""Configure resilient local logging and sanitize user-specific paths."""

from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


LOGGER_NAME = "local_file_converter"
LOG_FILE_NAME = "app.log"
MAX_LOG_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5
TEMP_PREFIX = "lfc_"


def get_log_directory() -> Path:
    """Return the per-user directory used for application logs."""
    local_app_data = os.environ.get("LOCALAPPDATA")

    if local_app_data:
        base_directory = Path(local_app_data)
    else:
        base_directory = Path.home() / "AppData" / "Local"

    return base_directory / "LocalFileConverter" / "logs"


def get_log_file_path() -> Path:
    """Return the active application log file path."""
    return get_log_directory() / LOG_FILE_NAME


def setup_logging(
    *,
    level: int | None = None,
    log_directory: str | Path | None = None,
) -> logging.Logger:
    """Configure the shared rotating logger with a stderr fallback."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level if level is not None else _default_log_level())
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    try:
        directory = (
            Path(log_directory)
            if log_directory is not None
            else get_log_directory()
        )
        directory.mkdir(parents=True, exist_ok=True)
        log_file = directory / LOG_FILE_NAME

        if not _has_rotating_file_handler(logger, log_file):
            handler = RotatingFileHandler(
                log_file,
                maxBytes=MAX_LOG_BYTES,
                backupCount=BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(formatter)
            handler.setLevel(logger.level)
            logger.addHandler(handler)

    except Exception:
        _ensure_fallback_handler(logger, formatter)

    logging.captureWarnings(True)
    return logger


def open_log_directory() -> bool:
    """Open the log directory and return whether the shell accepted it."""
    try:
        from utils.file_utils import open_directory

        return open_directory(get_log_directory())
    except Exception:
        return False


def log_exception_safely(
    logger: logging.Logger | None,
    message: str,
    *args: Any,
    exc_info: bool | BaseException | tuple[Any, Any, Any] = True,
    **kwargs: Any,
) -> None:
    """Log an exception without allowing logging failures to escape."""
    try:
        target_logger = logger or logging.getLogger(LOGGER_NAME)
        target_logger.exception(
            sanitize_for_log(message),
            *args,
            exc_info=exc_info,
            **kwargs,
        )
    except Exception:
        return


def sanitize_path(path: str | Path) -> str:
    """Shorten home-relative paths while preserving useful diagnostics."""
    try:
        resolved_path = Path(path).expanduser().resolve()
        home_path = Path.home().expanduser().resolve()

        try:
            relative_path = resolved_path.relative_to(home_path)
            return str(Path("~") / relative_path)
        except ValueError:
            return str(resolved_path)

    except Exception:
        return str(path)


def sanitize_for_log(value: object) -> str:
    """Replace the current user's home path in arbitrary log text."""
    text = str(value)

    try:
        home = str(Path.home().expanduser().resolve())
    except Exception:
        home = ""

    if home:
        text = text.replace(home, "~")

    return text


def cleanup_old_lfc_temp_files(
    temp_directory: str | Path | None = None,
    *,
    max_age_seconds: int = 24 * 60 * 60,
    logger: logging.Logger | None = None,
) -> int:
    """Best-effort remove stale application temp entries and return a count."""
    target_logger = logger or logging.getLogger(LOGGER_NAME)
    root = (
        Path(temp_directory)
        if temp_directory is not None
        else Path(tempfile.gettempdir())
    )
    cutoff = time.time() - max_age_seconds
    removed_count = 0

    try:
        candidates = list(root.iterdir())
    except OSError as error:
        _warning_safely(
            target_logger,
            "Cannot inspect temporary directory %s: %s",
            sanitize_path(root),
            error,
        )
        return 0

    for candidate in candidates:
        if not candidate.name.startswith(TEMP_PREFIX):
            continue

        try:
            if candidate.stat().st_mtime > cutoff:
                continue

            if candidate.is_dir():
                shutil.rmtree(candidate)
            else:
                candidate.unlink()

            removed_count += 1

        except OSError as error:
            _warning_safely(
                target_logger,
                "Cannot remove old temporary entry %s: %s",
                sanitize_path(candidate),
                error,
            )

    return removed_count


def _default_log_level() -> int:
    return logging.INFO if getattr(sys, "frozen", False) else logging.DEBUG


def _has_rotating_file_handler(
    logger: logging.Logger,
    log_file: Path,
) -> bool:
    expected_path = str(log_file.resolve())

    for handler in logger.handlers:
        if not isinstance(handler, RotatingFileHandler):
            continue

        try:
            if Path(handler.baseFilename).resolve() == Path(expected_path):
                return True
        except OSError:
            continue

    return False


def _ensure_fallback_handler(
    logger: logging.Logger,
    formatter: logging.Formatter,
) -> None:
    if any(
        isinstance(handler, logging.StreamHandler)
        for handler in logger.handlers
    ):
        return

    try:
        handler: logging.Handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except Exception:
        if not any(
            isinstance(handler, logging.NullHandler)
            for handler in logger.handlers
        ):
            logger.addHandler(logging.NullHandler())


def _warning_safely(
    logger: logging.Logger,
    message: str,
    *args: object,
) -> None:
    try:
        logger.warning(message, *args)
    except Exception:
        return
