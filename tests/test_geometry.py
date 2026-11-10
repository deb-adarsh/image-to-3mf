from __future__ import annotations

import pytest
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, box

from image_to_3mf.geometry import absorb_small_pieces, as_multipolygon


def test_small_piece_joins_the_layer_it_borders_most():
    a = MultiPolygon([box(0, 0, 10, 10)])
    b = MultiPolygon([box(10, 0, 20, 10)])
    # A 1 x 1 piece of layer c tucked into a notch: 3 sides touch b, 1 side touches a.
    b = MultiPolygon([box(10, 0, 20, 10).difference(box(10, 4, 11, 5))])
    c = MultiPolygon([box(10, 4, 11, 5)])

    a2, b2, c2 = absorb_small_pieces([a, b, c], min_area=2)

    assert c2.is_empty
    assert b2.area == pytest.approx(100)
    assert len(b2.geoms) == 1
    assert a2.equals(a)


def test_isolated_small_piece_is_dropped():
    a = MultiPolygon([box(0, 0, 10, 10)])
    speck = MultiPolygon([box(50, 50, 51, 51)])
    a2, speck2 = absorb_small_pieces([a, speck], min_area=2)
    assert speck2.is_empty
    assert a2.equals(a)


def test_large_pieces_are_untouched():
    layers = [MultiPolygon([box(0, 0, 10, 10)]), MultiPolygon([box(10, 0, 20, 10)])]
    assert absorb_small_pieces(layers, min_area=2) is layers


def test_as_multipolygon_keeps_only_polygons():
    mixed = GeometryCollection([box(0, 0, 1, 1), LineString([(0, 0), (1, 1)]), Point(3, 3)])
    result = as_multipolygon(mixed)
    assert isinstance(result, MultiPolygon)
    assert len(result.geoms) == 1
    assert as_multipolygon(box(0, 0, 1, 1)).area == 1
    assert as_multipolygon(Point(0, 0)).is_empty
