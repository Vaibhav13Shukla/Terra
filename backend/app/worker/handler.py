"""Async worker Lambda — the SQS-triggered counterpart to the API's
synchronous processing path (see app.api.main.create_analysis and
docs/adr/002-processing-runtime.md).

Only reached when ``TERRA_PROCESSING_MODE=async``: the API enqueues
``{"job_id", "request"}`` to SQS and returns the job in CREATED status; this
handler is the Lambda's SQS event-source-mapping target, runs the exact same
deterministic pipeline (``app.services.analysis_engine.run_analysis``) as the
synchronous path, and resolves the job via the same
:class:`~app.services.job_store.JobStore` — so ``GET /v1/analyses/{id}``
behaves identically regardless of which mode produced the result.

Never imports `boto3` itself: consuming an SQS-triggered Lambda event needs
no AWS SDK call at all (the Lambda runtime already parsed the event into a
plain dict), so this module — and its tests — are fully offline, matching
every other module in this codebase (§61).

A message whose processing raises is resolved to a FAILED job rather than
re-raised, so one bad request can't become a poison-pill message stuck
retrying against the queue forever; only a JobStore failure (a real
infrastructure problem) propagates, letting SQS retry/DLQ that message as
usual.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.api.deps import bootstrap_providers, get_job_store, get_provider
from app.config.settings import get_settings
from app.domain.models import AnalysisRequest
from app.observability.logging import timed_event
from app.services.analysis_engine import run_analysis
from app.services.explain_service import explain

logger = logging.getLogger(__name__)


def process_message(body: dict[str, Any]) -> None:
    """Process one decoded SQS message body: run the analysis and resolve
    the job to COMPLETED or FAILED. Never raises for an analysis-side
    failure (bad input, no data, provider outage) — only if the job store
    itself is unreachable, which should propagate so SQS retries."""
    job_id = body["job_id"]
    request = AnalysisRequest.model_validate(body["request"])
    settings = get_settings()

    bootstrap_providers()
    job_store = get_job_store()

    try:
        provider = get_provider(request.provider)
        with timed_event(
            "worker_analysis_completed",
            job_id=job_id,
            analysis_type=request.analysis_type,
            provider=request.provider,
        ):
            result = run_analysis(provider, request)
        result.explanation = explain(result, settings)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see module docstring
        job_store.fail(job_id, str(exc))
        return

    job_store.complete(job_id, result)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for the SQS event source mapping."""
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            process_message(body)
        except Exception:
            logger.exception("failed to process SQS record %s", record.get("messageId"))
            raise
    return {"batchItemFailures": []}
