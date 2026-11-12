"""Stage 5: write a 3MF with one coloured part per colour body.

Core spec, readable by any 3MF tool: one mesh object per part, a parent
object that groups them through ``<components>`` so they load as one object,
and a ``<basematerials>`` group that gives each part its display colour.

Bambu Studio / OrcaSlicer extensions (see ``bambu.py``): per-part filament
slots in ``Metadata/model_settings.config`` and, given a template project,
``Metadata/project_settings.config`` with the filament colours set. The
object is placed in the middle of the build plate.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import numpy as np

from image_to_3mf import bambu
from image_to_3mf.extrude import Mesh

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MODEL_PATH = "3D/3dmodel.model"
APPLICATION = "image-to-3mf"
DECIMALS = 4  # 0.1 micron: far below printer resolution

# Like Bambu Studio, declare no content type for the Metadata/*.config files.
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

_RELS = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/{MODEL_PATH}" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""

_MATERIAL_ID = 1
_FIRST_PART_ID = 2


@dataclass(frozen=True)
class Part:
    name: str
    color: tuple[int, int, int]  # sRGB, 0-255
    mesh: Mesh
    filament: int | None = None  # 1-based slot; default: the part's position


def filament_slots(parts: list[Part]) -> list[int]:
    """Each part's 1-based filament slot."""
    return [p.filament if p.filament is not None else i + 1 for i, p in enumerate(parts)]


def slot_colours(parts: list[Part]) -> list[tuple[int, int, int]]:
    """The colour of each filament slot 1..N (from the first part using it)."""
    slots = filament_slots(parts)
    colours: dict[int, tuple[int, int, int]] = {}
    for slot, part in zip(slots, parts):
        colours.setdefault(slot, part.color)
    if sorted(colours) != list(range(1, len(colours) + 1)):
        raise ValueError(f"filament slots must be 1..N without gaps, got {sorted(colours)}")
    return [colours[s] for s in range(1, len(colours) + 1)]


def write_3mf(
    path: str | Path,
    parts: list[Part],
    name: str = "image",
    project: bambu.BambuProject | None = None,
) -> Path:
    """Write ``parts`` as one multi-part object to a 3MF file and return its path.

    Each part prints with its ``filament`` slot (default: its position, 1-based).
    With a template ``project``,
    the file becomes a Bambu Studio project that reuses the template's printer,
    process and filament settings, with filament colours set from the parts.
    """
    if not parts:
        raise ValueError("nothing to export: no parts")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    meshes = [_dedupe(part.mesh) for part in parts]
    centre = project.plate_centre if project else bambu.DEFAULT_PLATE_CENTRE
    translation = _centre_on(meshes, centre)
    application = project.application if project else APPLICATION
    colours = slot_colours(parts)  # also checks the slots run 1..N
    settings = project.with_colours(colours) if project else None

    parent_id = _FIRST_PART_ID + len(parts)
    part_info = [
        (_FIRST_PART_ID + i, part.name, len(triangles), slot)
        for i, (part, (_, triangles), slot) in enumerate(zip(parts, meshes, filament_slots(parts)))
    ]

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr(MODEL_PATH, _model_xml(parts, meshes, name, application, translation))
        zf.writestr(bambu.MODEL_SETTINGS_PATH, bambu.model_settings_xml(parent_id, name, part_info))
        if settings is not None:
            zf.writestr(bambu.PROJECT_SETTINGS_PATH, bambu.project_settings_json(settings))
    return path


def model_xml(parts: list[Part], name: str = "image") -> str:
    """The 3D model part of the package, as an XML string (no plate placement)."""
    return _model_xml(parts, [_dedupe(p.mesh) for p in parts], name, APPLICATION, (0.0, 0.0, 0.0))


def _model_xml(parts, meshes, name, application, translation) -> str:
    parent_id = _FIRST_PART_ID + len(parts)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}"'
        f' xmlns:BambuStudio="{bambu.NAMESPACE}">',
        f' <metadata name="Application">{escape(application)}</metadata>',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        " <resources>",
        f'  <basematerials id="{_MATERIAL_ID}">',
    ]
    for part in parts:
        color = "#{:02X}{:02X}{:02X}FF".format(*part.color)
        out.append(f"   <base name={quoteattr(part.name)} displaycolor=\"{color}\"/>")
    out.append("  </basematerials>")

    for index, (part, (vertices, triangles)) in enumerate(zip(parts, meshes)):
        out.append(
            f'  <object id="{_FIRST_PART_ID + index}" type="model" name={quoteattr(part.name)}'
            f' pid="{_MATERIAL_ID}" pindex="{index}">'
        )
        out.append("   <mesh>")
        out.append("    <vertices>")
        out.extend(
            f'     <vertex x="{x:.{DECIMALS}f}" y="{y:.{DECIMALS}f}" z="{z:.{DECIMALS}f}"/>'
            for x, y, z in vertices
        )
        out.append("    </vertices>")
        out.append("    <triangles>")
        out.extend(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in triangles)
        out.append("    </triangles>")
        out.append("   </mesh>")
        out.append("  </object>")

    out.append(f'  <object id="{parent_id}" type="model" name={quoteattr(name)}>')
    out.append("   <components>")
    out.extend(f'    <component objectid="{_FIRST_PART_ID + i}"/>' for i in range(len(parts)))
    out.append("   </components>")
    out.append("  </object>")
    out.append(" </resources>")
    out.append(" <build>")
    tx, ty, tz = (f"{v:.{DECIMALS}f}" for v in translation)
    out.append(f'  <item objectid="{parent_id}" transform="1 0 0 0 1 0 0 0 1 {tx} {ty} {tz}"/>')
    out.append(" </build>")
    out.append("</model>")
    return "\n".join(out) + "\n"


def _centre_on(meshes, centre: tuple[float, float]) -> tuple[float, float, float]:
    """Translation that puts the meshes' footprint centre on ``centre``, resting on z = 0."""
    vertices = np.concatenate([v for v, _ in meshes])
    lo, hi = vertices.min(axis=0), vertices.max(axis=0)
    mid = (lo + hi) / 2
    return (centre[0] - mid[0] + 0.0, centre[1] - mid[1] + 0.0, -lo[2] + 0.0)  # no -0.0


def _dedupe(mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    """Merge vertices that are identical once written, and drop collapsed triangles."""
    rounded = np.round(mesh.vertices, DECIMALS) + 0.0  # + 0.0 turns -0.0 into 0.0
    vertices, inverse = np.unique(rounded, axis=0, return_inverse=True)
    triangles = inverse.reshape(-1)[mesh.triangles]
    a, b, c = triangles.T
    keep = (a != b) & (b != c) & (a != c)
    return vertices, triangles[keep]
