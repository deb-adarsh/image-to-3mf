from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from conftest import TEMPLATE_SETTINGS, write_bambu_template
from image_to_3mf.bambu import load_bambu_project, model_settings_xml

RED, GREEN = (200, 30, 40), (60, 160, 60)


# --- model_settings.config ---------------------------------------------------


def test_model_settings_assign_one_filament_per_part():
    root = ET.fromstring(model_settings_xml(9, "apple", [(2, "Red", 10, 1), (3, "Green", 20, 2)]))
    [obj] = root.findall("object")
    assert obj.get("id") == "9"
    meta = {m.get("key"): m.get("value") for m in obj.findall("metadata") if m.get("key")}
    assert meta == {"name": "apple", "extruder": "1"}

    parts = obj.findall("part")
    assert [p.get("id") for p in parts] == ["2", "3"]
    assert {p.get("subtype") for p in parts} == {"normal_part"}
    for slot, part in enumerate(parts, start=1):
        pmeta = {m.get("key"): m.get("value") for m in part.findall("metadata")}
        assert pmeta["extruder"] == str(slot)
        assert pmeta["matrix"] == "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"
    assert parts[1].find("mesh_stat").get("face_count") == "20"


def test_model_settings_escape_names():
    root = ET.fromstring(model_settings_xml(3, 'a "b" & <c>', [(2, "x & y", 1, 1)]))
    assert root.find("object/metadata").get("value") == 'a "b" & <c>'


# --- template project ---------------------------------------------------------


def test_loads_template(bambu_template):
    project = load_bambu_project(bambu_template)
    assert project.application == "BambuStudio-02.04.00.70"
    assert project.filament_count == 4
    assert project.plate_centre == (90.0, 90.0)


def test_sets_first_filament_colours_only(bambu_template):
    project = load_bambu_project(bambu_template)
    settings = project.with_colours([RED, GREEN])
    assert settings["filament_colour"] == ["#C81E28", "#3CA03C", "#FF0000", "#00FF00"]
    # Everything else, including the user's filament types, is untouched.
    assert {k: v for k, v in settings.items() if k != "filament_colour"} == {
        k: v for k, v in TEMPLATE_SETTINGS.items() if k != "filament_colour"
    }
    assert project.settings["filament_colour"][0] == "#FFFFFF"  # template not modified


def test_keeps_the_template_colour_format(tmp_path):
    settings = dict(TEMPLATE_SETTINGS, filament_colour=["#FFFFFFFF", "#000000FF"])
    settings["filament_multi_colour"] = ["#FFFFFFFF", "#000000FF"]
    project = load_bambu_project(write_bambu_template(tmp_path / "t.3mf", settings))
    result = project.with_colours([RED])
    assert result["filament_colour"] == ["#C81E28FF", "#000000FF"]
    assert result["filament_multi_colour"] == ["#C81E28FF", "#000000FF"]


def test_too_few_template_filaments(bambu_template):
    project = load_bambu_project(bambu_template)
    with pytest.raises(ValueError, match="has 4 filament"):
        project.with_colours([RED] * 5)


def test_plate_centre_falls_back_to_256_bed(tmp_path):
    settings = {k: v for k, v in TEMPLATE_SETTINGS.items() if k != "printable_area"}
    project = load_bambu_project(write_bambu_template(tmp_path / "t.3mf", settings))
    assert project.plate_centre == (128.0, 128.0)


def test_rejects_files_not_saved_by_bambu_studio(tmp_path):
    with pytest.raises(ValueError, match="not saved by Bambu Studio"):
        load_bambu_project(write_bambu_template(tmp_path / "t.3mf", application="image-to-3mf"))
    (tmp_path / "x.3mf").write_text("not a zip")
    with pytest.raises(ValueError, match="not a 3MF"):
        load_bambu_project(tmp_path / "x.3mf")
