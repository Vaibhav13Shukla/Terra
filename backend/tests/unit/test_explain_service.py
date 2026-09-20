"""The explain step must be observable: when Bedrock is enabled, an operator has to
be able to tell from the logs whether the text came from Bedrock or from the
deterministic fallback. A silent fallback made a mis-configured deployment
(missing IAM permission, retired model id) look identical to a working one."""
from __future__ import annotations

import pytest

from app.agents.bedrock import BedrockUnavailableError
from app.agents.explain import explain_result
from app.config.settings import Settings
from app.domain.models import AnalysisResult, AnalysisType, DataQuality, Metric
from app.services import explain_service


@pytest.fixture
def result() -> AnalysisResult:
    return AnalysisResult(
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
        limitations=["NDVI is a vegetation-vigor proxy; it does not establish drought."],
    )


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        explain_service, "log_event", lambda event, **fields: captured.append((event, fields))
    )
    return captured


def test_bedrock_disabled_uses_template_and_logs_nothing(result, events):
    text = explain_service.explain(result, Settings(bedrock_enabled=False))
    assert text == explain_result(result)
    assert events == []


def test_bedrock_success_is_logged(result, events, monkeypatch):
    monkeypatch.setattr(explain_service, "explain_result_bedrock", lambda *a, **k: "from bedrock")
    settings = Settings(bedrock_enabled=True, bedrock_model_id="test-model")

    assert explain_service.explain(result, settings) == "from bedrock"
    assert events == [("bedrock_explain_ok", {"model_id": "test-model"})]


def test_bedrock_failure_falls_back_and_says_why(result, events, monkeypatch):
    def boom(*args, **kwargs):
        raise BedrockUnavailableError("AccessDeniedException: no access to the model")

    monkeypatch.setattr(explain_service, "explain_result_bedrock", boom)
    settings = Settings(bedrock_enabled=True, bedrock_model_id="test-model")

    # The caller still gets a correct, deterministic explanation...
    assert explain_service.explain(result, settings) == explain_result(result)
    # ...and the operator can see that Bedrock was skipped, and why.
    assert len(events) == 1
    name, fields = events[0]
    assert name == "bedrock_explain_fallback"
    assert fields["model_id"] == "test-model"
    assert "AccessDeniedException" in fields["error"]
