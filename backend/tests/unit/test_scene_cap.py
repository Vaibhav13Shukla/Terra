"""Unit tests for the scene cap (§18, §67 — bound worst-case read cost)."""
from __future__ import annotations

import datetime as dt

from app.domain.models import DataAsset, Scene
from app.services.quality_filter import FilterOutcome, cap_scenes


def _scene(id_: str, cloud: float) -> Scene:
    return Scene(
        id=id_,
        provider="fixtures",
        datetime=dt.datetime(2025, 8, 1, tzinfo=dt.UTC),
        cloud_cover=cloud,
        assets={"red": DataAsset(key="red", href=f"fixture://{id_}/red")},
        selected=True,
    )


def test_noop_when_at_or_under_cap():
    outcome = FilterOutcome(selected=[_scene("a", 5.0), _scene("b", 8.0)], rejected=[])
    result = cap_scenes(outcome, max_scenes=4)
    assert result.scenes_used == 2
    assert result.scenes_rejected == 0


def test_keeps_least_cloudy_and_rejects_overflow_with_reason():
    scenes = [_scene(f"s{i}", cloud=float(i)) for i in range(6)]  # clouds 0..5
    outcome = FilterOutcome(selected=scenes, rejected=[])
    result = cap_scenes(outcome, max_scenes=3)
    assert result.scenes_used == 3
    kept_ids = {s.id for s in result.selected}
    assert kept_ids == {"s0", "s1", "s2"}  # 3 lowest cloud cover
    assert result.scenes_rejected == 3
    for s in result.rejected:
        assert s.selected is False
        assert "lowest cloud cover" in s.rejection_reason


def test_preserves_existing_rejected_scenes():
    already_rejected = _scene("bad", 90.0)
    outcome = FilterOutcome(
        selected=[_scene(f"s{i}", float(i)) for i in range(5)],
        rejected=[already_rejected],
    )
    result = cap_scenes(outcome, max_scenes=2)
    assert result.scenes_used == 2
    assert result.scenes_rejected == 4  # 1 original + 3 capped overflow
    assert already_rejected.id in {s.id for s in result.rejected}
