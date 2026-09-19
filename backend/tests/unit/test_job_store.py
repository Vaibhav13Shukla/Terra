"""Unit tests for the in-memory job store."""
from __future__ import annotations

import datetime as dt

import pytest

from app.domain.models import (
    AOI,
    AnalysisRequest,
    AnalysisResult,
    AnalysisType,
    DateRange,
    JobStatus,
)
from app.services.job_store import InMemoryJobStore, JobNotFoundError


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


def test_create_returns_job_in_created_status():
    store = InMemoryJobStore()
    job = store.create(_request())
    assert job.status == JobStatus.CREATED
    assert job.job_id
    assert job.result is None


def test_get_roundtrips():
    store = InMemoryJobStore()
    created = store.create(_request())
    fetched = store.get(created.job_id)
    assert fetched.job_id == created.job_id


def test_get_missing_raises():
    store = InMemoryJobStore()
    with pytest.raises(JobNotFoundError):
        store.get("does-not-exist")


def test_update_status_advances_and_touches_updated_at():
    store = InMemoryJobStore()
    job = store.create(_request())
    original_updated = job.updated_at
    updated = store.update_status(job.job_id, JobStatus.PROCESSING)
    assert updated.status == JobStatus.PROCESSING
    assert updated.updated_at >= original_updated


def test_complete_sets_result_and_status():
    store = InMemoryJobStore()
    job = store.create(_request())
    result = AnalysisResult(analysis_type=AnalysisType.NDVI_SNAPSHOT, status="success")
    completed = store.complete(job.job_id, result)
    assert completed.status == JobStatus.COMPLETED
    assert completed.result is result


def test_fail_sets_error_and_status():
    store = InMemoryJobStore()
    job = store.create(_request())
    failed = store.fail(job.job_id, "boom")
    assert failed.status == JobStatus.FAILED
    assert failed.error == "boom"


def test_list_recent_orders_newest_first():
    store = InMemoryJobStore()
    j1 = store.create(_request())
    j2 = store.create(_request())
    recent = store.list_recent()
    assert recent[0].job_id == j2.job_id
    assert recent[1].job_id == j1.job_id


def test_list_recent_respects_limit():
    store = InMemoryJobStore()
    for _ in range(5):
        store.create(_request())
    assert len(store.list_recent(limit=2)) == 2
