"""Unit tests for the async worker Lambda handler (app.worker.handler).

Fully offline: runs against the fixtures provider and the in-memory job
store, exactly like tests/contract/test_api.py does for the synchronous
path, and constructs SQS-shaped event dicts by hand rather than invoking
boto3/moto (consuming an SQS event needs no AWS SDK call — see the module
docstring in app.worker.handler).
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app.api import deps
from app.domain.models import AOI, AnalysisRequest, AnalysisType, DateRange
from app.worker.handler import handler, process_message


@pytest.fixture(autouse=True)
def _reset_state():
    deps.reset_state()
    yield
    deps.reset_state()


def _request(analysis_type=AnalysisType.NDVI_SNAPSHOT, **overrides) -> AnalysisRequest:
    fields = dict(
        aoi=AOI(
            coordinates=[
                [
                    (-120.60, 36.95),
                    (-120.55, 36.95),
                    (-120.55, 37.00),
                    (-120.60, 37.00),
                    (-120.60, 36.95),
                ]
            ]
        ),
        analysis_type=analysis_type,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        provider="fixtures",
    )
    fields.update(overrides)
    return AnalysisRequest(**fields)


def _sqs_event(job_id: str, request: AnalysisRequest) -> dict:
    body = json.dumps({"job_id": job_id, "request": json.loads(request.model_dump_json())})
    return {"Records": [{"messageId": "m-1", "body": body}]}


def test_process_message_completes_job_successfully():
    job_store = deps.get_job_store()
    request = _request()
    job = job_store.create(request)

    process_message({"job_id": job.job_id, "request": json.loads(request.model_dump_json())})

    completed = job_store.get(job.job_id)
    assert completed.status.value == "completed"
    assert completed.result.status == "success"
    assert completed.result.explanation  # deterministic explainer populated it


def test_process_message_marks_job_failed_on_unknown_provider():
    job_store = deps.get_job_store()
    request = _request(provider="fixtures")
    job = job_store.create(request)

    body = json.loads(request.model_dump_json())
    body["provider"] = "does-not-exist"
    process_message({"job_id": job.job_id, "request": body})

    failed = job_store.get(job.job_id)
    assert failed.status.value == "failed"
    assert failed.error


def test_handler_processes_sqs_event_end_to_end():
    job_store = deps.get_job_store()
    request = _request()
    job = job_store.create(request)

    event = _sqs_event(job.job_id, request)
    result = handler(event, context=None)

    assert result == {"batchItemFailures": []}
    completed = job_store.get(job.job_id)
    assert completed.status.value == "completed"


def test_handler_reraises_on_malformed_record_for_sqs_retry():
    with pytest.raises(json.JSONDecodeError):
        handler({"Records": [{"messageId": "bad", "body": "not-json"}]}, context=None)
