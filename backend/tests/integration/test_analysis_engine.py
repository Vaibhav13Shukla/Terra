"""Integration tests: the full deterministic pipeline against the fixtures
provider (discover -> filter -> windowed read -> NDVI -> compare -> evidence).
No network, no AWS — this is Terra's reproducible demo path (§13, §110)."""
from __future__ import annotations

import datetime as dt
import math

import pytest

from app.domain.models import (
    AOI,
    AnalysisRequest,
    AnalysisType,
    DateRange,
)
from app.providers.fixtures import demo_decline_provider
from app.services.analysis_engine import AnalysisError, run_analysis


def _demo_aoi() -> AOI:
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


def test_ndvi_change_matches_canonical_example():
    """The demo scenario is built to reproduce Terra's canonical example:
    NDVI 0.50 -> 0.41, an ~18% decrease."""
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=_demo_aoi(),
        analysis_type=AnalysisType.NDVI_CHANGE,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        comparison_range=DateRange(start=dt.date(2025, 7, 1), end=dt.date(2025, 7, 31)),
        cloud_threshold=20.0,
    )

    result = run_analysis(provider, request)

    assert result.status == "success"
    assert math.isclose(result.metric.current_value, 0.41, abs_tol=1e-3)
    assert math.isclose(result.metric.comparison_value, 0.50, abs_tol=1e-3)
    assert math.isclose(result.metric.percentage_change, -18.0, abs_tol=0.5)
    assert result.metric.absolute_change < 0

    # data quality: 2 usable scenes per period selected, 1 cloudy rejected per period
    assert result.data_quality.scenes_used == 4
    assert result.data_quality.scenes_rejected == 2
    assert result.data_quality.valid_pixel_ratio == pytest.approx(1.0, abs=1e-6)

    # evidence must be traceable
    assert result.evidence.formula == "NDVI = (NIR - RED) / (NIR + RED)"
    assert len(result.evidence.scenes) == 6  # 4 selected + 2 rejected
    assert any(s.rejection_reason for s in result.evidence.scenes if not s.selected)
    assert len(result.evidence.processing_steps) > 0

    # scientific honesty: limitation is always present
    assert any("does not establish" in lim for lim in result.limitations)


def test_ndvi_snapshot_single_period():
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=_demo_aoi(),
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    result = run_analysis(provider, request)
    assert result.status == "success"
    assert math.isclose(result.metric.current_value, 0.41, abs_tol=1e-3)
    assert result.metric.comparison_value is None


def test_no_scenes_returns_failed_not_exception():
    """A date range with zero fixture scenes is a legitimate 'no data' outcome,
    not a crash (§27, §60)."""
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=_demo_aoi(),
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2020, 1, 1), end=dt.date(2020, 1, 31)),
        cloud_threshold=20.0,
    )
    result = run_analysis(provider, request)
    assert result.status == "failed"
    assert "No usable satellite observations" in result.message
    assert result.data_quality.scenes_used == 0


def test_invalid_aoi_raises_analysis_error():
    huge_aoi = AOI(
        coordinates=[[(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)]]
    )
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=huge_aoi,
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
    )
    with pytest.raises(AnalysisError, match="exceeds limit"):
        run_analysis(provider, request)


def test_all_scenes_too_cloudy_in_one_period_is_failed():
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=_demo_aoi(),
        analysis_type=AnalysisType.NDVI_CHANGE,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        comparison_range=DateRange(start=dt.date(2025, 7, 1), end=dt.date(2025, 7, 31)),
        cloud_threshold=3.0,  # below every fixture scene's cloud cover -> none pass
    )
    result = run_analysis(provider, request)
    assert result.status == "failed"
    assert result.data_quality.scenes_used == 0
    assert result.data_quality.scenes_rejected > 0


def test_repeated_identical_query_is_deterministic():
    """Same inputs -> identical result (idempotent computation, §29)."""
    provider = demo_decline_provider()
    request = AnalysisRequest(
        aoi=_demo_aoi(),
        analysis_type=AnalysisType.NDVI_CHANGE,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        comparison_range=DateRange(start=dt.date(2025, 7, 1), end=dt.date(2025, 7, 31)),
    )
    r1 = run_analysis(provider, request)
    r2 = run_analysis(provider, request)
    assert r1.metric.current_value == r2.metric.current_value
    assert r1.metric.percentage_change == r2.metric.percentage_change
