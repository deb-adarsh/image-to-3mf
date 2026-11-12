"""Stage 1: load an image and reduce it to one binary mask per colour.

The palette is found from "flat" pixels only (pixels whose 3x3 neighbourhood
is one colour), so anti-aliased edges cannot become colours of their own. Edge
pixels that are a blend of the colours around them are then given one of those
colours, never an unrelated colour that happens to be close (a red/green edge
looks brown, but must not become the brown of a nearby stem).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

MAX_COLORS = 6  # artwork colours, not counting the background

_ALPHA_CUTOFF = 128  # alpha below this is transparent background
_FLAT_RANGE = 20  # max RGB range in a 3x3 neighbourhood for a pixel to count as flat
_MERGE_DELTA_E = 15.0  # auto-detected colours closer than this (CIE76) are one colour
_MIN_SHARE = 0.002  # an auto-detected colour must cover this share of flat pixels
_BLEND_TOLERANCE = 24.0  # RGB distance within which an edge pixel is a blend of neighbours
_OVERSHOOT = 0.25  # resampling rings past a blend's end colour by up to this share
_NEIGHBOURHOOD = 4  # radius in px to look for the colours around an edge pixel
_MAX_SAMPLES = 200_000  # pixels used to build the palette


@dataclass(frozen=True)
class ColorMask:
    """One colour of the artwork: its display colour and where it is."""

    color: tuple[int, int, int]  # sRGB, 0-255
    mask: np.ndarray  # bool, shape (H, W), True where this colour is

    @property
    def hex(self) -> str:
        return "#{:02X}{:02X}{:02X}".format(*self.color)


class Palette(list):
    """The artwork's colours (a list of ColorMask), plus the removed background."""

    def __init__(self, layers=(), background: tuple[int, int, int] | None = None):
        super().__init__(layers)
        self.background = background  # sRGB, or None for a transparent background


def load_image(path: str | Path) -> np.ndarray:
    """Load any Pillow-readable image as an RGBA uint8 array of shape (H, W, 4)."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()


def quantize(rgba: np.ndarray, n_colors: int | None = None) -> Palette:
    """Reduce artwork to its colours, with the background removed.

    The background is the transparent area if transparency dominates the image
    border, otherwise the colour that dominates the border.

    :param n_colors: Number of artwork colours (background not counted).
        ``None`` detects it, up to ``MAX_COLORS``.
    :return: One mask per colour, largest area first, and the background colour
        (``None`` if transparent). Masks never overlap.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"expected an RGBA array of shape (H, W, 4), got {rgba.shape}")
    if n_colors is not None and not 1 <= n_colors <= MAX_COLORS:
        raise ValueError(f"n_colors must be between 1 and {MAX_COLORS}, got {n_colors}")

    opaque = rgba[..., 3] >= _ALPHA_CUTOFF
    if not opaque.any():
        raise ValueError("image is fully transparent")

    rgb = rgba[..., :3]
    flat = _flat_pixels(rgba) & opaque
    transparent_background = _border(~opaque).mean() >= 0.5

    sample = rgb[flat] if flat.sum() >= 0.1 * opaque.sum() else rgb[opaque]
    flat_palette = _palette(sample, None)
    # Thin strokes have no flat pixels. The edge pixels that no blend of the
    # flat colours explains belong to strokes of colours not found yet.
    edges = rgb[opaque & ~flat].astype(np.float32)
    residual, _ = _best_blend(edges, flat_palette)
    strokes = edges[residual > _BLEND_TOLERANCE]

    if n_colors is None:
        min_count = max(3, int(_MIN_SHARE * len(sample)))
        palette = np.vstack([flat_palette, *_stroke_colours(strokes, flat_palette, min_count)])
    else:
        k = n_colors + (0 if transparent_background else 1)
        palette = _palette(np.concatenate([sample, strokes.astype(sample.dtype)]), k)

    labels = _assign(rgb, opaque, flat, palette)
    background = None
    if not transparent_background:
        border = _border(labels)
        bg_label = np.bincount(border[border >= 0]).argmax()
        background = _colour_of(rgb, labels == bg_label, flat, palette[bg_label])
        labels[labels == bg_label] = -1

    layers = []
    for index, centre in enumerate(palette):
        mask = labels == index
        if mask.any():
            layers.append(ColorMask(color=_colour_of(rgb, mask, flat, centre), mask=mask))

    if not layers:
        raise ValueError("no foreground found in image")
    layers.sort(key=lambda layer: int(layer.mask.sum()), reverse=True)
    return Palette(layers, background)


def _colour_of(rgb, mask, flat, fallback) -> tuple[int, int, int]:
    """Median colour of the flat pixels under ``mask``."""
    core = rgb[mask & flat]
    color = np.median(core, axis=0) if len(core) else fallback
    return tuple(int(round(c)) for c in color)


def _stroke_colours(px: np.ndarray, known: np.ndarray, min_count: int) -> list[np.ndarray]:
    """Colours of thin strokes, found from pixels that no known colour explains.

    A stroke pixel is the stroke's colour blended with the colour around it,
    so its lighter (or darker) shades are blends, not colours of their own.
    Each round takes the most saturated half of the unexplained pixels (the
    stroke centres) as a new colour, then drops every pixel that is now a
    blend of known colours, until too few pixels are left.
    """
    found: list[np.ndarray] = []
    palette = np.asarray(known, dtype=np.float32)
    for _ in range(4 * MAX_COLORS):
        if len(px) < min_count or len(palette) > MAX_COLORS:
            break
        distance = np.min([np.linalg.norm(px - c, axis=1) for c in palette], axis=0)
        colour = np.median(px[distance >= np.median(distance)], axis=0)
        off_blend, _ = _best_blend(colour[None, :], palette)
        if off_blend[0] > 2 * _BLEND_TOLERANCE:
            found.append(colour)
            palette = np.vstack([palette, colour])
            tolerance = _BLEND_TOLERANCE
        else:
            # Noisy blends of known colours (JPEG edges): no new colour.
            tolerance = 2 * _BLEND_TOLERANCE
        residual, _ = _best_blend(px, palette)
        px = px[residual > tolerance]
    return found


def _border(a: np.ndarray) -> np.ndarray:
    return np.concatenate([a[0, :], a[-1, :], a[1:-1, 0], a[1:-1, -1]])


def _flat_pixels(rgba: np.ndarray) -> np.ndarray:
    """True where the 3x3 neighbourhood is fully opaque and a single colour."""
    kernel = np.ones((3, 3), np.uint8)
    rgb = np.ascontiguousarray(rgba[..., :3])
    spread = (cv2.dilate(rgb, kernel) - cv2.erode(rgb, kernel)).max(axis=2)
    solid = cv2.erode(rgba[..., 3], kernel) == 255
    return (spread <= _FLAT_RANGE) & solid


def _to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (0-255, any shape ending in 3) to CIELAB (L 0-100)."""
    flat = np.asarray(rgb, dtype=np.float32).reshape(-1, 1, 3) / 255.0
    return cv2.cvtColor(flat, cv2.COLOR_RGB2Lab).reshape(np.shape(rgb))


def _to_rgb(lab: np.ndarray) -> np.ndarray:
    flat = np.asarray(lab, dtype=np.float32).reshape(-1, 1, 3)
    return (cv2.cvtColor(flat, cv2.COLOR_Lab2RGB).reshape(np.shape(lab)) * 255.0).clip(0, 255)


def _palette(sample: np.ndarray, k: int | None) -> np.ndarray:
    """Palette colours (sRGB float, shape (K, 3)), including any opaque background."""
    if len(sample) > _MAX_SAMPLES:
        rng = np.random.default_rng(0)
        sample = sample[rng.choice(len(sample), _MAX_SAMPLES, replace=False)]
    lab = _to_lab(sample)

    if k is None:
        centres = _detect_colours(lab)
    else:
        distinct = len(np.unique(sample, axis=0))
        if k > distinct:
            raise ValueError(f"asked for {k} colours but the image only has {distinct}")
        cv2.setRNGSeed(0)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.1)
        _, _, centres = cv2.kmeans(lab, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)

    return _to_rgb(centres)


def _detect_colours(lab: np.ndarray) -> np.ndarray:
    """Greedy palette: most common colours first, skipping near-duplicates."""
    bins, counts = np.unique(np.round(lab / 4.0).astype(np.int32), axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    min_count = _MIN_SHARE * len(lab)

    centres: list[np.ndarray] = []
    for i in order:
        if counts[i] < min_count or len(centres) > MAX_COLORS:
            break
        c = bins[i] * 4.0
        if all(np.linalg.norm(c - p) >= _MERGE_DELTA_E for p in centres):
            centres.append(c)
    centres_arr = np.array(centres, dtype=np.float32)

    # A few Lloyd iterations move each centre to the mean of its pixels.
    for _ in range(5):
        nearest = _nearest(lab, centres_arr)
        for j in range(len(centres_arr)):
            members = lab[nearest == j]
            if len(members):
                centres_arr[j] = members.mean(axis=0)
    return centres_arr


def _nearest(points: np.ndarray, centres: np.ndarray) -> np.ndarray:
    best = np.full(points.shape[:-1], np.inf, dtype=np.float32)
    label = np.zeros(points.shape[:-1], dtype=np.int64)
    for j, c in enumerate(centres):
        d = ((points - c) ** 2).sum(axis=-1)
        closer = d < best
        best[closer] = d[closer]
        label[closer] = j
    return label


def _assign(
    rgb: np.ndarray, opaque: np.ndarray, flat: np.ndarray, palette: np.ndarray
) -> np.ndarray:
    """Label every pixel with a palette index, or -1 for transparent."""
    labels = _nearest(_to_lab(rgb), _to_lab(palette))
    labels[~opaque] = -1

    edge = opaque & ~flat
    if not edge.any() or len(palette) < 2:
        return labels

    # Which palette colours sit (as flat pixels) near each edge pixel.
    size = 2 * _NEIGHBOURHOOD + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    nearby = np.stack(
        [cv2.dilate(((labels == j) & flat).astype(np.uint8), kernel)[edge] > 0 for j in range(len(palette))],
        axis=1,
    )

    residual, blend_label = _best_blend(rgb[edge].astype(np.float32), palette, nearby)

    # Edge pixels that are no blend of their neighbours (thin strokes) keep
    # their nearest palette colour.
    is_blend = residual <= _BLEND_TOLERANCE
    edge_labels = labels[edge]
    edge_labels[is_blend] = blend_label[is_blend]
    labels[edge] = edge_labels
    return labels


def _best_blend(
    px: np.ndarray, palette: np.ndarray, allowed: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """How well each pixel is explained as a palette colour or a blend of two.

    :param px: RGB pixels, float (N, 3).
    :param allowed: Optional bool (N, K): which palette colours each pixel may use.
    :return: RGB distance to the closest colour or blend line, and the palette
        index of the nearer end of that blend.
    """
    if allowed is None:
        allowed = np.ones((len(px), len(palette)), dtype=bool)
    best_residual = np.full(len(px), np.inf, dtype=np.float32)
    best_label = np.zeros(len(px), dtype=np.int64)

    def consider(residual, winner, ok):
        better = ok & (residual < best_residual)
        best_residual[better] = residual[better]
        best_label[better] = winner[better]

    for j, c in enumerate(palette):
        consider(np.linalg.norm(px - c, axis=1), np.full(len(px), j), allowed[:, j])
    for a, b in combinations(range(len(palette)), 2):
        ca, cb = palette[a], palette[b]
        ab = cb - ca
        t = np.clip(((px - ca) @ ab) / max(float(ab @ ab), 1e-6), -_OVERSHOOT, 1.0 + _OVERSHOOT)
        residual = np.linalg.norm(px - (ca + t[:, None] * ab), axis=1)
        consider(residual, np.where(t < 0.5, a, b), allowed[:, a] & allowed[:, b])
    return best_residual, best_label
