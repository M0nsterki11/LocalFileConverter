from collections.abc import Callable

from app.exceptions import ConversionCancelledError


CancelCheck = Callable[[], bool]


def check_cancelled(
    cancel_check: CancelCheck | None,
) -> None:
    """Prekida konverziju ako je korisnik zatražio prekid."""
    if cancel_check is not None and cancel_check():
        raise ConversionCancelledError(
            "Konverziju je prekinuo korisnik."
        )
