from __future__ import annotations

import numpy as np
import pytest
import trimesh
from shapely.geometry import MultiPolygon, Polygon, box

from image_to_3mf.extrude import extrude, to_mesh


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
