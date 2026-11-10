from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh
from PIL import Image

from image_to_3mf.cli import main

SAMPLES = Path(__file__).parent.parent / "samples"


def _write_logo(path):
    """A dark ring on white: one part with one hole."""
    yy, xx = np.mgrid[0:120, 0:200]
    r2 = (xx - 100) ** 2 + (yy - 60) ** 2
    ring = (r2 <= 50**2) & (r2 >= 25**2)
    img = np.full((120, 200, 3), 255, dtype=np.uint8)
    img[ring] = (0, 0, 0)
    Image.fromarray(img).save(path)


def test_end_to_end_writes_watertight_stl(tmp_path, capsys):
    src = tmp_path / "ring.png"
    out = tmp_path / "ring.stl"
    _write_logo(src)

    assert main([str(src), "-o", str(out), "--width", "100", "--depths", "3"]) == 0

    mesh = trimesh.load(out)
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    # Image is 200 px wide -> 0.5 mm/px; the ring is 100 px across -> 50 mm.
    assert mesh.extents == pytest.approx((50, 50, 3), abs=0.6)
    assert "1 part(s)" in capsys.readouterr().out


def test_missing_input_returns_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope.png")]) == 1
    assert "error:" in capsys.readouterr().err


def test_sample_logo(tmp_path, capsys):
    out = tmp_path / "logo.stl"
    assert main([str(SAMPLES / "logo_bw.png"), "-o", str(out), "--width", "80"]) == 0
    assert trimesh.load(out).is_watertight
    # Ring, star and the three letters of "3MF".
    assert "5 part(s)" in capsys.readouterr().out
