from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import lib3mf
import numpy as np
import pytest
import trimesh
from PIL import Image

from conftest import TEMPLATE_SETTINGS, write_bambu_template
from image_to_3mf.cli import main
from image_to_3mf.export_3mf import CORE_NS, MODEL_PATH

SAMPLES = Path(__file__).parent.parent / "samples"
NS = {"m": CORE_NS}


def _write_ring(path):
    """A dark ring on white: one part with one hole."""
    yy, xx = np.mgrid[0:120, 0:200]
    r2 = (xx - 100) ** 2 + (yy - 60) ** 2
    ring = (r2 <= 50**2) & (r2 >= 25**2)
    img = np.full((120, 200, 3), 255, dtype=np.uint8)
    img[ring] = (0, 0, 0)
    Image.fromarray(img).save(path)


def _read_parts(path) -> list[tuple[str, trimesh.Trimesh]]:
    """(display colour, mesh) for every mesh object in a 3MF."""
    root = ET.fromstring(zipfile.ZipFile(path).read(MODEL_PATH))
    colours = [b.get("displaycolor") for b in root.iterfind(".//m:base", NS)]
    parts = []
    for obj in root.iterfind(".//m:object", NS):
        mesh = obj.find("m:mesh", NS)
        if mesh is None:
            continue
        v = [[float(x.get(k)) for k in "xyz"] for x in mesh.iterfind("m:vertices/m:vertex", NS)]
        t = [[int(x.get(k)) for k in ("v1", "v2", "v3")] for x in mesh.iterfind("m:triangles/m:triangle", NS)]
        parts.append((colours[int(obj.get("pindex"))], trimesh.Trimesh(v, t, process=False)))
    return parts


def _strict_warnings(path) -> int:
    model = lib3mf.get_wrapper().CreateModel()
    reader = model.QueryReader("3mf")
    reader.SetStrictModeActive(True)
    reader.ReadFromFile(str(path))
    return reader.GetWarningCount()


def test_ring_to_stl(tmp_path, capsys):
    src, out = tmp_path / "ring.png", tmp_path / "ring.stl"
    _write_ring(src)

    assert main([str(src), "-o", str(out), "--width", "100", "--depths", "3"]) == 0

    mesh = trimesh.load(out)
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    # Image is 200 px wide -> 0.5 mm/px; the ring is 100 px across -> 50 mm.
    assert mesh.extents == pytest.approx((50, 50, 3), abs=0.6)
    assert "1 part(s)" in capsys.readouterr().out


def test_sample_logo(tmp_path, capsys):
    out = tmp_path / "logo.3mf"
    assert main([str(SAMPLES / "logo_bw.png"), "-o", str(out), "--width", "80"]) == 0
    [(colour, mesh)] = _read_parts(out)
    assert mesh.is_watertight
    # Ring, star and the three letters of "3MF".
    assert "5 part(s)" in capsys.readouterr().out


def test_sample_apple_has_one_watertight_body_per_colour(tmp_path, capsys):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--depths", "2", "3"]) == 0

    assert _strict_warnings(out) == 0
    parts = _read_parts(out)
    assert [c for c, _ in parts] == ["#C81E28FF", "#3CA03CFF", "#6E461EFF", "#FAFAFAFF"]
    assert all(m.is_watertight and m.volume > 0 for _, m in parts)
    # Depths: the first colour 2 mm, the rest repeat the last value, 3 mm.
    assert [round(m.bounds[1][2], 3) for _, m in parts] == [2, 3, 3, 3]
    out = capsys.readouterr().out
    assert out.count("1 part(s)") == 4
    assert "filament 4: #FAFAFA" in out


def test_bambu_project_template(tmp_path, capsys, bambu_template):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--bambu-project", str(bambu_template)]) == 0
    with zipfile.ZipFile(out) as zf:
        settings = json.loads(zf.read("Metadata/project_settings.config"))
    assert settings["filament_colour"] == ["#C81E28", "#3CA03C", "#6E461E", "#FAFAFA"]
    assert _strict_warnings(out) == 0


def test_bambu_project_needs_enough_filaments(tmp_path, capsys):
    two_filaments = write_bambu_template(
        tmp_path / "two.3mf", dict(TEMPLATE_SETTINGS, filament_colour=["#FFFFFF", "#000000"])
    )
    args = [str(SAMPLES / "apple.png"), "-o", str(tmp_path / "a.3mf"), "--bambu-project", str(two_filaments)]
    assert main(args) == 1
    assert "add filaments in Bambu Studio" in capsys.readouterr().err


def test_bambu_project_needs_3mf_output(tmp_path, capsys, bambu_template):
    args = [str(SAMPLES / "apple.png"), "-o", str(tmp_path / "a.stl"), "--bambu-project", str(bambu_template)]
    assert main(args) == 1


def test_colors_override(tmp_path, capsys):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--colors", "2"]) == 0
    assert len(_read_parts(out)) == 2


def test_unknown_output_format(tmp_path, capsys):
    assert main([str(SAMPLES / "apple.png"), "-o", str(tmp_path / "a.obj")]) == 1
    assert "must end in" in capsys.readouterr().err


def test_missing_input_returns_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope.png")]) == 1
    assert "error:" in capsys.readouterr().err
