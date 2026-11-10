"""Stage 5: write a core-spec 3MF with one coloured part per colour body.

The file holds one mesh object per part, a parent object that groups them
through ``<components>`` so they load as one object, and a ``<basematerials>``
group that gives each part its display colour. Bambu Studio / OrcaSlicer
filament assignment arrives with milestone 3.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

from image_to_3mf.extrude import Mesh

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MODEL_PATH = "3D/3dmodel.model"
DECIMALS = 4  # 0.1 micron: far below printer resolution

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


@dataclass(frozen=True)
class Part:
    name: str
    color: tuple[int, int, int]  # sRGB, 0-255
    mesh: Mesh


def write_3mf(path: str | Path, parts: list[Part], name: str = "image") -> Path:
    """Write ``parts`` as one multi-part object to a 3MF file and return its path."""
    if not parts:
        raise ValueError("nothing to export: no parts")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr(MODEL_PATH, model_xml(parts, name))
    return path


def model_xml(parts: list[Part], name: str = "image") -> str:
    """The 3D model part of the package, as an XML string."""
    material_id = 1
    first_part_id = 2
    parent_id = first_part_id + len(parts)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}">',
        ' <metadata name="Application">image-to-3mf</metadata>',
        " <resources>",
        f'  <basematerials id="{material_id}">',
    ]
    for part in parts:
        color = "#{:02X}{:02X}{:02X}FF".format(*part.color)
        out.append(f"   <base name={quoteattr(part.name)} displaycolor=\"{color}\"/>")
    out.append("  </basematerials>")

    for index, part in enumerate(parts):
        vertices, triangles = _dedupe(part.mesh)
        out.append(
            f'  <object id="{first_part_id + index}" type="model" name={quoteattr(part.name)}'
            f' pid="{material_id}" pindex="{index}">'
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
    out.extend(f'    <component objectid="{first_part_id + i}"/>' for i in range(len(parts)))
    out.append("   </components>")
    out.append("  </object>")
    out.append(" </resources>")
    out.append(" <build>")
    out.append(f'  <item objectid="{parent_id}"/>')
    out.append(" </build>")
    out.append("</model>")
    return "\n".join(out) + "\n"


def _dedupe(mesh: Mesh) -> tuple[np.ndarray, np.ndarray]:
    """Merge vertices that are identical once written, and drop collapsed triangles."""
    rounded = np.round(mesh.vertices, DECIMALS) + 0.0  # + 0.0 turns -0.0 into 0.0
    vertices, inverse = np.unique(rounded, axis=0, return_inverse=True)
    triangles = inverse.reshape(-1)[mesh.triangles]
    a, b, c = triangles.T
    keep = (a != b) & (b != c) & (a != c)
    return vertices, triangles[keep]
