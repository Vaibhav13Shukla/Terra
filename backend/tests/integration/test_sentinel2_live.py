"""Live network test against the real Earth Search STAC API + Sentinel-2 COGs.

Skipped by default (see pyproject.toml's ``network`` marker); run explicitly
with ``pytest -m network``. This is the one test that actually exercises what
the demo depends on: real STAC discovery, real windowed COG reads, real
scale/offset from catalog metadata, and real SCL/red/nir grid alignment.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.domain.models import AOI, DateRange
from app.processing.ndvi import apply_reflectance, compute_ndvi, scl_valid_mask
from app.providers.sentinel2 import Sentinel2Provider

pytestmark = pytest.mark.network


def _aoi() -> AOI:
    # Central California farmland — same AOI verified during the feasibility
    # spike to have low-cloud Sentinel-2 coverage.
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


def test_live_search_returns_scenes_with_required_bands():
    provider = Sentinel2Provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 6, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    assert len(scenes) >= 1
    for scene in scenes:
        assert {"red", "nir", "scl"} <= set(scene.assets)


def test_live_scale_offset_comes_from_stac_not_identity():
    """Regression test for the bug found during development: GDAL band tags
    report (1.0, 0.0) for these COGs, but the real reflectance factors
    (0.0001, -0.1) live in STAC raster:bands and must be used."""
    provider = Sentinel2Provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 6, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    assert scenes, "expected at least one live scene"
    red_asset = scenes[0].assets["red"]
    assert red_asset.scale is not None and red_asset.scale != 1.0
    assert red_asset.offset is not None and red_asset.offset != 0.0


def test_live_scl_aligns_to_red_nir_grid_and_ndvi_is_plausible():
    provider = Sentinel2Provider()
    scenes = provider.search(
        _aoi(),
        DateRange(start=dt.date(2025, 6, 1), end=dt.date(2025, 8, 31)),
        cloud_threshold=20.0,
    )
    assert scenes
    scene = scenes[0]

    red_win = provider.read_window(scene, "red", _aoi())
    nir_win = provider.read_window(scene, "nir", _aoi())
    # SCL is natively 20m vs red/nir's 10m — without alignment these shapes differ.
    scl_win = provider.read_window(scene, "scl", _aoi(), out_shape=red_win.array.shape)

    assert red_win.array.shape == nir_win.array.shape == scl_win.array.shape

    red = apply_reflectance(red_win.array, red_win.scale, red_win.offset)
    nir = apply_reflectance(nir_win.array, nir_win.scale, nir_win.offset)
    valid_mask = scl_valid_mask(scl_win.array)
    field = compute_ndvi(red, nir, valid_mask=valid_mask)

    assert field.stats.valid_pixels > 0
    # Farmland/mixed land cover: NDVI should land in a physically sane range,
    # not e.g. near 0 (which raw, unscaled DN would produce as a false signal).
    assert -0.2 <= field.stats.mean <= 0.95
