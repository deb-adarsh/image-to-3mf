from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import lib3mf
import numpy as np
import pytest
from shapely.geometry import MultiPolygon, box

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
        assert set(zf.namelist()) == {"[Content_Types].xml", "_rels/.rels", MODEL_PATH}


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
