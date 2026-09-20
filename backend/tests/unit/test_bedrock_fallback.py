"""Unit tests for the Bedrock adapter's mandatory graceful-fallback behavior
(§61: the core workflow must never depend on Bedrock being reachable).

boto3 is an AWS-deploy-time dependency, not needed for the deterministic core, so
it may or may not be installed where the tests run. These tests must not depend on
that: they simulate its absence explicitly (`sys.modules["boto3"] = None` makes
`import boto3` raise ImportError). Otherwise, on a machine that has boto3 they
would send a real InvokeModel request to AWS under whatever credentials the
developer has configured. They exercise exactly the path every real deployment
hits whenever Bedrock is disabled, mis-configured, or throttled: a clean
BedrockUnavailableError, never a raw exception leaking out.
"""
from __future__ import annotations

import sys

import pytest

from app.agents.bedrock import BedrockUnavailableError, parse_intent_bedrock
from app.domain.models import AnalysisResult, AnalysisType


@pytest.fixture(autouse=True)
def _boto3_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)


def test_parse_intent_bedrock_raises_clean_error_without_boto3():
    with pytest.raises(BedrockUnavailableError, match="boto3"):
        parse_intent_bedrock("How has vegetation changed?", "some-model", "us-west-2")


def test_explain_result_bedrock_raises_clean_error_without_boto3():
    from app.agents.bedrock import explain_result_bedrock

    result = AnalysisResult(analysis_type=AnalysisType.NDVI_SNAPSHOT, status="success")
    with pytest.raises(BedrockUnavailableError, match="boto3"):
        explain_result_bedrock(result, "some-model", "us-west-2")
