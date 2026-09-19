"""Contract tests for TERRA_PROCESSING_MODE=async: create_analysis should
enqueue and return immediately (status CREATED) rather than running the
pipeline inline. Uses a fake queue injected via app.api.deps (no boto3/SQS
required — see app.services.analysis_queue)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import app
from app.config.settings import get_settings
from app.domain.models import AnalysisRequest
from app.services.analysis_queue import AnalysisQueue


class FakeAnalysisQueue(AnalysisQueue):
    def __init__(self) -> None:
        self.enqueued: list[dict] = []

    def enqueue(self, job_id: str, request: AnalysisRequest) -> None:
        self.enqueued.append({"job_id": job_id, "request": request})


@pytest.fixture(autouse=True)
def _reset_state():
    deps.reset_state()
    yield
    deps.reset_state()
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _demo_aoi() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [-120.60, 36.95],
                [-120.55, 36.95],
                [-120.55, 37.00],
                [-120.60, 37.00],
                [-120.60, 36.95],
            ]
        ],
    }


def test_create_analysis_enqueues_and_returns_created_in_async_mode(client: TestClient, monkeypatch):
    monkeypatch.setenv("TERRA_PROCESSING_MODE", "async")
    monkeypatch.setenv("ANALYSES_QUEUE_URL", "https://sqs.example/q")
    get_settings.cache_clear()
    fake_queue = FakeAnalysisQueue()
    deps._analysis_queue = fake_queue

    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "created"
    assert job["result"] is None
    assert len(fake_queue.enqueued) == 1
    assert fake_queue.enqueued[0]["job_id"] == job["job_id"]


def test_create_analysis_async_mode_without_queue_url_returns_500(
    client: TestClient, monkeypatch
):
    monkeypatch.setenv("TERRA_PROCESSING_MODE", "async")
    monkeypatch.delenv("ANALYSES_QUEUE_URL", raising=False)
    get_settings.cache_clear()
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 500
