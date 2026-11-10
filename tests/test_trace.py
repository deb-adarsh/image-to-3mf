from __future__ import annotations

import numpy as np
import pytest

from image_to_3mf.trace import trace_mask


def test_square_traces_to_one_polygon(square_mask):
    geom = trace_mask(square_mask, smooth=0)
    assert len(geom.geoms) == 1
    assert geom.area == pytest.approx(900, rel=0.02)
    assert geom.bounds == pytest.approx((10, 10, 40, 40), abs=0.5)


def test_hole_is_kept(donut_mask):
    geom = trace_mask(donut_mask, smooth=0)
    assert len(geom.geoms) == 1
    assert len(geom.geoms[0].interiors) == 1
    assert geom.area == pytest.approx(40 * 40 - 20 * 20, rel=0.02)


def test_island_inside_hole_is_separate_part(donut_mask):
    donut_mask[27:33, 27:33] = True
    geom = trace_mask(donut_mask, smooth=0)
    assert len(geom.geoms) == 2
    assert geom.area == pytest.approx(40 * 40 - 20 * 20 + 6 * 6, rel=0.03)


def test_image_orientation_is_preserved():
    mask = np.zeros((20, 60), dtype=bool)
    mask[2:6, 10:50] = True  # wide bar near the top
    xmin, ymin, xmax, ymax = trace_mask(mask, smooth=0).bounds
    assert (xmin, xmax) == pytest.approx((10, 50), abs=0.5)
    assert (ymin, ymax) == pytest.approx((2, 6), abs=0.5)


def test_shape_touching_image_edge():
    mask = np.zeros((20, 20), dtype=bool)
    mask[0:10, 0:10] = True
    geom = trace_mask(mask, smooth=0)
    assert geom.bounds == pytest.approx((0, 0, 10, 10), abs=0.5)


def test_smoothing_rounds_a_circle():
    yy, xx = np.mgrid[0:100, 0:100]
    mask = (xx - 50) ** 2 + (yy - 50) ** 2 <= 40**2
    geom = trace_mask(mask, smooth=1.0)
    assert len(geom.geoms) == 1
    assert geom.is_valid
    assert geom.area == pytest.approx(np.pi * 40**2, rel=0.02)
    assert len(geom.geoms[0].exterior.coords) > 16  # curves were sampled, not left as corners


def test_specks_are_dropped():
    mask = np.zeros((20, 20), dtype=bool)
    mask[5, 5] = True
    assert trace_mask(mask, turdsize=2).is_empty


def test_bad_smooth_raises(square_mask):
    with pytest.raises(ValueError):
        trace_mask(square_mask, smooth=2.0)
