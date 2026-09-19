"""Unit tests for the deterministic result explainer."""
from __future__ import annotations

from app.agents.explain import explain_result
from app.domain.models import (
    AnalysisResult,
    AnalysisType,
    DataQuality,
    Metric,
)


def test_explain_change_result_mentions_direction_and_magnitude():
    result = AnalysisResult(
        analysis_type=AnalysisType.NDVI_CHANGE,
        status="success",
        metric=Metric(
            name="NDVI",
            current_value=0.41,
            comparison_value=0.50,
            absolute_change=-0.09,
            percentage_change=-18.0,
        ),
        data_quality=DataQuality(scenes_used=4, scenes_rejected=2, cloud_threshold=20.0),
        limitations=["NDVI is a vegetation-vigor proxy; does not establish drought."],
    )
    text = explain_result(result)
    assert "decreased 18.0%" in text
    assert "4 usable satellite observations" in text
    assert "2 rejected for quality" in text
    assert "does not establish drought" in text


def test_explain_snapshot_result():
    result = AnalysisResult(
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        status="success",
        metric=Metric(name="NDVI", current_value=0.55),
        data_quality=DataQuality(scenes_used=1, scenes_rejected=0, cloud_threshold=20.0),
    )
    text = explain_result(result)
    assert "0.550" in text
    assert "limited" in text  # single-scene confidence caveat


def test_explain_failed_result_uses_message():
    result = AnalysisResult(
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        status="failed",
        message="No usable satellite observations were found.",
    )
    assert explain_result(result) == "No usable satellite observations were found."


def test_explain_never_invents_a_number_not_on_the_result():
    """Regression guard: the explainer must not introduce any numeric claim
    that isn't already present on the AnalysisResult (§18, §20)."""
    result = AnalysisResult(
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        status="success",
        metric=Metric(name="NDVI", current_value=0.3333),
    )
    text = explain_result(result)
    assert "0.333" in text
    # no percentage-change language should appear for a snapshot
    assert "%" not in text
