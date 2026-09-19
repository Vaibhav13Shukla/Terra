"""Unit tests for DynamoDBJobStore, using a tiny in-memory fake table (not
boto3/moto — boto3 is not installed in this environment by design, see
docs/adr/003-ai-orchestration.md). The fake implements exactly the
put_item/get_item/scan surface DynamoDBJobStore's `_Table` Protocol uses, so
these tests exercise the real serialization/deserialization and query logic,
not just that mocked methods were called.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.domain.models import AOI, AnalysisRequest, AnalysisResult, AnalysisType, DateRange
from app.services.dynamodb_job_store import DynamoDBJobStore
from app.services.job_store import JobNotFoundError


class FakeTable:
    """Minimal in-memory stand-in for a boto3 DynamoDB Table resource."""

    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def put_item(self, Item: dict) -> None:
        self._items[Item["job_id"]] = Item

    def get_item(self, Key: dict) -> dict:
        item = self._items.get(Key["job_id"])
        return {"Item": item} if item is not None else {}

    def scan(self, **kwargs) -> dict:
        return {"Items": list(self._items.values())}


def _request() -> AnalysisRequest:
    return AnalysisRequest(
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
        analysis_type=AnalysisType.NDVI_SNAPSHOT,
        date_range=DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
    )


def test_create_stores_job_and_sets_ttl():
    table = FakeTable()
    store = DynamoDBJobStore(table)
    job = store.create(_request())
    stored = table._items[job.job_id]
    assert stored["job_id"] == job.job_id
    assert "ttl" in stored and stored["ttl"] > 0
    assert '"job_id"' in stored["data"]  # JSON blob round-trips the whole job


def test_get_roundtrips_full_fidelity():
    table = FakeTable()
    store = DynamoDBJobStore(table)
    created = store.create(_request())
    fetched = store.get(created.job_id)
    assert fetched.job_id == created.job_id
    assert fetched.request.analysis_type == AnalysisType.NDVI_SNAPSHOT
    assert fetched.request.aoi.bbox() == created.request.aoi.bbox()


def test_get_missing_raises():
    store = DynamoDBJobStore(FakeTable())
    with pytest.raises(JobNotFoundError):
        store.get("does-not-exist")


def test_complete_persists_result():
    table = FakeTable()
    store = DynamoDBJobStore(table)
    job = store.create(_request())
    result = AnalysisResult(analysis_type=AnalysisType.NDVI_SNAPSHOT, status="success")
    completed = store.complete(job.job_id, result)
    assert completed.status.value == "completed"
    refetched = store.get(job.job_id)
    assert refetched.status.value == "completed"
    assert refetched.result.status == "success"


def test_fail_persists_error():
    table = FakeTable()
    store = DynamoDBJobStore(table)
    job = store.create(_request())
    store.fail(job.job_id, "boom")
    refetched = store.get(job.job_id)
    assert refetched.status.value == "failed"
    assert refetched.error == "boom"


def test_list_recent_sorted_and_limited():
    table = FakeTable()
    store = DynamoDBJobStore(table)
    for _ in range(5):
        store.create(_request())
    recent = store.list_recent(limit=3)
    assert len(recent) == 3
    # non-increasing created_at (descending sort)
    timestamps = [j.created_at for j in recent]
    assert timestamps == sorted(timestamps, reverse=True)
