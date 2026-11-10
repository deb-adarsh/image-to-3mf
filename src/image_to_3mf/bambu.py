"""Bambu Studio / OrcaSlicer extensions to the 3MF (stage 5).

Two files under ``Metadata/``:

- ``model_settings.config`` (XML) gives each part its filament slot, so the
  parts load with filaments already assigned. Always written.
- ``project_settings.config`` (JSON) holds the project's printer, process and
  filament presets. Bambu Studio applies it as the whole project setup, so it
  cannot be a stub with just filament colours: a partial file replaces the
  user's printer settings with defaults. It is therefore only written from a
  template, a project the user saved in Bambu Studio for their own printer,
  with only ``filament_colour`` changed (a project-level option, which Bambu
  applies without ``different_settings_to_system``).

Format reference: Bambu Studio's own reader and writer,
src/libslic3r/Format/bbs_3mf.cpp, and how the GUI applies a project's
config, src/slic3r/GUI/Plater.cpp and src/libslic3r/PresetBundle.cpp.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

MODEL_SETTINGS_PATH = "Metadata/model_settings.config"
PROJECT_SETTINGS_PATH = "Metadata/project_settings.config"
NAMESPACE = "http://schemas.bambulab.com/package/2021"
DEFAULT_PLATE_CENTRE = (128.0, 128.0)  # 256 x 256 mm bed: X1, P1 and A1 series

_IDENTITY = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"
_APPLICATION = re.compile(r'<metadata\s+name="Application"\s*>([^<]*)</metadata>')


@dataclass(frozen=True)
class BambuProject:
    """Settings taken from a project saved by Bambu Studio, used as a template."""

    application: str  # e.g. "BambuStudio-02.04.00.70", marks the file as a Bambu project
    settings: dict  # the template's project_settings.config

    @property
    def filament_count(self) -> int:
        return len(self.settings.get("filament_colour", []))

    @property
    def plate_centre(self) -> tuple[float, float]:
        """Centre of the printable area, from the template's printer settings."""
        corners = self.settings.get("printable_area")
        try:
            points = [tuple(float(v) for v in c.split("x")) for c in corners]
        except (TypeError, ValueError, AttributeError):
            return DEFAULT_PLATE_CENTRE
        if not points:
            return DEFAULT_PLATE_CENTRE
        xs, ys = zip(*points)
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    def with_colours(self, colours: list[tuple[int, int, int]]) -> dict:
        """The template's settings with filament slots 1..N set to ``colours``."""
        if len(colours) > self.filament_count:
            raise ValueError(
                f"the template has {self.filament_count} filament(s) but the image needs "
                f"{len(colours)}: add filaments in Bambu Studio and save the template again"
            )
        settings = json.loads(json.dumps(self.settings))  # deep copy
        for key in ("filament_colour", "filament_multi_colour"):
            values = settings.get(key)
            if not isinstance(values, list) or len(values) != self.filament_count:
                continue
            for i, colour in enumerate(colours):
                values[i] = _hex_like(values[i], colour)
        return settings


def load_bambu_project(path: str | Path) -> BambuProject:
    """Read the template settings from a project 3MF saved by Bambu Studio."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if PROJECT_SETTINGS_PATH not in names or "3D/3dmodel.model" not in names:
                raise ValueError(f"{path.name} is not a Bambu Studio project: no project settings")
            settings = json.loads(zf.read(PROJECT_SETTINGS_PATH))
            model = zf.read("3D/3dmodel.model").decode("utf-8", errors="replace")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path.name} is not a 3MF file") from exc

    match = _APPLICATION.search(model)
    application = match.group(1).strip() if match else ""
    if not application.startswith("BambuStudio-"):
        raise ValueError(
            f"{path.name} was not saved by Bambu Studio (Application: {application or 'missing'})"
        )
    if not settings.get("filament_colour"):
        raise ValueError(f"{path.name} has no filament colours in its project settings")
    return BambuProject(application=application, settings=settings)


def model_settings_xml(object_id: int, object_name: str, parts: list[tuple[int, str, int]]) -> str:
    """Per-object and per-part settings, as Bambu Studio writes them.

    :param object_id: Id of the parent object in the 3D model.
    :param parts: ``(mesh object id, name, triangle count)`` for each part, in
        filament order: part ``i`` is printed with filament ``i + 1``.
    """
    total = sum(count for _, _, count in parts)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<config>",
        f'  <object id="{object_id}">',
        f'    <metadata key="name" value={quoteattr(object_name)}/>',
        '    <metadata key="extruder" value="1"/>',
        f'    <metadata face_count="{total}"/>',
    ]
    for slot, (part_id, name, count) in enumerate(parts, start=1):
        out += [
            f'    <part id="{part_id}" subtype="normal_part">',
            f'      <metadata key="name" value={quoteattr(name)}/>',
            f'      <metadata key="matrix" value="{_IDENTITY}"/>',
            f'      <metadata key="extruder" value="{slot}"/>',
            f'      <mesh_stat face_count="{count}" edges_fixed="0" degenerate_facets="0"'
            ' facets_removed="0" facets_reversed="0" backwards_edges="0"/>',
            "    </part>",
        ]
    out += ["  </object>", "</config>"]
    return "\n".join(out) + "\n"


def project_settings_json(settings: dict) -> str:
    return json.dumps(settings, indent=4) + "\n"


def _hex_like(template: str, colour: tuple[int, int, int]) -> str:
    """Format ``colour`` like the template value: "#RRGGBB" or "#RRGGBBAA"."""
    hex6 = "#{:02X}{:02X}{:02X}".format(*colour)
    if isinstance(template, str) and len(template) == 9:
        return hex6 + "FF"
    return hex6
