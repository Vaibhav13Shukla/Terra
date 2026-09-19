"""Unit tests for Sentinel2Provider's STAC-error retry classification (§28).

Regression tests for a bug found by the advisor: pystac_client wraps every
search failure -- including network-level errors -- into
pystac_client.exceptions.APIError, discarding the original exception type.
An earlier version of this module tried to retry on
requests.exceptions.ConnectionError/Timeout directly, which never matched
anything (those exceptions never escape pystac_client). These tests exercise
the actual classification logic offline, with a fake search object, so the
retry-worthiness of a failure is verified by assertion, not by assumption.
"""
from __future__ import annotations

import pytest
from pystac_client.exceptions import APIError

from app.providers.sentinel2 import _classify_stac_search, _TransientStacError


class _FakeSearch:
    def __init__(self, exc: Exception | None = None, items: list | None = None):
        self._exc = exc
        self._items = items or []

    def items(self):
        if self._exc is not None:
            raise self._exc
        return iter(self._items)


def test_network_error_with_no_status_code_is_transient():
    # Mirrors what StacApiIO.request() does for a connection/timeout error:
    # `raise APIError(str(err))` with status_code never set.
    exc = APIError("Connection refused")
    with pytest.raises(_TransientStacError):
        _classify_stac_search(_FakeSearch(exc=exc))


def test_5xx_response_is_transient():
    exc = APIError("Internal Server Error")
    exc.status_code = 503
    with pytest.raises(_TransientStacError):
        _classify_stac_search(_FakeSearch(exc=exc))


def test_4xx_response_is_not_transient_propagates_unchanged():
    exc = APIError("Bad Request")
    exc.status_code = 400
    with pytest.raises(APIError) as exc_info:
        _classify_stac_search(_FakeSearch(exc=exc))
    assert exc_info.value is exc  # same object, not wrapped/reclassified


def test_success_returns_items_unaffected():
    result = _classify_stac_search(_FakeSearch(items=[1, 2, 3]))
    assert result == [1, 2, 3]
