"""Optional Amazon Bedrock adapter for intent parsing and explanation (§9, §61).

This module is never imported at package-init time and never imports `boto3`
at module scope, so the default (offline) test suite and local development
work with zero AWS setup even when `boto3` isn't installed. It is only reached
when `Settings.bedrock_enabled` is true AND the caller explicitly asks for it.

Every function here can fail (missing credentials, model not enabled in the
account/region, throttling, malformed model output) and MUST fail into
:class:`BedrockUnavailableError` so the caller falls back to the deterministic
path in app.agents.intent_parser / app.agents.explain — the core workflow must
never depend on Bedrock being reachable (§61).

The LLM is used ONLY for: mapping a question to a structured intent, and
explaining an already-computed result. It never performs a calculation — see
app.services.analysis_engine, which this module does not import.
"""
from __future__ import annotations

import json

from app.domain.models import AnalysisIntent, AnalysisResult

_INTENT_SYSTEM_PROMPT = """You map a user's Earth Observation question to a \
structured analysis intent. You do not perform any calculation yourself.

Terra currently supports exactly two analyses:
- "ndvi_change": the question asks how vegetation/NDVI changed over time \
(comparison between two periods)
- "ndvi_snapshot": the question asks about current vegetation/NDVI state, \
no comparison implied

If the question is not about vegetation/land-cover at all, respond with \
supported=false and a short, clear reason. If the question asks for a \
determination that a single vegetation index cannot prove (e.g. "definitely \
needs irrigation"), still classify it as supported but say so in "reason" \
so the caller can add an explicit no-certainty caution.

Respond with ONLY a JSON object matching this exact schema, no other text:
{"supported": bool, "analysis_type": "ndvi_change" | "ndvi_snapshot" | null, \
"reason": string | null}"""

_EXPLAIN_SYSTEM_PROMPT = """You explain an already-computed satellite \
vegetation analysis result to a non-technical user, in 2-4 plain-text \
sentences (no markdown, no JSON — prose only).

Use ONLY the JSON data given to you. Do not invent observations, dates, or \
values not present in the data. Do not claim causes (drought, irrigation \
failure, soil moisture) that the data does not establish — NDVI is a \
vegetation-vigor proxy only. State the metric, its direction/magnitude, and \
the data quality (scenes used/rejected) if present."""


class BedrockUnavailableError(RuntimeError):
    """Raised whenever Bedrock cannot be used for this call — missing
    dependency, disabled by config, or a runtime/API failure. Callers should
    catch this and fall back to the deterministic path (§61)."""


def _client(region: str):
    """Lazily construct a Bedrock Runtime client. Raises
    :class:`BedrockUnavailableError` if `boto3` isn't installed or the client
    cannot be constructed — never propagates a raw boto3/botocore exception."""
    try:
        import boto3
    except ImportError as exc:
        raise BedrockUnavailableError(
            "boto3 is not installed; Bedrock is unavailable. "
            "Install it (see backend/requirements.txt) to enable Bedrock."
        ) from exc
    try:
        return boto3.client("bedrock-runtime", region_name=region)
    except Exception as exc:  # noqa: BLE001 - any client construction failure -> fallback
        raise BedrockUnavailableError(f"could not create Bedrock client: {exc}") from exc


def _invoke_text(model_id: str, region: str, system_prompt: str, user_text: str) -> str:
    """Invoke a Bedrock Anthropic-family model and return its raw text reply.
    Raises :class:`BedrockUnavailableError` on any failure."""
    client = _client(region)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }
    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]
    except Exception as exc:  # noqa: BLE001 - any Bedrock/runtime failure -> fallback
        raise BedrockUnavailableError(f"Bedrock invocation failed: {exc}") from exc


def parse_intent_bedrock(
    question: str, model_id: str, region: str, cloud_threshold: float = 20.0
) -> AnalysisIntent:
    """Bedrock-backed intent parsing. Raises :class:`BedrockUnavailableError`
    on any failure so the caller can fall back to
    :func:`app.agents.intent_parser.parse_intent`."""
    text = _invoke_text(model_id, region, _INTENT_SYSTEM_PROMPT, question)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BedrockUnavailableError(
            f"Bedrock returned non-JSON intent output: {text[:200]!r}"
        ) from exc
    try:
        return AnalysisIntent(
            supported=bool(data["supported"]),
            analysis_type=data.get("analysis_type"),
            cloud_threshold=cloud_threshold,
            reason=data.get("reason"),
        )
    except Exception as exc:  # noqa: BLE001 - schema validation failure -> fallback
        raise BedrockUnavailableError(
            f"Bedrock intent response failed schema validation: {exc}"
        ) from exc


def explain_result_bedrock(result: AnalysisResult, model_id: str, region: str) -> str:
    """Bedrock-backed explanation. Raises :class:`BedrockUnavailableError` on
    any failure so the caller can fall back to
    :func:`app.agents.explain.explain_result`."""
    text = _invoke_text(
        model_id, region, _EXPLAIN_SYSTEM_PROMPT, result.model_dump_json()
    )
    if not text.strip():
        raise BedrockUnavailableError("Bedrock explanation response was empty")
    return text.strip()
