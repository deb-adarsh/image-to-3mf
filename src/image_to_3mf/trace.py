"""Stage 2: trace a binary mask into smooth vector outlines with holes."""

from __future__ import annotations

import math

import numpy as np
import potrace
import shapely
from shapely.geometry import MultiPolygon, Polygon

# Potrace's alphamax: 0 keeps every corner sharp, 1.334 is the smoothest.
MAX_SMOOTH = 1.334


def trace_mask(
    mask: np.ndarray,
    smooth: float = 1.0,
    turdsize: int = 2,
    curve_tolerance: float = 0.25,
) -> MultiPolygon:
    """Trace the True pixels of ``mask`` into polygons.

    Coordinates are in pixels with the image's own orientation: x to the
    right, y down, (0, 0) at the top-left corner of the top-left pixel.

    :param smooth: Potrace corner threshold (alphamax), 0 to 1.334.
    :param turdsize: Drop specks of up to this many pixels.
    :param curve_tolerance: Maximum distance in pixels between a Bezier curve
        and the straight segments that approximate it.
    """
    if mask.ndim != 2:
        raise ValueError(f"expected a 2D mask, got shape {mask.shape}")
    if not 0 <= smooth <= MAX_SMOOTH:
        raise ValueError(f"smooth must be between 0 and {MAX_SMOOTH}, got {smooth}")

    # A one-pixel empty border keeps shapes that touch the image edge closed.
    padded = np.pad(mask.astype(bool), 1, mode="constant", constant_values=False)
    # potracer treats False as ink, so hand it the inverted mask.
    path = potrace.Bitmap(~padded).trace(
        turdsize=turdsize, alphamax=smooth, opticurve=True, opttolerance=0.2
    )
    rings = [_flatten_curve(curve, curve_tolerance) - 1.0 for curve in path]
    rings = [r for r in rings if len(r) >= 3]
    return _rings_to_polygons(rings)


def _flatten_curve(curve, tolerance: float) -> np.ndarray:
    """Turn a closed potrace curve into a ring of points (not repeated at the end)."""
    points = []
    current = np.array([curve.start_point.x, curve.start_point.y])
    for segment in curve.segments:
        end = np.array([segment.end_point.x, segment.end_point.y])
        if segment.is_corner:
            points.append([segment.c.x, segment.c.y])
            points.append(end)
        else:
            c1 = np.array([segment.c1.x, segment.c1.y])
            c2 = np.array([segment.c2.x, segment.c2.y])
            points.extend(_sample_bezier(current, c1, c2, end, tolerance))
        current = end
    return np.asarray(points, dtype=float)


def _sample_bezier(p0, p1, p2, p3, tolerance: float) -> np.ndarray:
    """Points along a cubic Bezier, excluding p0 and including p3."""
    # Standard flatness bound for a uniformly subdivided cubic.
    dd = max(np.linalg.norm(p0 - 2 * p1 + p2), np.linalg.norm(p1 - 2 * p2 + p3))
    steps = max(2, min(64, math.ceil(math.sqrt(0.75 * dd / tolerance)) if dd > 0 else 2))
    t = np.linspace(0.0, 1.0, steps + 1)[1:, None]
    mt = 1.0 - t
    return mt**3 * p0 + 3 * mt**2 * t * p1 + 3 * mt * t**2 * p2 + t**3 * p3


def _rings_to_polygons(rings: list[np.ndarray]) -> MultiPolygon:
    """Nest closed, non-crossing rings into polygons with holes.

    A ring inside an even number of other rings is an outline; a ring inside
    an odd number is a hole in its innermost container.
    """
    if not rings:
        return MultiPolygon()

    areas = [Polygon(r).buffer(0) for r in rings]
    tree = shapely.STRtree(areas)
    parent: list[int | None] = []
    depth: list[int] = []
    for i, poly in enumerate(areas):
        containers = [int(j) for j in tree.query(poly, predicate="within") if j != i]
        depth.append(len(containers))
        parent.append(min(containers, key=lambda j: areas[j].area) if containers else None)

    polygons = []
    for i, ring in enumerate(rings):
        if depth[i] % 2:
            continue
        holes = [rings[k] for k in range(len(rings)) if parent[k] == i and depth[k] % 2]
        polygons.append(Polygon(ring, holes).buffer(0))

    merged = shapely.unary_union(polygons)
    return as_multipolygon(merged)


def as_multipolygon(geom) -> MultiPolygon:
    if geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    return MultiPolygon([g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)])
