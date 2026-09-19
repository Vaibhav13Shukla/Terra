"""Scene quality filter (§7.4).

Decides which candidate scenes are usable for analysis and records *why* a
scene was rejected, so the evidence panel can explain the decision (§11, §62).
This is deterministic — no LLM involvement.

Note: AOI/scene-footprint intersection is not re-checked here. The Sentinel-2
provider's STAC search already constrains results to the query bbox (see
``app.providers.sentinel2.Sentinel2Provider.search``), and the domain
:class:`~app.domain.models.Scene` does not yet carry per-scene footprint
geometry. When that's added, wire ``app.services.geometry.intersects_bbox``
in here as an explicit check (tracked in docs/adr).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import AOI, Scene

REQUIRED_BANDS = ("red", "nir", "scl")


@dataclass(frozen=True)
class FilterOutcome:
    """Result of filtering a set of candidate scenes."""

    selected: list[Scene]
    rejected: list[Scene]

    @property
    def scenes_used(self) -> int:
        return len(self.selected)

    @property
    def scenes_rejected(self) -> int:
        return len(self.rejected)


def filter_scenes(
    scenes: list[Scene],
    aoi: AOI,
    cloud_threshold: float,
    required_bands: tuple[str, ...] = REQUIRED_BANDS,
) -> FilterOutcome:
    """Apply the authoritative quality filter to candidate scenes.

    A scene is selected only if all are true:
    - cloud_cover is known and below ``cloud_threshold``
    - it has every band in ``required_bands``

    Every rejected scene keeps a human-readable ``rejection_reason``.
    ``aoi`` is accepted for interface stability (future footprint check) but
    is not currently consulted — see module docstring.
    """
    del aoi  # reserved for a future explicit footprint-intersection check

    selected: list[Scene] = []
    rejected: list[Scene] = []

    for scene in scenes:
        reason = _rejection_reason(scene, cloud_threshold, required_bands)
        if reason is None:
            selected.append(scene.model_copy(update={"selected": True}))
        else:
            rejected.append(
                scene.model_copy(update={"selected": False, "rejection_reason": reason})
            )

    return FilterOutcome(selected=selected, rejected=rejected)


def _rejection_reason(
    scene: Scene,
    cloud_threshold: float,
    required_bands: tuple[str, ...],
) -> str | None:
    if scene.cloud_cover is None:
        return "cloud cover unknown"
    if scene.cloud_cover >= cloud_threshold:
        return f"cloud cover {scene.cloud_cover:.1f}% >= threshold {cloud_threshold:.1f}%"

    missing = [b for b in required_bands if b not in scene.assets]
    if missing:
        return f"missing required band(s): {', '.join(missing)}"

    return None
