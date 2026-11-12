"""Stage 4: extrude 2D layers into watertight solids, one per colour."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from manifold3d import CrossSection, Error, FillRule, Manifold, OpType
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


def extrude_layers(
    layers: list[MultiPolygon], depths: list[float], bottoms: list[float] | None = None
) -> list[Manifold]:
    """Extrude each layer from its bottom (default: the bed) up by its depth.

    Later layers win shared space: wherever bodies would overlap, the later
    body is subtracted from every earlier one, so no two bodies share any
    volume. Put a backing plate first to have colours sit on it or be inlaid
    into it.
    """
    bottoms = [0.0] * len(layers) if bottoms is None else bottoms
    if not len(layers) == len(depths) == len(bottoms):
        raise ValueError(
            f"got {len(layers)} layers, {len(depths)} depths and {len(bottoms)} bottoms"
        )

    bodies = [extrude(g, d, z0) for g, d, z0 in zip(layers, depths, bottoms)]
    above = Manifold()
    for i in reversed(range(len(bodies))):
        body = bodies[i] - above
        _check(body)
        above = above + body
        bodies[i] = body
    return bodies


def union(bodies: list[Manifold]) -> Manifold:
    """All bodies merged into one solid."""
    solid = Manifold.batch_boolean(bodies, OpType.Add) if bodies else Manifold()
    _check(solid)
    return solid


def to_mesh(solid: Manifold) -> Mesh:
    """Export a manifold as a plain vertex/triangle mesh."""
    mesh = solid.to_mesh()
    vertices = np.asarray(mesh.vert_properties, dtype=float)[:, :3]
    triangles = np.asarray(mesh.tri_verts, dtype=np.int64)
    return Mesh(vertices=vertices, triangles=triangles)


def _check(solid: Manifold) -> None:
    if solid.status() != Error.NoError:
        raise RuntimeError(f"geometry operation failed: {solid.status()}")
