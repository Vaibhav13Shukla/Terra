"""NDVI computation and change statistics — pure, deterministic, numpy-only.

This module is intentionally free of any I/O, provider, or AWS concern so it can
be unit-tested exhaustively and reused unchanged in Lambda. All scientific
correctness rules from the brief (§19, §20) live here:

* NDVI = (NIR - RED) / (NIR + RED)
* zero/negative denominators, nodata and invalid pixels are masked, never faked
* every result carries data-quality info (valid pixel count/ratio)

Reflectance scaling: Sentinel-2 L2A COGs store integer DN. The provider supplies
per-band ``scale`` and ``offset`` (from STAC ``raster:bands``). Because NDVI is a
ratio, a common *scale* cancels — but the post-2022 processing-baseline BOA
*offset* does **not** cancel, so it must be applied before the ratio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Sentinel-2 Scene Classification (SCL) codes we treat as usable surface for NDVI.
# 4 = vegetation, 5 = bare soil, 6 = water, 7 = unclassified. Everything else
# (nodata, saturated, cloud shadow, cloud medium/high, cirrus, snow) is rejected.
DEFAULT_VALID_SCL_CLASSES: frozenset[int] = frozenset({4, 5, 6, 7})


@dataclass(frozen=True)
class NDVIStats:
    """Summary statistics for an NDVI array over valid pixels only."""

    mean: float
    median: float
    minimum: float
    maximum: float
    valid_pixels: int
    total_pixels: int

    @property
    def valid_ratio(self) -> float:
        if self.total_pixels == 0:
            return 0.0
        return self.valid_pixels / self.total_pixels


@dataclass(frozen=True)
class NDVIField:
    """A computed NDVI array plus its stats. ``array`` is a masked array where
    invalid pixels are masked out (not zeroed)."""

    array: np.ma.MaskedArray
    stats: NDVIStats
    extra_masked: dict[str, int] = field(default_factory=dict)


def apply_reflectance(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    """Convert integer DN to surface reflectance: ``reflectance = dn*scale + offset``.

    Returns float32. Callers pass the scale/offset the provider read from the
    scene's ``raster:bands`` metadata (defaults 0.0001 / -0.1 for S2 L2A baseline
    >= 04.00, i.e. DN 1000 == reflectance 0.0)."""
    return dn.astype(np.float32) * np.float32(scale) + np.float32(offset)


def scl_valid_mask(
    scl: np.ndarray, valid_classes: frozenset[int] = DEFAULT_VALID_SCL_CLASSES
) -> np.ndarray:
    """Boolean mask: ``True`` where the SCL pixel is a usable surface class."""
    valid = np.zeros(scl.shape, dtype=bool)
    for cls in valid_classes:
        valid |= scl == cls
    return valid


def compute_ndvi(
    red: np.ndarray,
    nir: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> NDVIField:
    """Compute NDVI from red and NIR reflectance arrays.

    Parameters
    ----------
    red, nir:
        Same-shape float arrays of surface reflectance (already scaled).
    valid_mask:
        Optional boolean array (True = keep). Typically an SCL-derived mask.
        Pixels that are False here, or that are non-finite, or whose denominator
        is ~0, are masked out of the result.
    """
    if red.shape != nir.shape:
        raise ValueError(f"red/nir shape mismatch: {red.shape} vs {nir.shape}")
    if valid_mask is not None and valid_mask.shape != red.shape:
        raise ValueError("valid_mask shape must match band shape")

    red = red.astype(np.float64)
    nir = nir.astype(np.float64)

    denom = nir + red
    # Invalid where denominator ~0, or inputs non-finite.
    invalid = ~np.isfinite(red) | ~np.isfinite(nir) | (np.abs(denom) < 1e-9)
    if valid_mask is not None:
        invalid |= ~valid_mask

    # Compute safely; masked positions get a placeholder that we then mask.
    safe_denom = np.where(invalid, 1.0, denom)
    ndvi = (nir - red) / safe_denom
    # Physically NDVI is in [-1, 1]; values outside indicate bad pixels.
    invalid |= ~np.isfinite(ndvi) | (ndvi < -1.0) | (ndvi > 1.0)

    masked = np.ma.masked_array(ndvi, mask=invalid)
    stats = _stats(masked)
    return NDVIField(array=masked, stats=stats)


def _stats(masked: np.ma.MaskedArray) -> NDVIStats:
    total = int(masked.size)
    valid = int(masked.count())
    if valid == 0:
        return NDVIStats(
            mean=float("nan"),
            median=float("nan"),
            minimum=float("nan"),
            maximum=float("nan"),
            valid_pixels=0,
            total_pixels=total,
        )
    compressed = masked.compressed()
    return NDVIStats(
        mean=float(np.mean(compressed)),
        median=float(np.median(compressed)),
        minimum=float(np.min(compressed)),
        maximum=float(np.max(compressed)),
        valid_pixels=valid,
        total_pixels=total,
    )


@dataclass(frozen=True)
class ChangeResult:
    """Result of comparing two scalar metric values."""

    current_value: float
    comparison_value: float
    absolute_change: float
    percentage_change: float


def percentage_change(current: float, previous: float) -> ChangeResult:
    """Absolute and percentage change of ``current`` relative to ``previous``.

    ``percentage_change = (current - previous) / |previous| * 100``.
    Raises if ``previous`` is 0 (percentage change is undefined) — we surface that
    rather than returning a misleading number."""
    if not np.isfinite(current) or not np.isfinite(previous):
        raise ValueError("cannot compute change from non-finite values")
    if previous == 0:
        raise ValueError("percentage change undefined when previous value is 0")
    abs_change = current - previous
    pct = (abs_change / abs(previous)) * 100.0
    return ChangeResult(
        current_value=current,
        comparison_value=previous,
        absolute_change=abs_change,
        percentage_change=pct,
    )
