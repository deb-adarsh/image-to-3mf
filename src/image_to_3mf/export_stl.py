"""Binary STL writer, used for milestone 1's single-colour output."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from image_to_3mf.extrude import Mesh

_RECORD = np.dtype(
    [("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")]
)


def write_stl(path: str | Path, mesh: Mesh) -> Path:
    """Write ``mesh`` as a binary STL file and return its path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tris = mesh.vertices[mesh.triangles]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)

    records = np.zeros(len(tris), dtype=_RECORD)
    records["normal"] = normals
    records["vertices"] = tris

    with path.open("wb") as f:
        f.write(b"image-to-3mf".ljust(80, b"\0"))
        f.write(np.uint32(len(records)).tobytes())
        f.write(records.tobytes())
    return path
