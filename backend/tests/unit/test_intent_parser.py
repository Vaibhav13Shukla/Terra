"""Unit tests for the deterministic intent parser (§37 evaluation examples)."""
from __future__ import annotations

from app.agents.intent_parser import extract_last_n_days, parse_intent
from app.domain.models import AnalysisType


def test_vegetation_change_question_maps_to_ndvi_change():
    intent = parse_intent("How has vegetation changed here over the last 30 days?")
    assert intent.supported is True
    assert intent.analysis_type == AnalysisType.NDVI_CHANGE


def test_plain_vegetation_question_maps_to_snapshot():
    intent = parse_intent("What is the vegetation index here?")
    assert intent.supported is True
    assert intent.analysis_type == AnalysisType.NDVI_SNAPSHOT


def test_irrigation_certainty_question_flags_overclaim_but_still_supported():
    """§37: 'Tell me if this farm definitely needs irrigation' — the system
    should not claim certainty from NDVI alone, but this still maps to a
    supported vegetation analysis with an explicit caution."""
    intent = parse_intent("Tell me if this farm definitely needs irrigation.")
    assert intent.supported is True
    assert intent.reason is not None
    assert "does not by itself prove" in intent.reason


def test_unrelated_question_is_unsupported():
    """§37: 'Find the best place to build a nuclear reactor' must not be
    silently reinterpreted — it should be a clear unsupported response."""
    intent = parse_intent("Find the best place to build a nuclear reactor.")
    assert intent.supported is False
    assert intent.analysis_type is None
    assert "isn't about vegetation" in intent.reason


def test_empty_question_is_unsupported():
    intent = parse_intent("")
    assert intent.supported is False


def test_extract_last_n_days():
    assert extract_last_n_days("vegetation change over the last 45 days") == 45
    assert extract_last_n_days("vegetation change") is None
