"""Unit tests for the bounded retry/backoff helper (§28)."""
from __future__ import annotations

import pytest

from app.services.retry import RetryExhaustedError, retry_with_backoff


class _TransientError(Exception):
    pass


class _OtherError(Exception):
    pass


def test_succeeds_first_try_no_retry_needed():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    result = retry_with_backoff(fn, exceptions=(_TransientError,), sleep=lambda s: None)
    assert result == "ok"
    assert len(calls) == 1


def test_retries_transient_failures_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _TransientError("flaky")
        return "ok"

    sleeps = []
    result = retry_with_backoff(
        fn,
        exceptions=(_TransientError,),
        max_attempts=3,
        sleep=lambda s: sleeps.append(s),
        rand=lambda: 0.0,
    )
    assert result == "ok"
    assert len(calls) == 3
    assert len(sleeps) == 2  # slept before attempts 2 and 3, not after success


def test_exponential_backoff_delays_increase():
    sleeps = []

    def fn():
        raise _TransientError("always fails")

    with pytest.raises(RetryExhaustedError):
        retry_with_backoff(
            fn,
            exceptions=(_TransientError,),
            max_attempts=3,
            base_delay=1.0,
            sleep=lambda s: sleeps.append(s),
            rand=lambda: 0.0,
        )
    # base_delay * 2**(n-1) for n=1,2 (no jitter since rand()->0)
    assert sleeps == [1.0, 2.0]


def test_gives_up_after_max_attempts_raises_retry_exhausted():
    calls = []

    def fn():
        calls.append(1)
        raise _TransientError("nope")

    with pytest.raises(RetryExhaustedError) as exc_info:
        retry_with_backoff(fn, exceptions=(_TransientError,), max_attempts=3, sleep=lambda s: None)
    assert len(calls) == 3
    assert isinstance(exc_info.value.__cause__, _TransientError)


def test_non_matching_exception_propagates_immediately_no_retry():
    """§28: never retry deterministic validation errors — only the exception
    types explicitly named as retryable get retried."""
    calls = []

    def fn():
        calls.append(1)
        raise _OtherError("not transient")

    with pytest.raises(_OtherError):
        retry_with_backoff(fn, exceptions=(_TransientError,), sleep=lambda s: None)
    assert len(calls) == 1  # no retry attempted


def test_invalid_max_attempts_rejected():
    with pytest.raises(ValueError):
        retry_with_backoff(lambda: None, exceptions=(_TransientError,), max_attempts=0)
