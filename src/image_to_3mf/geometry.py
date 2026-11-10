"""2D geometry helpers shared by the trace and compose stages."""

from __future__ import annotations

import shapely
from shapely.geometry import MultiPolygon, Polygon


def as_multipolygon(geom) -> MultiPolygon:
    """Keep only the polygonal parts of ``geom``, as a MultiPolygon."""
    if geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    parts = []
    for g in getattr(geom, "geoms", []):
        parts.extend(as_multipolygon(g).geoms)
    return MultiPolygon(parts)


def absorb_small_pieces(layers: list[MultiPolygon], min_area: float) -> list[MultiPolygon]:
    """Merge every polygon smaller than ``min_area`` into the layer it borders most.

    Layers are expected not to overlap. A small piece is given to the layer
    that shares the longest border with it, so the layers keep covering the
    same area without gaps. A piece that borders no other layer, or only
    touches it at a point, is dropped: afterwards no layer has a polygon
    smaller than ``min_area``.
    """
    kept = [[p for p in layer.geoms if p.area >= min_area] for layer in layers]
    small = [(i, p) for i, layer in enumerate(layers) for p in layer.geoms if p.area < min_area]
    if not small:
        return layers

    kept_geoms = [MultiPolygon(parts) for parts in kept]
    additions: list[list[Polygon]] = [[] for _ in layers]
    for i, piece in small:
        # Thicken the piece's outline a hair to measure shared border length.
        rim_width = _rim_width(piece)
        rim = piece.exterior.buffer(rim_width)
        touch = [
            rim.intersection(g).area if j != i and not g.is_empty else 0.0
            for j, g in enumerate(kept_geoms)
        ]
        best = max(range(len(touch)), key=touch.__getitem__)
        if touch[best] > 0:
            # Borders that are a rounding error apart must coincide to fuse.
            additions[best].append(shapely.snap(piece, kept_geoms[best], rim_width))

    result = []
    for parts, extra in zip(kept, additions):
        merged = as_multipolygon(shapely.unary_union(parts + extra)) if extra else MultiPolygon(parts)
        result.append(MultiPolygon([p for p in merged.geoms if p.area >= min_area]))
    return result


def _rim_width(piece: Polygon) -> float:
    minx, miny, maxx, maxy = piece.bounds
    return max(maxx - minx, maxy - miny, 1e-9) * 1e-3 + 1e-9
