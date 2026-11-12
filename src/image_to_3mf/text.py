"""Render a line of text into polygons, in millimetres.

The text is drawn large with Pillow's FreeType renderer and traced like any
other artwork, so no font-outline library is needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPolygon

from image_to_3mf.compose import scale_to_mm
from image_to_3mf.trace import trace_mask

PX_PER_MM = 20  # tracing resolution: 0.05 mm per pixel


def render_text(text: str, size: float, font: str | Path | None = None) -> MultiPolygon:
    """Polygons for ``text`` set in ``font`` at ``size`` mm (the font's em size).

    The result's bottom-left is near (0, 0), y up. ``font`` is a path to a
    TrueType/OpenType file, or ``None`` for Pillow's built-in font.
    """
    if not text.strip():
        return MultiPolygon()
    if size <= 0:
        raise ValueError(f"text size must be positive, got {size}")

    px = max(8, round(size * PX_PER_MM))
    try:
        face = ImageFont.truetype(str(font), px) if font else ImageFont.load_default(px)
    except OSError as exc:
        raise ValueError(f"cannot load font {font}: {exc}") from exc

    left, top, right, bottom = face.getbbox(text)
    pad = px // 4
    width, height = right - left + 2 * pad, bottom - top + 2 * pad
    image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(image).text((pad - left, pad - top), text, font=face, fill=255)

    mask = np.asarray(image) >= 128
    return scale_to_mm(trace_mask(mask, smooth=1.0), width, height, width / PX_PER_MM)
