"""Stage 1: load an image and reduce it to binary colour masks.

Milestone 1 only needs a single foreground mask (black-and-white artwork).
N-colour k-means quantization arrives with milestone 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Pixels with alpha below this are treated as transparent background.
_ALPHA_CUTOFF = 128


@dataclass(frozen=True)
class ColorMask:
    """One colour of the artwork: its display colour and where it is."""

    color: tuple[int, int, int]  # sRGB, 0-255
    mask: np.ndarray  # bool, shape (H, W), True where this colour is


def load_image(path: str | Path) -> np.ndarray:
    """Load any Pillow-readable image as an RGBA uint8 array of shape (H, W, 4)."""
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.uint8).copy()


def binarize(rgba: np.ndarray) -> ColorMask:
    """Split single-colour artwork into foreground and background.

    Transparent pixels are flattened onto whichever of black or white
    contrasts with the opaque artwork, so both dark and light logos on a
    transparent background survive. The flattened image is thresholded with
    Otsu's method, and the class that dominates the image border is taken as
    background.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"expected an RGBA array of shape (H, W, 4), got {rgba.shape}")

    gray = _flatten_to_gray(rgba)
    _, dark_is_zero = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    light = dark_is_zero > 0  # True for the lighter class

    border = np.concatenate([light[0, :], light[-1, :], light[:, 0], light[:, -1]])
    background_is_light = border.mean() >= 0.5
    mask = ~light if background_is_light else light

    if not mask.any():
        raise ValueError("no foreground found in image")

    color = tuple(int(c) for c in np.median(rgba[mask][:, :3], axis=0))
    return ColorMask(color=color, mask=mask)


def _flatten_to_gray(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float32)
    alpha = rgba[..., 3:].astype(np.float32) / 255.0
    gray_rgb = cv2.cvtColor(rgba[..., :3], cv2.COLOR_RGB2GRAY)

    opaque = rgba[..., 3] >= _ALPHA_CUTOFF
    if opaque.all():
        return gray_rgb
    if not opaque.any():
        raise ValueError("image is fully transparent")

    # Pick the backdrop that contrasts with the artwork itself.
    backdrop = 0.0 if gray_rgb[opaque].mean() > 127 else 255.0
    flat = rgb * alpha + backdrop * (1.0 - alpha)
    return cv2.cvtColor(flat.round().astype(np.uint8), cv2.COLOR_RGB2GRAY)
