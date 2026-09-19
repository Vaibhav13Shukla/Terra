"""Shared "explain a computed result" step, used by both the synchronous API
path (app.api.main) and the async worker (app.worker.handler) so the two
processing modes produce identical output (§53 — one implementation, not two
copies that can drift). Never computes anything itself — see app.agents.
"""
from __future__ import annotations

from app.agents.bedrock import BedrockUnavailableError, explain_result_bedrock
from app.agents.explain import explain_result
from app.config.settings import Settings
from app.domain.models import AnalysisResult


def explain(result: AnalysisResult, settings: Settings) -> str:
    """Explain via Bedrock if enabled, else the deterministic template
    explainer. Never lets a Bedrock failure break the caller (§61)."""
    if settings.bedrock_enabled:
        try:
            return explain_result_bedrock(result, settings.bedrock_model_id, settings.aws_region)
        except BedrockUnavailableError:
            pass  # fall through to deterministic explainer
    return explain_result(result)
