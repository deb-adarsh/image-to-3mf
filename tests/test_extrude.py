from __future__ import annotations

import numpy as np
import pytest
import trimesh
from shapely.geometry import MultiPolygon, Polygon, box

from image_to_3mf.extrude import extrude, extrude_layers, to_mesh, union


def _trimesh(solid) -> trimesh.Trimesh:
    mesh = to_mesh(solid)
    return trimesh.Trimesh(mesh.vertices, mesh.triangles, process=False)


def test_box_extrusion_is_watertight():
    solid = extrude(MultiPolygon([box(0, 0, 10, 20)]), height=3)
    assert solid.volume() == pytest.approx(600)
    assert solid.genus() == 0
    mesh = _trimesh(solid)
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(600)  # positive: normals face outwards


def test_hole_makes_genus_one():
    ring = Polygon(box(0, 0, 10, 10).exterior, [box(3, 3, 7, 7).exterior.coords])
    solid = extrude(MultiPolygon([ring]), height=2)
    assert solid.genus() == 1
    assert solid.volume() == pytest.approx((100 - 16) * 2)
    assert _trimesh(solid).is_watertight


def test_separate_parts_stay_separate():
    geom = MultiPolygon([box(0, 0, 1, 1), box(5, 5, 6, 6)])
    assert len(extrude(geom, height=1).decompose()) == 2


def test_z_offset():
    solid = extrude(MultiPolygon([box(0, 0, 1, 1)]), height=2, z0=1.5)
    assert np.allclose(solid.bounding_box(), (0, 0, 1.5, 1, 1, 3.5))


def test_empty_geometry_raises():
    with pytest.raises(ValueError):
        extrude(MultiPolygon(), height=1)


def test_non_positive_height_raises():
    with pytest.raises(ValueError):
        extrude(MultiPolygon([box(0, 0, 1, 1)]), height=0)


# --- several colour layers ---------------------------------------------------


def test_layers_with_different_depths_do_not_overlap():
    layers = [MultiPolygon([box(0, 0, 10, 10)]), MultiPolygon([box(10, 0, 20, 10)])]
    low, high = extrude_layers(layers, [1.0, 3.0])
    assert low.volume() == pytest.approx(100)
    assert high.volume() == pytest.approx(300)
    assert (low ^ high).volume() == pytest.approx(0, abs=1e-9)
    assert _trimesh(low).is_watertight and _trimesh(high).is_watertight


def test_upper_layer_is_cut_out_of_lower_layer():
    # Overlapping footprints: the later (upper) layer wins the shared volume.
    lower = MultiPolygon([box(0, 0, 10, 10)])
    upper = MultiPolygon([box(5, 0, 15, 10)])
    low, high = extrude_layers([lower, upper], [2.0, 2.0])
    assert high.volume() == pytest.approx(200)
    assert low.volume() == pytest.approx(100)
    assert (low ^ high).volume() == pytest.approx(0, abs=1e-9)


def test_depth_count_must_match():
    with pytest.raises(ValueError):
        extrude_layers([MultiPolygon([box(0, 0, 1, 1)])], [1.0, 2.0])


def test_bottoms_stack_layers():
    plate = MultiPolygon([box(0, 0, 10, 10)])
    top = MultiPolygon([box(2, 2, 8, 8)])
    p, t = extrude_layers([plate, top], [1.5, 1.0], [0.0, 1.5])
    assert np.allclose(t.bounding_box(), (2, 2, 1.5, 8, 8, 2.5))
    assert p.volume() == pytest.approx(150)  # nothing to cut: the top sits on the plate


def test_bottoms_inlay_cuts_into_the_plate():
    plate = MultiPolygon([box(0, 0, 10, 10)])
    inlay = MultiPolygon([box(2, 2, 8, 8)])
    p, i = extrude_layers([plate, inlay], [2.0, 0.6], [0.0, 1.4])
    assert p.volume() == pytest.approx(200 - 36 * 0.6)
    assert (p ^ i).volume() == pytest.approx(0, abs=1e-9)


def test_union_merges_bodies():
    a, b = extrude_layers([MultiPolygon([box(0, 0, 1, 1)]), MultiPolygon([box(1, 0, 2, 1)])], [1, 1])
    merged = union([a, b])
    assert merged.volume() == pytest.approx(2)
    assert len(merged.decompose()) == 1
