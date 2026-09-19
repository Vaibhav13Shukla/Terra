"""Unit tests for Sentinel2Provider's metadata handling — the STAC
``raster:bands`` scale/offset extraction — without any network access.

These pin the fix for a bug found via a live-data check: the COG's own GDAL
band tags report an uninformative (1.0, 0.0) even when the STAC item's
``raster:bands`` field carries the real Sentinel-2 L2A reflectance factors
(0.0001, -0.1). See app.providers.sentinel2 module docstring.
"""
from __future__ import annotations

from app.providers.sentinel2 import Sentinel2Provider


def test_raster_bands_scale_offset_present():
    extra_fields = {
        "raster:bands": [
            {"nodata": 0, "data_type": "uint16", "spatial_resolution": 10,
             "scale": 0.0001, "offset": -0.1}
        ]
    }
    scale, offset = Sentinel2Provider._raster_bands_scale_offset(extra_fields)
    assert scale == 0.0001
    assert offset == -0.1


def test_raster_bands_scale_offset_absent_returns_none():
    # SCL assets typically omit scale/offset entirely (classification, not
    # reflectance) — the caller must fall back to identity, not a wrong default.
    extra_fields = {
        "raster:bands": [
            {"nodata": 0, "data_type": "uint8", "spatial_resolution": 20}
        ]
    }
    scale, offset = Sentinel2Provider._raster_bands_scale_offset(extra_fields)
    assert scale is None
    assert offset is None


def test_raster_bands_scale_offset_no_field_returns_none():
    scale, offset = Sentinel2Provider._raster_bands_scale_offset({})
    assert scale is None
    assert offset is None
