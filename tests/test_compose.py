from __future__ import annotations

import pytest
from shapely.geometry import MultiPolygon, box

from image_to_3mf.compose import scale_to_mm


def test_scales_image_width_and_flips_y():
    # A 10 x 5 px box at the top-left of a 100 x 50 px image.
    geom = MultiPolygon([box(0, 0, 10, 5)])
    result = scale_to_mm(geom, image_width_px=100, image_height_px=50, width_mm=200)
    # 2 mm per px; the top of the image becomes the top in y-up space.
    assert result.bounds == pytest.approx((0, 90, 20, 100))
    assert result.area == pytest.approx(10 * 5 * 4)


def test_outer_rings_are_counter_clockwise():
    geom = MultiPolygon([box(0, 0, 10, 5)])
    result = scale_to_mm(geom, 100, 50, 100)
    assert result.geoms[0].exterior.is_ccw


def test_rejects_non_positive_width():
    with pytest.raises(ValueError):
        scale_to_mm(MultiPolygon([box(0, 0, 1, 1)]), 10, 10, 0)
