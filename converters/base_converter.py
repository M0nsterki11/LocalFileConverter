from collections.abc import Callable

from app.exceptions import ConversionCancelledError
from app.i18n import translate


CancelCheck = Callable[[], bool]


def check_cancelled(
    cancel_check: CancelCheck | None,
) -> None:
    """Stop conversion when the user requested cancellation."""
    if cancel_check is not None and cancel_check():
        raise ConversionCancelledError(
            translate(
                "BaseConverter",
                "The conversion was cancelled by the user.",
            )
        )
