"""Unit tests for the deterministic fixtures provider."""
from __future__ import annotations

import datetime as dt
import math

import pytest

from app.domain.models import AOI, DateRange, Scene
from app.processing.ndvi import compute_ndvi
from app.providers.fixtures import demo_decline_provider


def _aoi() -> AOI:
    return AOI(
        coordinates=[
            [
                (-120.60, 36.95),
                (-120.55, 36.95),
                (-120.55, 37.00),
                (-120.60, 37.00),
                (-120.60, 36.95),
            ]
        ]
    )


def test_search_respects_date_range_but_not_cloud_threshold():
    """search() returns all date-matching candidates, cloudy or not — cloud
    filtering is the authoritative job of app.services.quality_filter, so
    that rejected scenes keep an evidence-visible reason (§7.4)."""
    provider = demo_decline_provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    ids = {s.id for s in scenes}
    assert ids == {"fx-aug-01", "fx-aug-02", "fx-aug-cloudy"}


def test_search_july_period():
    provider = demo_decline_provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 7, 1), end=dt.date(2025, 7, 31)),
        cloud_threshold=20.0,
    )
    ids = {s.id for s in scenes}
    assert ids == {"fx-jul-01", "fx-jul-02", "fx-jul-cloudy"}


def test_read_window_yields_expected_ndvi():
    provider = demo_decline_provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 8, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    scene = next(s for s in scenes if s.id == "fx-aug-01")
    red = provider.read_window(scene, "red", _aoi())
    nir = provider.read_window(scene, "nir", _aoi())
    field = compute_ndvi(red.array, nir.array)
    assert math.isclose(field.stats.mean, 0.41, abs_tol=1e-3)


def test_unknown_scene_raises():
    provider = demo_decline_provider()
    fake = Scene(id="nope", provider="fixtures", datetime=dt.datetime.now(dt.UTC))
    with pytest.raises(KeyError):
        provider.read_window(fake, "red", _aoi())
