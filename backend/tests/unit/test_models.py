"""Unit tests for the domain model validation rules."""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.domain.models import (
    AOI,
    AnalysisRequest,
    AnalysisType,
    DateRange,
)


def _aoi() -> AOI:
    return AOI(
        coordinates=[
            [
                (-120.60, 36.95),
                (-120.55, 36.95),
                (-120.55, 37.00),
                (-120.60, 37.00),
                (-120.60, 36.95),
            ]
        ]
    )


def test_daterange_orders():
    with pytest.raises(ValidationError):
        DateRange(start=dt.date(2025, 8, 31), end=dt.date(2025, 8, 1))


def test_daterange_stac_format():
    dr = DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31))
    s = dr.as_stac_datetime()
    assert s == "2025-08-01T00:00:00Z/2025-08-31T23:59:59Z"


def test_ndvi_change_requires_comparison():
    with pytest.raises(ValidationError, match="comparison_range"):
        AnalysisRequest(
            aoi=_aoi(),
            analysis_type=AnalysisType.NDVI_CHANGE,
            date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        )


def test_ndvi_snapshot_needs_no_comparison():
    req = AnalysisRequest(
        aoi=_aoi(),
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
    )
    assert req.comparison_range is None
    assert req.cloud_threshold == 20.0


def test_cloud_threshold_bounds():
    with pytest.raises(ValidationError):
        AnalysisRequest(
            aoi=_aoi(),
            analysis_type=AnalysisType.NDVI_SNAPSHOT,
            date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
            cloud_threshold=150.0,
        )


def test_aoi_bbox():
    assert _aoi().bbox() == (-120.60, 36.95, -120.55, 37.00)


def test_latitude_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AOI(coordinates=[[(0.0, 95.0), (1.0, 95.0), (1.0, 96.0), (0.0, 96.0), (0.0, 95.0)]])
