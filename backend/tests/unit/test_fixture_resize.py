"""Unit test for the fixtures provider's nearest-neighbor resize helper, which
mirrors Sentinel2Provider's real SCL-to-red/nir grid alignment (§17)."""
from __future__ import annotations

import numpy as np

from app.providers.fixtures import _nearest_resize


def test_nearest_resize_upsamples_categorical_values_without_inventing_classes():
    # 2x2 "SCL-like" grid upsampled to 4x4 (matching a 2x higher-res band).
    small = np.array([[4, 5], [6, 7]], dtype=np.uint8)
    big = _nearest_resize(small, (4, 4))
    assert big.shape == (4, 4)
    # every value in the output must be one of the original class codes —
    # nearest-neighbor never interpolates/invents a class value
    assert set(np.unique(big)) <= {4, 5, 6, 7}
    # top-left quadrant should be the original top-left value
    assert (big[:2, :2] == 4).all()


def test_nearest_resize_noop_when_shape_already_matches():
    arr = np.ones((4, 4))
    result = _nearest_resize(arr, (4, 4))
    assert result.shape == (4, 4)
    assert (result == 1).all()
