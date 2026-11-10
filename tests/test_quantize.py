from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from conftest import rgba
from image_to_3mf.quantize import load_image, quantize

RED, GREEN, BROWN, WHITE, BLACK = (200, 30, 40), (60, 160, 60), (110, 70, 30), (250, 250, 250), (10, 10, 10)


def _square_expected(img: np.ndarray) -> np.ndarray:
    expected = np.zeros(img.shape[:2], dtype=bool)
    expected[10:30, 10:30] = True
    return expected


# --- single colour -----------------------------------------------------------


def test_dark_artwork_on_white():
    img = rgba(40, 40, color=(255, 255, 255))
    img[10:30, 10:30, :3] = BLACK
    layers = quantize(img)
    assert len(layers) == 1
    assert np.array_equal(layers[0].mask, _square_expected(img))
    assert layers[0].color == BLACK
    assert layers[0].hex == "#0A0A0A"


def test_light_artwork_on_black():
    img = rgba(40, 40, color=(0, 0, 0))
    img[10:30, 10:30, :3] = (240, 240, 240)
    [layer] = quantize(img)
    assert np.array_equal(layer.mask, _square_expected(img))


def test_dark_artwork_on_transparent():
    img = rgba(40, 40, color=(0, 0, 0), alpha=0)
    img[10:30, 10:30] = (*BLACK, 255)
    [layer] = quantize(img)
    assert np.array_equal(layer.mask, _square_expected(img))


def test_light_artwork_on_transparent():
    img = rgba(40, 40, color=(0, 0, 0), alpha=0)
    img[10:30, 10:30] = (*WHITE, 255)
    [layer] = quantize(img)
    assert np.array_equal(layer.mask, _square_expected(img))


def test_blank_image_raises():
    with pytest.raises(ValueError):
        quantize(rgba(20, 20))


def test_fully_transparent_raises():
    with pytest.raises(ValueError):
        quantize(rgba(20, 20, alpha=0))


# --- several colours ---------------------------------------------------------


def _three_colour_image() -> np.ndarray:
    img = rgba(60, 90, color=(255, 255, 255))
    img[10:50, 10:40, :3] = RED  # largest
    img[10:40, 50:80, :3] = GREEN
    img[45:55, 50:70, :3] = BROWN  # smallest
    return img


def test_detects_each_colour_largest_first():
    layers = quantize(_three_colour_image())
    assert [layer.color for layer in layers] == [RED, GREEN, BROWN]
    assert [int(layer.mask.sum()) for layer in layers] == [40 * 30, 30 * 30, 10 * 20]


def test_masks_do_not_overlap():
    layers = quantize(_three_colour_image())
    total = np.sum([layer.mask.astype(int) for layer in layers], axis=0)
    assert total.max() == 1


def test_n_colors_override_merges_colours():
    layers = quantize(_three_colour_image(), n_colors=2)
    assert len(layers) == 2


def test_n_colors_out_of_range_raises():
    with pytest.raises(ValueError):
        quantize(_three_colour_image(), n_colors=0)


def test_blended_edge_goes_to_a_neighbour_not_a_lookalike_colour():
    """A red/green edge blends to brown; it must not be labelled as the brown stem."""
    img = rgba(40, 80, color=(255, 255, 255))
    img[5:35, 5:35, :3] = RED
    img[5:35, 36:60, :3] = GREEN
    img[5:35, 35, :3] = (130, 95, 50)  # 50/50 red/green blend, close to BROWN
    img[10:30, 65:75, :3] = BROWN
    layers = {layer.color: layer.mask for layer in quantize(img)}
    assert not layers[BROWN][:, :62].any()
    assert layers[RED][5:35, 35].all() or layers[GREEN][5:35, 35].all()


def test_thin_stroke_survives():
    """A 1 px dark line is not a blend of its white surroundings, so it is kept."""
    img = rgba(30, 30, color=(255, 255, 255))
    img[5:25, 15, :3] = BLACK
    [layer] = quantize(img)
    assert layer.mask[5:25, 15].all()
    assert layer.mask.sum() == 20


def test_load_image_returns_rgba(tmp_path):
    path = tmp_path / "gray.png"
    Image.new("L", (7, 5), 128).save(path)
    img = load_image(path)
    assert img.shape == (5, 7, 4)
    assert img.dtype == np.uint8
