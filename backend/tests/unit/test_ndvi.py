"""Unit tests for the NDVI processing engine (pure numpy)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from app.processing.ndvi import (
    apply_reflectance,
    compute_ndvi,
    percentage_change,
    scl_valid_mask,
)


def test_ndvi_known_values():
    # NDVI = (NIR - RED)/(NIR + RED). red=0.1, nir=0.5 -> 0.4/0.6 = 0.6667
    red = np.full((4, 4), 0.1)
    nir = np.full((4, 4), 0.5)
    field = compute_ndvi(red, nir)
    assert field.stats.valid_pixels == 16
    assert math.isclose(field.stats.mean, 0.4 / 0.6, rel_tol=1e-6)
    assert math.isclose(field.stats.minimum, field.stats.maximum, rel_tol=1e-9)


def test_ndvi_masks_zero_denominator():
    red = np.array([[0.0, 0.2], [0.3, 0.0]])
    nir = np.array([[0.0, 0.4], [0.5, 0.0]])  # top-left & bottom-right: denom 0
    field = compute_ndvi(red, nir)
    assert field.stats.valid_pixels == 2
    assert field.stats.total_pixels == 4
    assert math.isclose(field.stats.valid_ratio, 0.5)


def test_ndvi_masks_non_finite_and_out_of_range():
    red = np.array([[0.1, np.nan], [0.1, 0.1]])
    nir = np.array([[0.5, 0.5], [np.inf, 0.5]])
    field = compute_ndvi(red, nir)
    # only two pixels are finite and in-range
    assert field.stats.valid_pixels == 2


def test_ndvi_all_invalid_returns_nan_stats():
    red = np.zeros((3, 3))
    nir = np.zeros((3, 3))
    field = compute_ndvi(red, nir)
    assert field.stats.valid_pixels == 0
    assert math.isnan(field.stats.mean)
    assert field.stats.valid_ratio == 0.0


def test_ndvi_shape_mismatch_raises():
    with pytest.raises(ValueError):
        compute_ndvi(np.zeros((2, 2)), np.zeros((3, 3)))


def test_valid_mask_excludes_clouds():
    red = np.full((2, 2), 0.1)
    nir = np.full((2, 2), 0.5)
    mask = np.array([[True, False], [True, False]])  # right column masked out
    field = compute_ndvi(red, nir, valid_mask=mask)
    assert field.stats.valid_pixels == 2


def test_scl_valid_mask_default_classes():
    # 4=veg 5=soil kept; 8,9=cloud, 3=shadow, 0=nodata rejected
    scl = np.array([[4, 8], [5, 3], [9, 0]])
    mask = scl_valid_mask(scl)
    assert mask.tolist() == [[True, False], [True, False], [False, False]]


def test_apply_reflectance_offset_matters():
    # S2 L2A baseline >=04.00: DN 1000 -> reflectance 0.0
    dn = np.array([[1000, 2000]], dtype=np.uint16)
    refl = apply_reflectance(dn, scale=0.0001, offset=-0.1)
    assert math.isclose(float(refl[0, 0]), 0.0, abs_tol=1e-6)
    assert math.isclose(float(refl[0, 1]), 0.1, abs_tol=1e-6)


def test_percentage_change_basic():
    r = percentage_change(current=0.41, previous=0.50)
    assert math.isclose(r.absolute_change, -0.09, abs_tol=1e-9)
    assert math.isclose(r.percentage_change, -18.0, abs_tol=1e-6)


def test_percentage_change_zero_previous_raises():
    with pytest.raises(ValueError):
        percentage_change(current=0.4, previous=0.0)


def test_percentage_change_non_finite_raises():
    with pytest.raises(ValueError):
        percentage_change(current=float("nan"), previous=0.5)


def test_offset_does_not_cancel_in_ndvi():
    """Regression guard for §20: the BOA offset changes NDVI, so it must be
    applied. NDVI computed from offset-corrected reflectance differs from NDVI
    computed from raw DN treated as reflectance."""
    red_dn = np.array([[1200.0]])
    nir_dn = np.array([[3000.0]])
    ndvi_raw = compute_ndvi(red_dn, nir_dn).stats.mean  # wrong: no offset
    red_r = apply_reflectance(red_dn, 0.0001, -0.1)
    nir_r = apply_reflectance(nir_dn, 0.0001, -0.1)
    ndvi_corrected = compute_ndvi(red_r, nir_r).stats.mean
    assert not math.isclose(ndvi_raw, ndvi_corrected, rel_tol=1e-3)
