"""Stage 4: extrude 2D layers into watertight solids."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from manifold3d import CrossSection, Error, FillRule, Manifold
from shapely.geometry import MultiPolygon


@dataclass(frozen=True)
class Mesh:
    vertices: np.ndarray  # float (N, 3), millimetres
    triangles: np.ndarray  # int (M, 3), counter-clockwise seen from outside


def extrude(geom: MultiPolygon, height: float, z0: float = 0.0) -> Manifold:
    """Extrude polygons straight up from ``z0`` by ``height`` millimetres."""
    if height <= 0:
        raise ValueError(f"height must be positive, got {height}")
    if geom.is_empty:
        raise ValueError("nothing to extrude: geometry is empty")

    contours = []
    for polygon in geom.geoms:
        contours.append(np.asarray(polygon.exterior.coords)[:-1, :2])
        contours.extend(np.asarray(ring.coords)[:-1, :2] for ring in polygon.interiors)

    section = CrossSection(contours, FillRule.EvenOdd)
    solid = Manifold.extrude(section, height).translate((0.0, 0.0, z0))
    if solid.status() != Error.NoError:
        raise RuntimeError(f"extrusion failed: {solid.status()}")
    return solid


def to_mesh(solid: Manifold) -> Mesh:
    """Export a manifold as a plain vertex/triangle mesh."""
    mesh = solid.to_mesh()
    vertices = np.asarray(mesh.vert_properties, dtype=float)[:, :3]
    triangles = np.asarray(mesh.tri_verts, dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles)
