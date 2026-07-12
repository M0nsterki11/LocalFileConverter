from collections.abc import Callable


CancelCheck = Callable[[], bool]


class ConversionCancelledError(Exception):
    """Konverziju je prekinuo korisnik."""


def check_cancelled(
    cancel_check: CancelCheck | None,
) -> None:
    """Prekida konverziju ako je korisnik zatražio prekid."""
    if cancel_check is not None and cancel_check():
        raise ConversionCancelledError(
            "Konverziju je prekinuo korisnik."
        )