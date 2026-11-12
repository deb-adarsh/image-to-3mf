from __future__ import annotations

import pytest

from image_to_3mf.text import render_text


def test_one_part_per_glyph():
    geom = render_text("LT", 10)
    assert len(geom.geoms) == 2
    assert geom.is_valid


def test_size_is_in_millimetres():
    small, large = render_text("H", 5), render_text("H", 10)
    h_small = small.bounds[3] - small.bounds[1]
    h_large = large.bounds[3] - large.bounds[1]
    assert h_large == pytest.approx(2 * h_small, rel=0.05)
    assert 0.5 * 10 < h_large < 10  # a capital is a bit under the em size


def test_counters_are_holes():
    [o] = render_text("O", 10).geoms
    assert len(o.interiors) == 1


def test_blank_text():
    assert render_text("   ", 10).is_empty


def test_bad_font_raises(tmp_path):
    with pytest.raises(ValueError, match="cannot load font"):
        render_text("A", 10, tmp_path / "missing.ttf")
