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

# Cap on scenes actually read per period. Measured against live Sentinel-2
# data: ~4-6s per scene for red+nir+scl windowed reads (network + GDAL
# overhead per asset). An AOI with abundant low-cloud coverage can return 20
# candidate scenes per period; reading all of them serially took >120s and
# was the direct cause of a request timeout during development (see
# docs/adr/002-processing-runtime.md). Capping to the least-cloudy N keeps
# worst-case latency bounded and avoids downloading data with no
# statistical benefit to a simple mean (§18, §67 — cost discipline).
MAX_SCENES_PER_PERIOD = 4


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


def cap_scenes(
    outcome: FilterOutcome, max_scenes: int = MAX_SCENES_PER_PERIOD
) -> FilterOutcome:
    """Cap ``outcome.selected`` to the ``max_scenes`` least-cloudy scenes.

    Scenes beyond the cap move to ``rejected`` with an explicit reason, so
    they remain visible in the evidence panel (§7.4) rather than silently
    vanishing. A no-op when ``selected`` is already at or under the cap.
    Scenes with unknown cloud_cover never reach here (they're already
    rejected by :func:`filter_scenes`), so sorting is well-defined.
    """
    if len(outcome.selected) <= max_scenes:
        return outcome

    ranked = sorted(outcome.selected, key=lambda s: s.cloud_cover)  # type: ignore[arg-type]
    kept, overflow = ranked[:max_scenes], ranked[max_scenes:]

    capped_overflow = [
        s.model_copy(
            update={
                "selected": False,
                "rejection_reason": (
                    f"more than {max_scenes} usable scenes were available; "
                    f"used the {max_scenes} with lowest cloud cover"
                ),
            }
        )
        for s in overflow
    ]
    return FilterOutcome(selected=kept, rejected=outcome.rejected + capped_overflow)


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
