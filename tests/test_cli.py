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
    # Height: 1.5 mm plate + 3 mm raised ring, merged into one solid.
    assert mesh.extents == pytest.approx((50, 50, 4.5), abs=0.6)
    assert "1 part(s)" in capsys.readouterr().out


def test_sample_logo(tmp_path, capsys):
    out = tmp_path / "logo.3mf"
    assert main([str(SAMPLES / "logo_bw.png"), "-o", str(out), "--width", "80"]) == 0
    (plate_colour, plate), (colour, mesh) = _read_parts(out)
    assert plate_colour == "#FFFFFFFF"  # the image background
    assert plate.is_watertight and mesh.is_watertight
    # Ring, star and the three letters of "3MF".
    assert "5 part(s)" in capsys.readouterr().out


def test_sample_apple_has_one_watertight_body_per_colour(tmp_path, capsys):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--depths", "2", "3"]) == 0

    assert _strict_warnings(out) == 0
    parts = _read_parts(out)
    # A plate in the largest colour (the background is transparent), then the colours.
    assert [c for c, _ in parts] == ["#C81E28FF", "#C81E28FF", "#3CA03CFF", "#6E461EFF", "#FAFAFAFF"]
    assert all(m.is_watertight and m.volume > 0 for _, m in parts)
    # 1.5 mm plate; colours stand on it, the first 2 mm, the rest repeat 3 mm.
    assert [round(m.bounds[1][2], 3) for _, m in parts] == [1.5, 3.5, 4.5, 4.5, 4.5]
    assert {round(m.bounds[0][2], 3) for _, m in parts[1:]} == {1.5}
    out = capsys.readouterr().out
    assert out.count("1 part(s)") == 4
    assert "base plate: filament 1 #C81E28" in out
    assert "filament 4: #FAFAFA" in out


def test_plate_shares_a_filament_with_the_same_colour(tmp_path):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out)]) == 0
    settings = ET.fromstring(zipfile.ZipFile(out).read("Metadata/model_settings.config"))
    slots = [
        next(m.get("value") for m in part.findall("metadata") if m.get("key") == "extruder")
        for part in settings.iter("part")
    ]
    assert slots == ["1", "1", "2", "3", "4"]


def test_inlay_style_is_flush(tmp_path):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--style", "inlay", "--base", "2"]) == 0
    parts = _read_parts(out)
    assert all(m.is_watertight for _, m in parts)
    assert {round(m.bounds[1][2], 3) for _, m in parts} == {2.0}  # one flat top
    assert {round(m.bounds[0][2], 3) for _, m in parts[1:]} == {1.4}  # 0.6 mm inlays
    # The plate keeps its full footprint: colours are cut into it.
    plate = parts[0][1]
    assert plate.volume < plate.area  # far below footprint x 2 mm once inlays are removed


def test_inlay_needs_a_plate_deep_enough(tmp_path, capsys):
    args = [str(SAMPLES / "apple.png"), "-o", str(tmp_path / "a.3mf"), "--style", "inlay"]
    assert main(args + ["--base", "0"]) == 1
    assert main(args + ["--base", "1", "--depths", "1.5"]) == 1
    assert "deeper than" in capsys.readouterr().err


def test_no_plate(tmp_path):
    out = tmp_path / "apple.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--base", "0"]) == 0
    parts = _read_parts(out)
    assert len(parts) == 4
    assert {round(m.bounds[0][2], 3) for _, m in parts} == {0.0}


def test_margin_widens_the_plate(tmp_path):
    a, b = tmp_path / "a.3mf", tmp_path / "b.3mf"
    assert main([str(SAMPLES / "apple.png"), "-o", str(a)]) == 0
    assert main([str(SAMPLES / "apple.png"), "-o", str(b), "--margin", "3"]) == 0
    width_a = np.ptp(_read_parts(a)[0][1].vertices[:, 0])
    width_b = np.ptp(_read_parts(b)[0][1].vertices[:, 0])
    assert width_b == pytest.approx(width_a + 6, abs=0.1)


def test_text_line(tmp_path, capsys):
    plain, texted = tmp_path / "plain.3mf", tmp_path / "text.3mf"
    assert main([str(SAMPLES / "logo_bw.png"), "-o", str(plain)]) == 0
    capsys.readouterr()
    assert main([str(SAMPLES / "logo_bw.png"), "-o", str(texted), "--text", "Hi", "--text-size", "10"]) == 0

    # Ink-coloured text below the artwork, held by one connected plate.
    (_, plate), (_, ink) = _read_parts(texted)
    (_, _), (_, plain_ink) = _read_parts(plain)
    assert ink.bounds[0][1] < plain_ink.bounds[0][1] - 10
    assert plate.is_watertight
    assert plate.euler_number == 2  # one closed solid without holes: the plate is one piece
    # 5 logo parts, plus "H" and the stem and dot of "i".
    assert "8 part(s)" in capsys.readouterr().out


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
    assert main([str(SAMPLES / "apple.png"), "-o", str(out), "--colors", "2", "--base", "0"]) == 0
    assert len(_read_parts(out)) == 2


def test_unknown_output_format(tmp_path, capsys):
    assert main([str(SAMPLES / "apple.png"), "-o", str(tmp_path / "a.obj")]) == 1
    assert "must end in" in capsys.readouterr().err


def test_missing_input_returns_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope.png")]) == 1
    assert "error:" in capsys.readouterr().err
