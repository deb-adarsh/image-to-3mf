"""Stage 3: turn traced pixel outlines into final 2D layers in millimetres.

Scale to size, fold away specks, thicken strokes too thin to print, add an
optional text line, and build the backing plate's footprint.
"""

from __future__ import annotations

import shapely
import shapely.affinity
from shapely.geometry import MultiPolygon, Polygon

from image_to_3mf.geometry import absorb_small_pieces, as_multipolygon

MIN_FEATURE = 0.8  # mm, about two 0.4 mm nozzle widths

# Geometry thinner than this is rounding noise, not a feature.
_NOISE = 1e-4  # mm
# Thin pieces narrower than this share of the minimum feature are left alone.
_SLIVER = 0.1


def scale_to_mm(
    geom: MultiPolygon, image_width_px: int, image_height_px: int, width_mm: float
) -> MultiPolygon:
    """Map pixel coordinates (y down) to millimetres (y up, origin bottom-left).

    The whole image, not just the artwork, is scaled to ``width_mm`` so the
    output keeps the image's framing.
    """
    if width_mm <= 0:
        raise ValueError(f"width_mm must be positive, got {width_mm}")
    scale = width_mm / image_width_px
    flipped = shapely.transform(
        geom, lambda xy: (xy * [1.0, -1.0] + [0.0, image_height_px]) * scale
    )
    # Flipping y reverses ring orientation; normalise it back.
    return as_multipolygon(shapely.orient_polygons(flipped))


def remove_specks(
    layers: list[MultiPolygon], min_feature: float = MIN_FEATURE
) -> list[MultiPolygon]:
    """Fold specks smaller than ``min_feature`` squared into the neighbouring colour.

    A speck between colours is noise (an anti-aliasing or JPEG artifact). A
    small piece standing on its own, such as the dot of an "i", is a detail:
    it is kept if at least a quarter of that area, for ``thicken`` to widen.
    Layers must not overlap; the result still covers the same area, except
    for the tiniest stand-alone specks, which are dropped.
    """
    return absorb_small_pieces(layers, min_feature**2, keep_isolated=(min_feature / 2) ** 2)


def thicken(layers: list[MultiPolygon], min_feature: float = MIN_FEATURE) -> list[MultiPolygon]:
    """Widen strokes narrower than ``min_feature`` so they print.

    The thin parts of a layer are what a morphological opening (shrink by
    half the minimum feature, then grow back) removes. Each thin part is grown
    by however much its estimated width falls short, and takes that area
    from the other layers, so layers still never overlap. Later layers
    (smaller colours, usually the details) are thickened first.
    """
    if min_feature <= 0:
        return list(layers)
    r = min_feature / 2
    layers = list(layers)
    for i in reversed(range(len(layers))):
        layer = layers[i]
        if layer.is_empty:
            continue
        opened = layer.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
        thin = as_multipolygon(layer.difference(opened.buffer(_NOISE)))

        growth = []
        for piece in thin.geoms:
            # Area / half the perimeter approximates the width of a strip.
            width = 2 * piece.area / piece.length
            if width < _SLIVER * min_feature:
                # A hairline where the opening did not quite restore a curved
                # edge: rounding noise, not a stroke.
                continue
            shortfall = r - width / 2
            if shortfall > _NOISE:
                growth.append(piece.buffer(shortfall))
        if not growth:
            continue

        grown = shapely.unary_union(growth)
        layers[i] = as_multipolygon(shapely.unary_union([layer, grown]))
        for j in range(len(layers)):
            if j != i:
                layers[j] = as_multipolygon(layers[j].difference(grown))
    return layers


def backing_plate(layers: list[MultiPolygon], margin: float = 0.0) -> MultiPolygon:
    """Footprint of a plate under the artwork: its outline grown by ``margin``.

    Holes in the artwork (letter counters, background-coloured details) are
    filled, so the plate shows through them. The plate must hold every piece
    together: if the outline falls apart into islands (separate letters, say),
    the plate becomes the convex hull of the artwork instead.
    """
    if margin < 0:
        raise ValueError(f"margin must not be negative, got {margin}")
    union = shapely.unary_union([g for g in layers if not g.is_empty])
    plate = _fill_holes(union.buffer(margin) if margin > 0 else union)
    if len(plate.geoms) > 1:
        hull = union.convex_hull
        plate = as_multipolygon(hull.buffer(margin) if margin > 0 else hull)
    return plate


def _fill_holes(geom) -> MultiPolygon:
    return as_multipolygon(
        shapely.unary_union([Polygon(p.exterior) for p in as_multipolygon(geom).geoms])
    )


def place_below(text: MultiPolygon, artwork: list[MultiPolygon], gap: float) -> MultiPolygon:
    """Centre ``text`` horizontally under the artwork, ``gap`` mm below it."""
    if text.is_empty:
        return text
    ax0, ay0, ax1, _ = shapely.unary_union([g for g in artwork if not g.is_empty]).bounds
    tx0, _, tx1, ty1 = text.bounds
    dx = (ax0 + ax1) / 2 - (tx0 + tx1) / 2
    dy = ay0 - gap - ty1
    return as_multipolygon(shapely.affinity.translate(text, dx, dy))


def add_to_layer(layers: list[MultiPolygon], index: int, geom: MultiPolygon) -> list[MultiPolygon]:
    """Put ``geom`` in layer ``index``, taking that area from the other layers."""
    result = []
    for i, layer in enumerate(layers):
        if i == index:
            result.append(as_multipolygon(shapely.unary_union([layer, geom])))
        else:
            result.append(as_multipolygon(layer.difference(geom)))
    return result
