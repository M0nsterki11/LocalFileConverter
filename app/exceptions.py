"""Domain exceptions shared by validation, converters, and the UI."""

from __future__ import annotations


class LocalFileConverterError(Exception):
    """Base class for expected MyFile Converter errors."""

    def __init__(
        self,
        message: str = "",
        *,
        user_message: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(message)
        self.user_message = user_message
        self.suggestion = suggestion


class InputFileError(LocalFileConverterError):
    """Input file is missing, invalid, empty, or unreadable."""


class UnsupportedFormatError(InputFileError):
    """The selected input or output format is not supported."""


class OutputDirectoryError(LocalFileConverterError):
    """The output directory cannot be created or written to."""


class InsufficientDiskSpaceError(OutputDirectoryError):
    """The target disk does not have enough free space."""

    def __init__(
        self,
        message: str = "",
        *,
        required_bytes: int | None = None,
        available_bytes: int | None = None,
        user_message: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        super().__init__(
            message,
            user_message=user_message,
            suggestion=suggestion,
        )
        self.required_bytes = required_bytes
        self.available_bytes = available_bytes


class FileLockedError(LocalFileConverterError):
    """A file is locked or temporarily unavailable."""


class CorruptedFileError(InputFileError):
    """A file cannot be parsed by the relevant converter."""


class DependencyNotFoundError(LocalFileConverterError):
    """A required local tool is missing."""


class ConversionError(LocalFileConverterError):
    """A conversion failed after validation started."""


class ConversionCancelledError(ConversionError):
    """The user cancelled an active conversion."""
