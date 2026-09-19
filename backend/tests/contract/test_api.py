"""Contract tests for the Terra API (§35 — pins request/response schemas and
HTTP status codes). Runs entirely against the in-memory job store and the
built-in providers (fixtures + Sentinel2Provider, unused here) — no network.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import app
from app.domain.models import AOI, DateRange, Scene
from app.providers.base import DataProvider, ProviderRegistry


@pytest.fixture(autouse=True)
def _reset_state():
    deps.reset_state()
    yield
    deps.reset_state()


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


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_responses_carry_security_headers(client: TestClient):
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"


def test_list_providers_includes_builtins(client: TestClient):
    resp = client.get("/v1/providers")
    assert resp.status_code == 200
    providers = resp.json()["providers"]
    assert "fixtures" in providers
    assert "sentinel-2-l2a" in providers


def test_list_scenes_against_fixtures_provider(client: TestClient):
    resp = client.get(
        "/v1/scenes",
        params={
            "min_lon": -120.60,
            "min_lat": 36.95,
            "max_lon": -120.55,
            "max_lat": 37.00,
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "cloud_threshold": 20,
            "provider": "fixtures",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenes_used"] == 2
    assert body["scenes_rejected"] == 1
    assert body["rejected"][0]["rejection_reason"] is not None


def test_list_scenes_invalid_bbox_returns_400(client: TestClient):
    resp = client.get(
        "/v1/scenes",
        params={
            "min_lon": 0.0,
            "min_lat": 0.0,
            "max_lon": 2.0,
            "max_lat": 2.0,
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "provider": "fixtures",
        },
    )
    assert resp.status_code == 400


def test_list_scenes_unknown_provider_returns_400(client: TestClient):
    resp = client.get(
        "/v1/scenes",
        params={
            "min_lon": -120.60,
            "min_lat": 36.95,
            "max_lon": -120.55,
            "max_lat": 37.00,
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "provider": "does-not-exist",
        },
    )
    assert resp.status_code == 400


def test_create_analysis_direct_structured_request(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "comparison_start_date": "2025-07-01",
        "comparison_end_date": "2025-07-31",
        "analysis": "ndvi_change",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "completed"
    assert job["result"]["status"] == "success"
    assert job["result"]["metric"]["percentage_change"] == pytest.approx(-18.0, abs=0.5)
    assert job["result"]["explanation"]  # deterministic explainer populated it
    assert "decreased" in job["result"]["explanation"]


def test_create_analysis_via_natural_language_question(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "comparison_start_date": "2025-07-01",
        "comparison_end_date": "2025-07-31",
        "question": "How has vegetation changed here?",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "success"


def test_create_analysis_unsupported_question_returns_422(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "question": "Find the best place to build a nuclear reactor.",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 422
    assert "isn't about vegetation" in resp.json()["detail"]


def test_create_analysis_invalid_aoi_returns_400(client: TestClient):
    huge_aoi = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]],
    }
    body = {
        "aoi": huge_aoi,
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 400
    assert "exceeds limit" in resp.json()["detail"]


def test_create_analysis_missing_analysis_and_question_returns_422(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 422  # FastAPI's own request-validation error


def test_create_analysis_unknown_provider_returns_400(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "does-not-exist",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 400


def test_get_analysis_roundtrip_and_evidence(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    created = client.post("/v1/analyses", json=body).json()
    job_id = created["job_id"]

    fetched = client.get(f"/v1/analyses/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["job_id"] == job_id

    evidence = client.get(f"/v1/analyses/{job_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["formula"] == "NDVI = (NIR - RED) / (NIR + RED)"


def test_get_analysis_missing_returns_404(client: TestClient):
    resp = client.get("/v1/analyses/does-not-exist")
    assert resp.status_code == 404


def test_list_analyses_returns_recent(client: TestClient):
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    client.post("/v1/analyses", json=body)
    client.post("/v1/analyses", json=body)
    resp = client.get("/v1/analyses")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_ndvi_change_without_explicit_comparison_dates_defaults_to_prior_period(
    client: TestClient,
):
    """§7.2: default comparison is an equal-length immediately-preceding period."""
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_change",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 200
    job = resp.json()
    # comparison window should be July 2025 (31 days ending 2025-07-31)
    comparison_range = job["request"]["comparison_range"]
    assert comparison_range["end"] == "2025-07-31"


class _AlwaysFailsProvider(DataProvider):
    """Regression fixture: a provider whose search() raises an unexpected
    exception (e.g. what RetryExhaustedError looks like after every retry
    attempt is exhausted on a real STAC outage)."""

    name = "always-fails"
    supported_bands = ("red", "nir", "scl")

    def search(self, aoi: AOI, date_range: DateRange, cloud_threshold: float, limit: int = 20):
        raise RuntimeError("simulated STAC outage")

    def read_window(self, scene: Scene, band_key: str, aoi: AOI, out_shape=None):
        raise AssertionError("should never be reached")


def test_unexpected_provider_failure_fails_job_not_stranded_in_created(
    client: TestClient,
):
    """Regression test: an unexpected exception from the provider (not
    AnalysisError) must still resolve the job to FAILED, not leave it stuck
    in CREATED forever with no way for a poller to know what happened."""
    deps.bootstrap_providers()
    ProviderRegistry.register(_AlwaysFailsProvider())

    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "always-fails",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 502

    # The job must exist and be resolved to failed, not stuck in "created".
    jobs = client.get("/v1/analyses").json()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["status"] == "failed"
    assert "simulated STAC outage" in job["error"]

    fetched = client.get(f"/v1/analyses/{job['job_id']}").json()
    assert fetched["status"] == "failed"
