"""Unit tests for the Bedrock adapter's mandatory graceful-fallback behavior
(§61: the core workflow must never depend on Bedrock being reachable).

boto3 is not installed in the default dev/test environment (by design — it's
an AWS-deploy-time dependency, not needed for the deterministic core), so
these tests exercise exactly the path every real deployment hits whenever
Bedrock is disabled, mis-configured, or throttled: a clean
BedrockUnavailableError, never a raw exception leaking out.
"""
from __future__ import annotations

import pytest

from app.agents.bedrock import BedrockUnavailableError, parse_intent_bedrock
from app.domain.models import AnalysisResult, AnalysisType


def test_parse_intent_bedrock_raises_clean_error_without_boto3():
    with pytest.raises(BedrockUnavailableError, match="boto3"):
        parse_intent_bedrock("How has vegetation changed?", "some-model", "us-west-2")


def test_explain_result_bedrock_raises_clean_error_without_boto3():
    from app.agents.bedrock import explain_result_bedrock

    result = AnalysisResult(analysis_type=AnalysisType.NDVI_SNAPSHOT, status="success")
    with pytest.raises(BedrockUnavailableError, match="boto3"):
        explain_result_bedrock(result, "some-model", "us-west-2")
