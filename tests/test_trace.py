from __future__ import annotations

import numpy as np
import pytest
import shapely

from image_to_3mf.trace import trace_layers, trace_mask


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


# --- several colour layers ---------------------------------------------------


def _check_tiling(layers, total_area):
    for i in range(len(layers)):
        for j in range(i + 1, len(layers)):
            assert layers[i].intersection(layers[j]).area == pytest.approx(0, abs=1e-6)
    assert shapely.unary_union(layers).area == pytest.approx(total_area, rel=0.01)


def test_adjacent_colours_tile_without_gaps():
    left = np.zeros((40, 70), dtype=bool)
    left[5:35, 5:35] = True
    right = np.zeros_like(left)
    right[5:35, 35:65] = True

    layers = trace_layers([left, right])

    assert [len(g.geoms) for g in layers] == [1, 1]
    assert [g.area for g in layers] == pytest.approx([900, 900], rel=0.02)
    _check_tiling(layers, 1800)


def test_inner_colour_becomes_a_hole_in_the_outer(donut_mask):
    inner = np.zeros_like(donut_mask)
    inner[20:40, 20:40] = True

    outer_layer, inner_layer = trace_layers([donut_mask, inner])

    assert len(outer_layer.geoms[0].interiors) == 1
    assert inner_layer.area == pytest.approx(400, rel=0.02)
    _check_tiling([outer_layer, inner_layer], 1600)


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 2, 0)])
def test_layers_never_overlap_in_any_order(order):
    yy, xx = np.mgrid[0:80, 0:80]
    disc = (xx - 40) ** 2 + (yy - 40) ** 2 <= 35**2
    top = disc & (yy < 30)
    left = disc & (yy >= 30) & (xx < 40)
    right = disc & (yy >= 30) & (xx >= 40)
    masks = [top, left, right]

    layers = trace_layers([masks[i] for i in order], smooth=1.0)

    assert all(len(g.geoms) == 1 for g in layers)
    _check_tiling(layers, trace_mask(disc, smooth=1.0).area)


def test_no_layers():
    assert trace_layers([]) == []
