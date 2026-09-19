"""The deployed entry point: API Gateway HTTP API (payload v2) -> Mangum -> FastAPI.

Every other API test uses FastAPI's TestClient, which never exercises the
Lambda adapter. These tests drive `app.api.main.handler` with the event shape
API Gateway actually sends, so a deploy-time routing mistake is caught offline.

Why the stage matters (see infra/template.yaml, TerraHttpApi): on a *named*
stage ("dev") API Gateway sends rawPath "/dev/health", which the app does not
route -> 404 for every endpoint. The template therefore uses the "$default"
stage, whose paths carry no prefix. `test_named_stage_prefix_is_not_routed`
pins that behaviour so nobody re-adds a StageName without noticing.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.api import deps
from app.api.main import handler

pytestmark = pytest.mark.skipif(handler is None, reason="mangum not installed")


@pytest.fixture(autouse=True)
def _reset_state():
    deps.reset_state()
    yield
    deps.reset_state()


def _event(method: str, path: str, body: dict | None = None, stage: str = "$default") -> dict:
    """A minimal API Gateway HTTP API v2 (payload format 2.0) proxy event."""
    return {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json", "host": "abc123.execute-api.us-west-2.amazonaws.com"},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abc123",
            "domainName": "abc123.execute-api.us-west-2.amazonaws.com",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.10",
                "userAgent": "pytest",
            },
            "requestId": "req-1",
            "stage": stage,
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1767225600000,
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def _invoke(event: dict) -> tuple[int, dict]:
    response = handler(event, SimpleNamespace(aws_request_id="req-1"))
    return response["statusCode"], json.loads(response["body"])


def test_health_through_lambda_handler():
    status, body = _invoke(_event("GET", "/health"))
    assert status == 200
    assert body["status"] == "ok"


def test_providers_listed_through_lambda_handler():
    status, body = _invoke(_event("GET", "/v1/providers"))
    assert status == 200
    assert "fixtures" in json.dumps(body)


def test_analysis_round_trip_through_lambda_handler():
    """POST then GET the job, as the browser does — over the Lambda event shape."""
    request = {
        "aoi": {
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
        },
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "comparison_start_date": "2025-07-01",
        "comparison_end_date": "2025-07-31",
        "analysis": "ndvi_change",
        "provider": "fixtures",
    }
    status, job = _invoke(_event("POST", "/v1/analyses", request))
    assert status == 200
    assert job["status"] == "completed"

    status, fetched = _invoke(_event("GET", f"/v1/analyses/{job['job_id']}"))
    assert status == 200
    assert fetched["job_id"] == job["job_id"]
    assert fetched["result"]["metric"]["percentage_change"] == pytest.approx(-18.0, abs=0.5)


def test_unknown_job_is_404_through_lambda_handler():
    status, _ = _invoke(_event("GET", "/v1/analyses/does-not-exist"))
    assert status == 404


def test_named_stage_prefix_is_not_routed():
    """Documents WHY infra uses the "$default" stage.

    With a named stage API Gateway prepends "/<stage>" to rawPath. The app has no
    such prefix, so the request 404s. If this test ever starts failing because the
    app now strips a stage prefix, the template comment on TerraHttpApi should be
    revisited — not this test silently deleted.
    """
    status, _ = _invoke(_event("GET", "/dev/health", stage="dev"))
    assert status == 404
