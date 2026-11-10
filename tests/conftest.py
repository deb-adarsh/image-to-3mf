from __future__ import annotations

import numpy as np
import pytest


def rgba(height: int, width: int, color=(255, 255, 255), alpha: int = 255) -> np.ndarray:
    """A solid-colour RGBA image."""
    img = np.zeros((height, width, 4), dtype=np.uint8)
    img[..., :3] = color
    img[..., 3] = alpha
    return img


@pytest.fixture
def square_mask() -> np.ndarray:
    """A 30 x 30 px square in a 50 x 50 px image."""
    mask = np.zeros((50, 50), dtype=bool)
    mask[10:40, 10:40] = True
    return mask


@pytest.fixture
def donut_mask() -> np.ndarray:
    """A 40 x 40 px square with a 20 x 20 px hole."""
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:50, 10:50] = True
    mask[20:40, 20:40] = False
    return mask
