"""Unit tests for geometry validation."""
from __future__ import annotations

import pytest

from app.domain.models import AOI
from app.services.geometry import (
    InvalidGeometryError,
    intersects_bbox,
    validate_aoi,
)


def _square(lon0: float, lat0: float, size: float) -> AOI:
    return AOI(
        coordinates=[
            [
                (lon0, lat0),
                (lon0 + size, lat0),
                (lon0 + size, lat0 + size),
                (lon0, lat0 + size),
                (lon0, lat0),
            ]
        ]
    )


def test_valid_small_aoi():
    aoi = _square(-120.60, 36.95, 0.05)  # ~5km square
    info = validate_aoi(aoi)
    assert info.area_km2 > 0
    assert info.bbox[0] == -120.60
    assert -120.60 < info.centroid[0] < -120.55


def test_aoi_too_large_rejected():
    aoi = _square(0.0, 0.0, 1.0)  # ~1 degree ~ 12000 km^2 > limit
    with pytest.raises(InvalidGeometryError, match="exceeds limit"):
        validate_aoi(aoi)


def test_self_intersecting_rejected():
    # bowtie polygon
    aoi = AOI(
        coordinates=[
            [
                (0.0, 0.0),
                (0.01, 0.01),
                (0.01, 0.0),
                (0.0, 0.01),
                (0.0, 0.0),
            ]
        ]
    )
    with pytest.raises(InvalidGeometryError):
        validate_aoi(aoi)


def test_unclosed_ring_rejected_at_model():
    # AOI model itself enforces closed rings
    with pytest.raises(ValueError):
        AOI(coordinates=[[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]])


def test_intersects_bbox_true_and_false():
    aoi = _square(-120.60, 36.95, 0.05)
    assert intersects_bbox(aoi, (-120.58, 36.96, -120.50, 37.10)) is True
    assert intersects_bbox(aoi, (10.0, 10.0, 11.0, 11.0)) is False
