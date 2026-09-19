"""Contract tests for auth enforcement at the API layer.

Auth is OFF by default (app.config.settings.Settings.auth_enabled = False),
so every other contract test in this suite runs unauthenticated, exactly as
a real deployment does until AUTH_ENABLED=true is set. These tests exercise
the *enabled* path in isolation, overriding the settings/require_auth
dependency rather than talking to a real Cognito pool.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import app
from app.auth.dependencies import AuthenticatedUser, require_auth
from app.config.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_state():
    deps.reset_state()
    yield
    deps.reset_state()
    app.dependency_overrides.clear()


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


def test_analyses_endpoints_are_open_when_auth_disabled(client: TestClient):
    # Default settings: auth_enabled=False. No Authorization header sent.
    resp = client.get("/v1/analyses")
    assert resp.status_code == 200


def _enabled_settings() -> Settings:
    return Settings(
        auth_enabled=True,
        cognito_user_pool_id="us-west-2_TestPool",
        cognito_app_client_id="test-client-id",
    )


def test_missing_token_returns_401_when_auth_enabled(client: TestClient):
    app.dependency_overrides[get_settings] = _enabled_settings
    resp = client.get("/v1/analyses")
    assert resp.status_code == 401


def test_auth_enabled_without_pool_configured_returns_500(client: TestClient):
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=True)
    resp = client.get("/v1/analyses")
    assert resp.status_code == 500


def test_valid_token_allows_access_when_auth_enabled(client: TestClient):
    app.dependency_overrides[require_auth] = lambda: AuthenticatedUser(subject="user-1")
    resp = client.get("/v1/analyses")
    assert resp.status_code == 200


def test_create_analysis_requires_auth_when_enabled(client: TestClient):
    app.dependency_overrides[get_settings] = _enabled_settings
    body = {
        "aoi": _demo_aoi(),
        "start_date": "2025-08-01",
        "end_date": "2025-08-31",
        "analysis": "ndvi_snapshot",
        "provider": "fixtures",
    }
    resp = client.post("/v1/analyses", json=body)
    assert resp.status_code == 401


def test_health_and_scenes_remain_public_when_auth_enabled(client: TestClient):
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=True)
    assert client.get("/health").status_code == 200
    resp = client.get(
        "/v1/scenes",
        params={
            "min_lon": -120.60,
            "min_lat": 36.95,
            "max_lon": -120.55,
            "max_lat": 37.00,
            "start_date": "2025-08-01",
            "end_date": "2025-08-31",
            "provider": "fixtures",
        },
    )
    assert resp.status_code == 200
