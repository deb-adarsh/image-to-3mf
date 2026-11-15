from __future__ import annotations

import math

import pytest
import shapely
import shapely.affinity
from shapely.geometry import MultiPolygon, Polygon, box

from image_to_3mf.compose import (
    add_to_layer,
    backing_plate,
    place_below,
    remove_specks,
    scale_to_mm,
    thicken,
)


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


def test_remove_specks_folds_tiny_piece_into_neighbour():
    big = MultiPolygon([box(0, 0, 10, 10)])
    tiny = MultiPolygon([box(10, 0, 10.2, 0.2)])  # 0.04 mm2, far below the minimum feature
    big2, tiny2 = remove_specks([big, tiny])
    assert tiny2.is_empty
    assert big2.area == pytest.approx(100.04)


# --- thin strokes --------------------------------------------------------------


def _min_width_ok(geom, min_feature):
    """True if an opening at just under ``min_feature`` keeps nearly everything."""
    r = min_feature / 2 * 0.98
    opened = geom.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    return opened.area >= 0.97 * geom.area


def test_thin_line_is_widened_to_the_minimum_feature():
    line = MultiPolygon([box(0, 0, 20, 0.3)])
    [result] = thicken([line], 0.8)
    assert not _min_width_ok(line, 0.8)
    assert _min_width_ok(result, 0.8)
    assert result.area == pytest.approx(20 * 0.8, rel=0.06)


def test_wide_shapes_and_sharp_corners_are_untouched():
    star = Polygon([(10 + (8 if i % 2 == 0 else 3.2) * math.sin(i * math.pi / 5),
                     10 + (8 if i % 2 == 0 else 3.2) * math.cos(i * math.pi / 5)) for i in range(10)])
    shapes = MultiPolygon([box(0, 0, 10, 5), shapely.affinity.translate(star, 20, 0)])
    [result] = thicken([shapes], 0.8)
    assert result.area == pytest.approx(shapes.area)


def test_thickening_takes_space_from_other_layers():
    under = MultiPolygon([box(0, -5, 20, 0), box(0, 0.3, 20, 5)])
    line = MultiPolygon([box(0, 0, 20, 0.3)])
    under2, line2 = thicken([under, line], 0.8)
    assert under2.intersection(line2).area == pytest.approx(0, abs=1e-6)
    # No gaps opened up: everything covered before is still covered.
    lost = shapely.unary_union([under, line]).difference(shapely.unary_union([under2, line2]))
    assert lost.area == pytest.approx(0, abs=1e-6)
    assert _min_width_ok(line2, 0.8)


def test_zero_min_feature_changes_nothing():
    line = MultiPolygon([box(0, 0, 20, 0.3)])
    assert thicken([line], 0)[0].equals(line)


# --- backing plate -----------------------------------------------------------


def test_plate_fills_holes():
    ring = MultiPolygon([box(0, 0, 10, 10).difference(box(3, 3, 7, 7))])
    plate = backing_plate([ring])
    assert plate.area == pytest.approx(100)
    assert not plate.geoms[0].interiors


def test_plate_margin():
    plate = backing_plate([MultiPolygon([box(0, 0, 10, 10)])], margin=2)
    assert plate.bounds == pytest.approx((-2, -2, 12, 12))


def test_plate_holds_separate_pieces_together():
    pieces = [MultiPolygon([box(0, 0, 5, 5)]), MultiPolygon([box(20, 0, 25, 5)])]
    plate = backing_plate(pieces)
    assert len(plate.geoms) == 1
    assert plate.area == pytest.approx(125)  # the convex hull


def test_negative_margin_raises():
    with pytest.raises(ValueError):
        backing_plate([MultiPolygon([box(0, 0, 1, 1)])], margin=-1)


# --- text placement ----------------------------------------------------------


def test_place_below_centres_text_under_artwork():
    art = [MultiPolygon([box(0, 10, 40, 30)])]
    text = MultiPolygon([box(100, 100, 110, 104)])
    placed = place_below(text, art, gap=2)
    assert placed.bounds == pytest.approx((15, 4, 25, 8))


def test_add_to_layer_moves_area_between_layers():
    a, b = MultiPolygon([box(0, 0, 10, 10)]), MultiPolygon([box(10, 0, 20, 10)])
    a2, b2 = add_to_layer([a, b], 1, MultiPolygon([box(5, 0, 15, 10)]))
    assert a2.area == pytest.approx(50)
    assert b2.area == pytest.approx(150)


def test_stand_alone_dot_is_kept_and_widened():
    """Regression: the dot of a small "i" was dropped as a speck."""
    stem = MultiPolygon([box(0, 0, 0.9, 5)])
    dot = MultiPolygon([box(0.1, 6, 0.7, 6.6)])  # 0.36 mm2: below 0.8 x 0.8, but on its own
    [kept] = remove_specks([MultiPolygon(list(stem.geoms) + list(dot.geoms))], 0.8)
    assert len(kept.geoms) == 2
    [widened] = thicken([kept], 0.8)
    assert min(p.area for p in widened.geoms) > 0.64


def test_tiny_stand_alone_speck_is_dropped():
    [result] = remove_specks([MultiPolygon([box(0, 0, 5, 5), box(10, 10, 10.2, 10.2)])], 0.8)
    assert len(result.geoms) == 1
