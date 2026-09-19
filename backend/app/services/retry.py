"""Bounded retry with exponential backoff + jitter (§28).

For transient failures on external network calls (STAC search, COG reads)
only — never for deterministic validation errors, which retrying can't fix
and which should surface immediately. Callers pass the specific exception
types that are worth retrying; anything else propagates on the first
attempt.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 0.5


class RetryExhaustedError(RuntimeError):
    """Raised when all attempts fail. Wraps the last underlying exception so
    callers can inspect the real cause via ``__cause__``."""


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    exceptions: tuple[type[BaseException], ...],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    rand: Callable[[], float] = random.random,
) -> T:
    """Call ``fn()`` up to ``max_attempts`` times, retrying only on the given
    ``exceptions``. Delay before attempt *n* (n>=2) is
    ``base_delay * 2**(n-2)`` plus up to ``base_delay`` of jitter — standard
    exponential backoff with jitter, bounded by ``max_attempts`` (never
    infinite). ``sleep``/``rand`` are injectable for deterministic tests.

    Raises :class:`RetryExhaustedError` (chained to the last exception) if
    every attempt fails. Any exception not in ``exceptions`` propagates
    immediately, unretried — this is what keeps validation errors from being
    uselessly retried (§28)."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except exceptions as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + rand() * base_delay
            sleep(delay)

    raise RetryExhaustedError(
        f"all {max_attempts} attempt(s) failed: {last_exc}"
    ) from last_exc
