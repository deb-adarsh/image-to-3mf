"""Stage 3: turn traced pixel outlines into final 2D layers in millimetres.

Minimum feature width, backing plate and text arrive with milestone 4.
"""

from __future__ import annotations

import shapely
from shapely.geometry import MultiPolygon

from image_to_3mf.geometry import absorb_small_pieces, as_multipolygon

# Footprint of a 0.4 mm nozzle: anything smaller cannot print as its own colour.
MIN_SPECK_AREA = 0.16  # mm^2


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
    layers: list[MultiPolygon], min_area: float = MIN_SPECK_AREA
) -> list[MultiPolygon]:
    """Fold pieces too small to print into the neighbouring colour.

    Layers must not overlap; the result still covers the same area, except
    for specks that touch no other colour, which are dropped.
    """
    return absorb_small_pieces(layers, min_area)
