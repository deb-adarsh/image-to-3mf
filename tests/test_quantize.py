from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from conftest import rgba
from image_to_3mf.quantize import binarize, load_image


def _square_expected(img: np.ndarray) -> np.ndarray:
    expected = np.zeros(img.shape[:2], dtype=bool)
    expected[10:30, 10:30] = True
    return expected


def test_dark_artwork_on_white():
    img = rgba(40, 40, color=(255, 255, 255))
    img[10:30, 10:30, :3] = (10, 10, 10)
    layer = binarize(img)
    assert np.array_equal(layer.mask, _square_expected(img))
    assert layer.color == (10, 10, 10)


def test_light_artwork_on_black():
    img = rgba(40, 40, color=(0, 0, 0))
    img[10:30, 10:30, :3] = (240, 240, 240)
    layer = binarize(img)
    assert np.array_equal(layer.mask, _square_expected(img))


def test_dark_artwork_on_transparent():
    img = rgba(40, 40, color=(0, 0, 0), alpha=0)
    img[10:30, 10:30] = (10, 10, 10, 255)
    assert np.array_equal(binarize(img).mask, _square_expected(img))


def test_light_artwork_on_transparent():
    img = rgba(40, 40, color=(0, 0, 0), alpha=0)
    img[10:30, 10:30] = (250, 250, 250, 255)
    assert np.array_equal(binarize(img).mask, _square_expected(img))


def test_blank_image_raises():
    with pytest.raises(ValueError):
        binarize(rgba(20, 20))


def test_fully_transparent_raises():
    with pytest.raises(ValueError):
        binarize(rgba(20, 20, alpha=0))


def test_load_image_returns_rgba(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (7, 5), 128).save(path)
    img = load_image(path)
    assert img.shape == (5, 7, 4)
    assert img.dtype == np.uint8
