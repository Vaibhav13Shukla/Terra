"""Unit tests for the scene quality filter."""
from __future__ import annotations

import datetime as dt

from app.domain.models import AOI, DataAsset, Scene
from app.services.quality_filter import filter_scenes


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


def _scene(
    id_: str,
    cloud: float | None,
    bands: tuple[str, ...] = ("red", "nir", "scl"),
) -> Scene:
    return Scene(
        id=id_,
        provider="fixtures",
        datetime=dt.datetime(2025, 8, 1, tzinfo=dt.UTC),
        cloud_cover=cloud,
        assets={b: DataAsset(key=b, href=f"fixture://{id_}/{b}") for b in bands},
    )


def test_selects_low_cloud_complete_scene():
    outcome = filter_scenes([_scene("a", 5.0)], _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_used == 1
    assert outcome.scenes_rejected == 0
    assert outcome.selected[0].selected is True


def test_rejects_high_cloud():
    outcome = filter_scenes([_scene("a", 45.0)], _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_used == 0
    assert outcome.scenes_rejected == 1
    assert "cloud cover" in outcome.rejected[0].rejection_reason


def test_rejects_unknown_cloud():
    outcome = filter_scenes([_scene("a", None)], _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_rejected == 1
    assert "unknown" in outcome.rejected[0].rejection_reason


def test_rejects_missing_band():
    outcome = filter_scenes([_scene("a", 5.0, bands=("red",))], _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_rejected == 1
    assert "missing required band" in outcome.rejected[0].rejection_reason
    assert "nir" in outcome.rejected[0].rejection_reason


def test_boundary_cloud_equal_to_threshold_is_rejected():
    # Reject at-or-above threshold, not strictly-above, so cloud_threshold=20
    # means "usable scenes are strictly below 20% cloud".
    outcome = filter_scenes([_scene("a", 20.0)], _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_rejected == 1


def test_mixed_batch_partitions_correctly():
    scenes = [_scene("good", 5.0), _scene("bad", 90.0), _scene("nocloud", None)]
    outcome = filter_scenes(scenes, _aoi(), cloud_threshold=20.0)
    assert outcome.scenes_used == 1
    assert outcome.scenes_rejected == 2
    assert outcome.selected[0].id == "good"
