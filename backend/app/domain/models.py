"""Terra domain model.

Typed, validated core objects shared across providers, processing, services
and the API layer. Everything that crosses a module boundary is defined here so
no part of the system passes around untyped dicts (see docs/adr/001).

Coordinates are WGS84 (EPSG:4326) longitude/latitude. Dates are ISO ``YYYY-MM-DD``.
"""
from __future__ import annotations

import datetime as _dt
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class AnalysisType(StrEnum):
    """Analyses Terra can actually perform. Adding a member is a deliberate act:
    it must be wired into the processing engine and covered by tests."""

    NDVI_CHANGE = "ndvi_change"
    NDVI_SNAPSHOT = "ndvi_snapshot"


class JobStatus(StrEnum):
    """Lifecycle of an analysis job."""

    CREATED = "created"
    DISCOVERING = "discovering"
    PROCESSING = "processing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #

Longitude = Annotated[float, Field(ge=-180.0, le=180.0)]
Latitude = Annotated[float, Field(ge=-90.0, le=90.0)]


class AOI(BaseModel):
    """Area of Interest as a GeoJSON-style Polygon (WGS84).

    We accept the subset of GeoJSON we actually support — a single Polygon —
    rather than the full spec, so validation can be strict and total. Geometry
    correctness (winding, self-intersection, area bounds) is enforced by
    :mod:`app.services.geometry`, not here; this type only guarantees shape.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["Polygon"] = "Polygon"
    # GeoJSON polygon: list of linear rings; ring = list of [lon, lat] pairs.
    coordinates: list[list[tuple[Longitude, Latitude]]] = Field(
        ..., description="GeoJSON Polygon coordinates: [ [ [lon,lat], ... ] ]"
    )

    @field_validator("coordinates")
    @classmethod
    def _ring_is_closed_and_sized(
        cls, rings: list[list[tuple[float, float]]]
    ) -> list[list[tuple[float, float]]]:
        if not rings:
            raise ValueError("polygon must have at least one ring")
        outer = rings[0]
        if len(outer) < 4:
            raise ValueError(
                "polygon ring must have >= 4 positions (closed ring)"
            )
        if outer[0] != outer[-1]:
            raise ValueError("polygon ring must be closed (first == last position)")
        return rings

    def bbox(self) -> tuple[float, float, float, float]:
        """Return (min_lon, min_lat, max_lon, max_lat) over the outer ring."""
        outer = self.coordinates[0]
        lons = [p[0] for p in outer]
        lats = [p[1] for p in outer]
        return (min(lons), min(lats), max(lons), max(lats))


# --------------------------------------------------------------------------- #
# Time
# --------------------------------------------------------------------------- #


class DateRange(BaseModel):
    """Inclusive date range, ISO ``YYYY-MM-DD``."""

    model_config = ConfigDict(extra="forbid")

    start: _dt.date
    end: _dt.date

    @model_validator(mode="after")
    def _ordered(self) -> DateRange:
        if self.end < self.start:
            raise ValueError("end date must be on or after start date")
        return self

    def as_stac_datetime(self) -> str:
        """Format for a STAC ``datetime`` range query."""
        return f"{self.start.isoformat()}T00:00:00Z/{self.end.isoformat()}T23:59:59Z"


# --------------------------------------------------------------------------- #
# Scenes / assets
# --------------------------------------------------------------------------- #


class DataAsset(BaseModel):
    """A single retrievable band/asset within a scene.

    ``scale``/``offset`` are the reflectance conversion factors for this asset,
    when the provider can supply them (e.g. from STAC ``raster:bands``
    metadata). They are NOT reliably present in the COG's own GDAL band tags —
    see :mod:`app.providers.sentinel2` — so providers should populate them from
    catalog metadata during ``search()`` rather than inferring them at read
    time. ``None`` means "unknown"; the reader falls back to documented
    provider defaults.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., description="Logical band key, e.g. 'red', 'nir', 'scl'")
    href: str = Field(..., description="COG URL (https:// or s3://)")
    scale: float | None = Field(default=None, description="Reflectance scale factor")
    offset: float | None = Field(default=None, description="Reflectance additive offset")


class Scene(BaseModel):
    """A candidate satellite observation returned by a provider's search.

    ``selected``/``rejection_reason`` are filled by the quality filter so the
    same object can carry evidence about why it was or wasn't used."""

    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    datetime: _dt.datetime
    cloud_cover: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Scene cloud cover percent"
    )
    assets: dict[str, DataAsset] = Field(default_factory=dict)
    selected: bool = False
    rejection_reason: str | None = None


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


class AnalysisRequest(BaseModel):
    """Fully-specified, validated analysis request (the deterministic contract).

    The natural-language layer's job is to *produce* one of these; it never
    performs the analysis itself (see docs/adr/003)."""

    model_config = ConfigDict(extra="forbid")

    aoi: AOI
    analysis_type: AnalysisType
    date_range: DateRange
    comparison_range: DateRange | None = Field(
        default=None,
        description="Baseline period for change analyses; required for ndvi_change.",
    )
    cloud_threshold: float = Field(
        default=20.0, ge=0.0, le=100.0, description="Max scene cloud cover percent"
    )
    provider: str = Field(default="sentinel-2-l2a")

    @model_validator(mode="after")
    def _comparison_required_for_change(self) -> AnalysisRequest:
        if self.analysis_type == AnalysisType.NDVI_CHANGE and self.comparison_range is None:
            raise ValueError("ndvi_change requires a comparison_range")
        return self


# --------------------------------------------------------------------------- #
# Results / evidence
# --------------------------------------------------------------------------- #


class Metric(BaseModel):
    """A single computed metric with optional before/after comparison."""

    model_config = ConfigDict(extra="forbid")

    name: str
    current_value: float
    comparison_value: float | None = None
    absolute_change: float | None = None
    percentage_change: float | None = None
    unit: str | None = None


class DataQuality(BaseModel):
    """Data-quality summary attached to every result (§62 — never hide uncertainty)."""

    model_config = ConfigDict(extra="forbid")

    scenes_used: int = Field(ge=0)
    scenes_rejected: int = Field(ge=0)
    cloud_threshold: float
    valid_pixel_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class ProcessingStep(BaseModel):
    """One recorded step in the pipeline, for the technical-details/evidence panel."""

    model_config = ConfigDict(extra="forbid")

    name: str
    detail: str
    duration_ms: float | None = None


class Evidence(BaseModel):
    """Traceability for a result: which scenes, formula, and steps produced it."""

    model_config = ConfigDict(extra="forbid")

    scenes: list[Scene] = Field(default_factory=list)
    formula: str | None = None
    processing_steps: list[ProcessingStep] = Field(default_factory=list)
    bands_used: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Decision-ready output of an analysis job."""

    model_config = ConfigDict(extra="forbid")

    analysis_type: AnalysisType
    status: Literal["success", "partial", "failed"]
    metric: Metric | None = None
    data_quality: DataQuality | None = None
    evidence: Evidence | None = None
    limitations: list[str] = Field(default_factory=list)
    message: str | None = None


class AnalysisJob(BaseModel):
    """Persistent job record (mirrors the DynamoDB item shape)."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus = JobStatus.CREATED
    request: AnalysisRequest
    result: AnalysisResult | None = None
    error: str | None = None
    created_at: _dt.datetime
    updated_at: _dt.datetime

    def touch(self, status: JobStatus) -> AnalysisJob:
        self.status = status
        self.updated_at = _dt.datetime.now(_dt.UTC)
        return self


def _example() -> dict[str, Any]:  # pragma: no cover - doc helper
    """Illustrative payload used in docs/tests."""
    return {
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
        "analysis_type": "ndvi_change",
        "date_range": {"start": "2025-08-01", "end": "2025-08-31"},
        "comparison_range": {"start": "2025-07-01", "end": "2025-07-31"},
        "cloud_threshold": 20,
    }
