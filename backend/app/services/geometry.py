"""Geometry validation and helpers — centralized so no other module reasons
about CRS or winding on its own (§17).

Inputs are always WGS84 (EPSG:4326) lon/lat, matching :class:`app.domain.models.AOI`.
We validate that a polygon is well-formed, not self-intersecting, and within a
sane area budget (a hackathon demo must not trigger a full-tile download).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Polygon, shape
from shapely.validation import explain_validity

from app.domain.models import AOI

# Guard rails for demo cost/correctness. A degree^2 near the equator is huge;
# we cap AOI area well below a Sentinel-2 tile (~110km x 110km).
MAX_AOI_AREA_KM2 = 2500.0  # 50km x 50km
MIN_AOI_AREA_KM2 = 0.0001  # ~100 m^2, guards against a degenerate point
_KM2_PER_DEG2_AT_EQUATOR = 111.32 * 111.32


class InvalidGeometryError(ValueError):
    """Raised when an AOI fails geometric validation."""


@dataclass(frozen=True)
class GeometryInfo:
    """Derived, validated facts about an AOI."""

    bbox: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    area_km2: float
    centroid: tuple[float, float]  # (lon, lat)


def to_shapely(aoi: AOI) -> Polygon:
    """Convert a validated :class:`AOI` to a shapely Polygon."""
    geom = shape(aoi.model_dump())
    if not isinstance(geom, Polygon):
        raise InvalidGeometryError("AOI must be a single Polygon")
    return geom


def _approx_area_km2(poly: Polygon) -> float:
    """Approximate polygon area in km^2 using a local equirectangular scaling.

    Good enough for an area *budget check* (not for scientific area reporting):
    we scale longitude by cos(latitude) at the centroid to reduce distortion."""
    centroid_lat = poly.centroid.y
    lon_scale = math.cos(math.radians(centroid_lat))
    # shapely area is in deg^2; correct for longitude convergence.
    deg2 = poly.area * lon_scale
    return deg2 * _KM2_PER_DEG2_AT_EQUATOR


def validate_aoi(aoi: AOI) -> GeometryInfo:
    """Validate an AOI and return derived geometry info.

    Raises :class:`InvalidGeometryError` for self-intersecting, empty, or
    out-of-budget polygons."""
    poly = to_shapely(aoi)

    if poly.is_empty:
        raise InvalidGeometryError("AOI polygon is empty")
    if not poly.is_valid:
        raise InvalidGeometryError(f"AOI polygon is invalid: {explain_validity(poly)}")

    area = _approx_area_km2(poly)
    if area > MAX_AOI_AREA_KM2:
        raise InvalidGeometryError(
            f"AOI area {area:.1f} km^2 exceeds limit {MAX_AOI_AREA_KM2:.0f} km^2; "
            "select a smaller area."
        )
    if area < MIN_AOI_AREA_KM2:
        raise InvalidGeometryError(
            f"AOI area {area:.6f} km^2 is too small to analyze."
        )

    minx, miny, maxx, maxy = poly.bounds
    return GeometryInfo(
        bbox=(minx, miny, maxx, maxy),
        area_km2=area,
        centroid=(poly.centroid.x, poly.centroid.y),
    )


def intersects_bbox(
    aoi: AOI, other_bbox: tuple[float, float, float, float]
) -> bool:
    """Whether the AOI intersects another WGS84 bbox (min_lon,min_lat,max_lon,max_lat)."""
    poly = to_shapely(aoi)
    minx, miny, maxx, maxy = other_bbox
    other = Polygon(
        [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy), (minx, miny)]
    )
    return poly.intersects(other)
