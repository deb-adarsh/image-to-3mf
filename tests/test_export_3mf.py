from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile

import lib3mf
import numpy as np
import pytest
from shapely.geometry import MultiPolygon, box

from image_to_3mf.bambu import MODEL_SETTINGS_PATH, PROJECT_SETTINGS_PATH, load_bambu_project
from image_to_3mf.export_3mf import CORE_NS, MODEL_PATH, Part, model_xml, write_3mf
from image_to_3mf.extrude import Mesh, extrude_layers, to_mesh

NS = {"m": CORE_NS}


def _two_parts() -> list[Part]:
    layers = [MultiPolygon([box(0, 0, 10, 10)]), MultiPolygon([box(10, 0, 20, 10)])]
    low, high = extrude_layers(layers, [1.0, 2.0])
    return [
        Part(name="Colour 1 #C81E28", color=(200, 30, 40), mesh=to_mesh(low)),
        Part(name="Colour 2 #3CA03C", color=(60, 160, 60), mesh=to_mesh(high)),
    ]


def _iterate(it, getter):
    items = []
    while it.MoveNext():
        items.append(getattr(it, getter)())
    return items


def test_file_passes_strict_lib3mf_read(tmp_path):
    path = write_3mf(tmp_path / "two.3mf", _two_parts(), name="two")

    model = lib3mf.get_wrapper().CreateModel()
    reader = model.QueryReader("3mf")
    reader.SetStrictModeActive(True)
    reader.ReadFromFile(str(path))

    assert reader.GetWarningCount() == 0
    meshes = _iterate(model.GetMeshObjects(), "GetCurrentMeshObject")
    assert [m.GetName() for m in meshes] == ["Colour 1 #C81E28", "Colour 2 #3CA03C"]
    assert all(m.IsManifoldAndOriented() for m in meshes)

    [parent] = _iterate(model.GetComponentsObjects(), "GetCurrentComponentsObject")
    assert parent.GetName() == "two"
    assert parent.GetComponentCount() == 2
    assert len(_iterate(model.GetBuildItems(), "GetCurrent")) == 1


def test_package_layout(tmp_path):
    path = write_3mf(tmp_path / "two.3mf", _two_parts())
    with zipfile.ZipFile(path) as zf:
        assert set(zf.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            MODEL_PATH,
            MODEL_SETTINGS_PATH,
        }


# --- Bambu Studio extensions -------------------------------------------------


def _read(path, member):
    with zipfile.ZipFile(path) as zf:
        return zf.read(member)


def test_model_settings_ids_match_the_model(tmp_path):
    path = write_3mf(tmp_path / "two.3mf", _two_parts(), name="two")
    model = ET.fromstring(_read(path, MODEL_PATH))
    settings = ET.fromstring(_read(path, MODEL_SETTINGS_PATH))

    parent = model.findall(".//m:object", NS)[-1]
    components = [c.get("objectid") for c in parent.iterfind("m:components/m:component", NS)]
    [obj] = settings.findall("object")
    assert obj.get("id") == parent.get("id")
    assert [p.get("id") for p in obj.findall("part")] == components

    names = {o.get("id"): o.get("name") for o in model.iterfind(".//m:object", NS)}
    for slot, part in enumerate(obj.findall("part"), start=1):
        meta = {m.get("key"): m.get("value") for m in part.findall("metadata")}
        assert meta["extruder"] == str(slot)
        assert meta["name"] == names[part.get("id")]


def test_model_is_marked_for_bambu_studio(tmp_path):
    model = _read(write_3mf(tmp_path / "two.3mf", _two_parts()), MODEL_PATH).decode()
    assert 'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"' in model
    assert '<metadata name="BambuStudio:3mfVersion">1</metadata>' in model
    # Without a template it stays a third-party file: no project settings to apply.
    assert "<metadata name=\"Application\">image-to-3mf</metadata>" in model


def _placed_bounds(path):
    model = ET.fromstring(_read(path, MODEL_PATH))
    t = [float(v) for v in model.find(".//m:build/m:item", NS).get("transform").split()]
    offset = np.array(t[9:12])
    verts = np.array(
        [[float(v.get(k)) for k in "xyz"] for v in model.iterfind(".//m:vertex", NS)]
    ) + offset
    return verts.min(axis=0), verts.max(axis=0)


def test_object_is_centred_on_a_256_mm_plate(tmp_path):
    lo, hi = _placed_bounds(write_3mf(tmp_path / "two.3mf", _two_parts()))
    assert (lo + hi)[:2] / 2 == pytest.approx((128, 128))
    assert lo[2] == pytest.approx(0)


def test_template_project(tmp_path, bambu_template):
    project = load_bambu_project(bambu_template)
    path = write_3mf(tmp_path / "two.3mf", _two_parts(), project=project)

    model = _read(path, MODEL_PATH).decode()
    assert "<metadata name=\"Application\">BambuStudio-02.04.00.70</metadata>" in model
    settings = json.loads(_read(path, PROJECT_SETTINGS_PATH))
    assert settings["filament_colour"] == ["#C81E28", "#3CA03C", "#FF0000", "#00FF00"]
    assert settings["filament_type"] == ["PLA", "PLA", "PETG", "PLA"]

    lo, hi = _placed_bounds(path)
    assert (lo + hi)[:2] / 2 == pytest.approx((90, 90))  # template printer: 180 mm bed


def test_each_part_gets_its_own_display_colour():
    root = ET.fromstring(model_xml(_two_parts()))
    colours = [b.get("displaycolor") for b in root.iterfind(".//m:basematerials/m:base", NS)]
    assert colours == ["#C81E28FF", "#3CA03CFF"]

    meshes = [o for o in root.iterfind(".//m:object", NS) if o.find("m:mesh", NS) is not None]
    assert [int(o.get("pindex")) for o in meshes] == [0, 1]
    assert {o.get("pid") for o in meshes} == {"1"}
    assert root.find(".//m:build/m:item", NS).get("objectid") == root.findall(".//m:object", NS)[-1].get("id")


def test_vertices_are_unique_per_part():
    root = ET.fromstring(model_xml(_two_parts()))
    for mesh in root.iterfind(".//m:mesh", NS):
        coords = [tuple(v.attrib.values()) for v in mesh.iterfind("m:vertices/m:vertex", NS)]
        assert len(coords) == len(set(coords))


def test_duplicate_vertices_are_merged():
    # Two triangles of a square, written with a duplicated corner.
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0], [1, 1, 0], [0, 1, 0]], float)
    mesh = Mesh(vertices=vertices, triangles=np.array([[0, 1, 2], [3, 4, 5]]))
    root = ET.fromstring(model_xml([Part("p", (0, 0, 0), mesh)]))
    assert len(root.findall(".//m:vertex", NS)) == 4
    assert len(root.findall(".//m:triangle", NS)) == 2


def test_names_are_escaped():
    part = _two_parts()[0]
    root = ET.fromstring(model_xml([Part('a "<b>" & c', part.color, part.mesh)], name="x & y"))
    assert root.find(".//m:base", NS).get("name") == 'a "<b>" & c'


def test_no_parts_raises(tmp_path):
    with pytest.raises(ValueError):
        write_3mf(tmp_path / "empty.3mf", [])


def test_parts_can_share_a_filament(tmp_path):
    low, high = _two_parts()
    parts = [Part("Base", (200, 30, 40), low.mesh, filament=1), Part("Red", (200, 30, 40), high.mesh, filament=1)]
    path = write_3mf(tmp_path / "shared.3mf", parts)
    settings = ET.fromstring(_read(path, MODEL_SETTINGS_PATH))
    slots = [m.get("value") for m in settings.iter("metadata") if m.get("key") == "extruder"]
    assert slots == ["1", "1", "1"]  # object default, then both parts


def test_filament_slots_must_not_skip(tmp_path):
    low, high = _two_parts()
    with pytest.raises(ValueError, match="without gaps"):
        write_3mf(tmp_path / "x.3mf", [Part("a", (0, 0, 0), low.mesh, filament=1), Part("b", (1, 1, 1), high.mesh, filament=3)])


def test_nearly_coincident_vertices_stay_apart():
    """Regression: rounding merged vertices 0.02 microns apart and opened holes."""
    vertices = np.array([[0, 0, 0], [2e-5, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    triangles = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    root = ET.fromstring(model_xml([Part("p", (0, 0, 0), Mesh(vertices, triangles))]))
    xs = [float(v.get("x")) for v in root.iterfind(".//m:vertex", NS)]
    assert len(xs) == 4 and len(root.findall(".//m:triangle", NS)) == 4
    assert np.float32(max(xs)) == np.float32(2e-5)  # written exactly


def test_lobes_touching_at_a_point_stay_watertight():
    """Regression: merging the kernel's two vertices at a pinch point made the mesh non-manifold."""
    from image_to_3mf.extrude import extrude

    lobes = MultiPolygon([box(0, 0, 1, 1), box(1, 1, 2, 2)])  # touch at (1, 1)
    mesh = to_mesh(extrude(lobes, 1.0))
    root = ET.fromstring(model_xml([Part("p", (0, 0, 0), mesh)]))
    v = [[float(x.get(k)) for k in "xyz"] for x in root.iterfind(".//m:vertex", NS)]
    t = [[int(x.get(k)) for k in ("v1", "v2", "v3")] for x in root.iterfind(".//m:triangle", NS)]
    import trimesh

    assert trimesh.Trimesh(v, t, process=False).is_watertight
