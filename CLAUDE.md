# image-to-3mf — POC

Convert flat artwork (logos, icons, clip art, simple diagrams) into a multi-colour,
print-ready 3MF that opens in Bambu Studio with filaments already assigned,
slices without repair warnings, and prints.

## Scope

In scope: flat images with 2–6 colours, Python CLI, Bambu Studio / OrcaSlicer output.

Out of scope for the POC: photos and lithophanes, AI image-to-3D, web UI,
node editor, catalog, accounts, slicing.

## Pipeline

| Stage | Responsibility | Libraries | Output |
|---|---|---|---|
| 1. Load & quantize | Remove background, reduce to N colours, drop anti-aliasing noise | Pillow, OpenCV, numpy, scikit-learn (k-means) | One binary mask per colour |
| 2. Trace | Mask → smooth vector outlines with holes | potrace (`potracer` pure-Python, or `pypotrace`) | Polygons per colour |
| 3. Clean & compose | Remove specks, enforce min feature width, backing plate (outward offset of the union), optional text | Shapely or pyclipper (Clipper2) | Final 2D layers |
| 4. Extrude & boolean | Per-layer height, stack layers, no overlaps between colour bodies | manifold3d | One watertight solid per colour |
| 5. Export | Core 3MF + Bambu config files | lib3mf, or zipfile + XML | `.3mf` |

Keep each stage a separate module with a pure function interface so stages can be
tested and swapped independently.

## Suggested layout

```
src/image_to_3mf/
  quantize.py    # stage 1
  trace.py       # stage 2
  compose.py     # stage 3
  extrude.py     # stage 4
  export_3mf.py  # stage 5
  cli.py         # entry point
tests/
samples/         # test images
out/             # generated files (gitignored)
```

## CLI parameters

- `--width` output width in mm (height follows aspect ratio)
- `--colors` number of colours (auto-detect, overridable)
- `--depths` per-colour layer depth in mm
- `--base` base plate thickness in mm, `--margin` outline margin in mm
- `--min-feature` minimum feature width in mm (default 0.8, about 2 nozzle widths)
- `--smooth` tracing smoothness
- `--style raised|inlay` raised details vs flush inlays
- `--text`, `--font`, `--text-size` optional text line (milestone 4)

## 3MF requirements (stage 5)

Core spec, readable by any 3MF tool:
- One `<object>` per colour body, vertices deduplicated per part (do not weld parts together).
- A parent object using `<components>` so the parts load as one object.
- `<basematerials>` with a display colour per part, as a fallback.

Bambu Studio / OrcaSlicer extensions, needed for filaments to be pre-assigned:
- `Metadata/model_settings.config` (XML): each part with `<metadata key="extruder" value="N"/>` (1-based).
- `Metadata/project_settings.config` (JSON despite the extension): `filament_colour` and
  `filament_type` arrays indexed by filament slot.
- Setting changes in project_settings may be ignored unless also listed in
  `different_settings_to_system`.

Validate against a file Bambu Studio saves itself: build a simple two-part, two-colour
object in Bambu Studio, save it, unzip it, and diff our output against it.

Useful references: CNCKitchen/stlTexturizer PR #111 (multi-part 3MF writer),
printago.io blog post on Bambu/Orca 3MF structure, aprilcube (pip) for a working generator.

## Milestones

1. **Single colour** — black and white logo → extruded STL. Proves trace and extrude.
2. **Multi-colour geometry** — N-colour image → N separate watertight bodies in a core-spec 3MF.
3. **Bambu-ready** — file opens in Bambu Studio as one object with N parts, filaments pre-assigned.
4. **Polish** — backing plate, outline margin, min-feature cleanup, optional text.
5. **Test prints** — print 3–4 samples and fix what fails.

## Definition of done (per sample image)

- Every colour body is watertight (`trimesh` `is_watertight`, or manifold3d status OK).
- Bambu Studio loads it with the correct number of filaments and colours.
- It slices without repair warnings.
- The print resembles the source image.

## Test images

1. Simple two-colour logo
2. Multi-colour clip-art icon (e.g. a fruit with leaves)
3. Line diagram with thin strokes (tests min-feature thickening)
4. Cartoon with small details (deliberate stress test)

## Known risks

- Anti-aliased edges create false in-between colours → quantize in stage 1, drop specks in stage 3.
- Thin strokes disappear or print badly → thicken to `--min-feature` with an offset close/open.
- Bambu config format is community-documented, not official → validate against Bambu-saved files.
- Overlapping colour bodies confuse slicers → boolean-subtract upper layers from lower ones in stage 4.

## Working conventions

- Python 3.11+, `pyproject.toml`, `uv` for environments.
- `pytest` for tests; each stage gets unit tests on tiny synthetic images.
- Do not commit generated files in `out/`.
- Build one milestone at a time and confirm it works before starting the next.
