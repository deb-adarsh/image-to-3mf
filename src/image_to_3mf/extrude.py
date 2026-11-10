"""Stage 4: extrude 2D layers into watertight solids, one per colour."""

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
    _check(solid)
    return solid


def extrude_layers(layers: list[MultiPolygon], depths: list[float]) -> list[Manifold]:
    """Extrude each colour layer from the bed up to its own depth.

    Later layers sit on top of earlier ones: wherever bodies would overlap,
    the later (upper) body is subtracted from the earlier (lower) one, so no
    two colour bodies share any volume.
    """
    if len(layers) != len(depths):
        raise ValueError(f"got {len(layers)} layers but {len(depths)} depths")

    bodies = [extrude(layer, depth) for layer, depth in zip(layers, depths)]
    above = Manifold()
    for i in reversed(range(len(bodies))):
        body = bodies[i] - above
        _check(body)
        above = above + body
        bodies[i] = body
    return bodies


def to_mesh(solid: Manifold) -> Mesh:
    """Export a manifold as a plain vertex/triangle mesh."""
    mesh = solid.to_mesh()
    vertices = np.asarray(mesh.vert_properties, dtype=float)[:, :3]
    triangles = np.asarray(mesh.tri_verts, dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles)


def _check(solid: Manifold) -> None:
    if solid.status() != Error.NoError:
        raise RuntimeError(f"geometry operation failed: {solid.status()}")
