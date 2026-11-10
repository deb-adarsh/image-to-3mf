# image-to-3mf

Convert flat artwork (logos, icons, clip art, simple diagrams) into a multi-colour,
print-ready 3MF that opens in Bambu Studio / OrcaSlicer with filaments already assigned.

This is a proof of concept. See [CLAUDE.md](CLAUDE.md) for the full plan, pipeline and milestones.

## Status

| Milestone | State |
|---|---|
| 1. Single colour: black-and-white logo → extruded STL | Done |
| 2. Multi-colour geometry: N colours → N watertight bodies in a core-spec 3MF | Done |
| 3. Bambu-ready: filaments pre-assigned in Bambu Studio | Built, not yet checked in Bambu Studio |
| 4. Polish: backing plate, margin, min-feature cleanup, text | Next |
| 5. Test prints | |

## Usage

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run image-to-3mf samples/apple.png --width 80 --depths 2 3
```

This writes `out/apple.3mf`: one object made of one part per colour, each part a
separate watertight body with its own display colour. Use `-o name.stl` for a
single-colour STL instead.

| Option | Meaning | Default |
|---|---|---|
| `--width` | Output width in mm (height follows the aspect ratio) | 80 |
| `--colors` | Number of colours, not counting the background | detected (up to 6) |
| `--depths` | Depth in mm per colour, largest colour first; the last value repeats | 2 |
| `--smooth` | Tracing smoothness, 0 (sharp corners) to 1.334 | 1.0 |
| `-o`, `--output` | Output path, `.3mf` or `.stl` | `out/<input>.3mf` |
| `--bambu-project` | A project 3MF saved by Bambu Studio to use as a template (see below) | none |

### Bambu Studio and OrcaSlicer

Every 3MF carries `Metadata/model_settings.config`, which gives colour 1 filament 1,
colour 2 filament 2, and so on (largest colour first), and places the object in the
middle of a 256 mm plate.

Filament colours and types live in `Metadata/project_settings.config`. Bambu Studio
loads that file as the project's complete printer, process and filament setup, so a
file holding only filament colours would replace your printer settings with defaults.
To get a ready-to-print project instead:

1. In Bambu Studio, select your printer and load at least as many filaments as the
   image has colours (for example, sync your AMS). Add any object (a cube will do;
   only the settings are used) and save the project as your template.
2. Pass it with `--bambu-project template.3mf`.

The output then reuses the template's printer, process and filament settings, sets
filament colours 1..N to the image colours, and centres the object on that printer's
plate. Filament types stay as they are in the template.

How the image is read:

- The background is the transparent area if transparency fills most of the image
  border, otherwise the colour that fills most of the border. It is not printed.
  Until the backing plate arrives (milestone 4), areas of the background colour
  inside the artwork become holes.
- Colours are listed and stacked largest area first. Where colour bodies would
  touch or overlap, the later colour wins, so no two bodies share any volume.
- The whole image is scaled to `--width`, so blank margins around the artwork are kept.

## Development

```bash
uv run pytest                            # tests
uv run python samples/make_samples.py    # regenerate sample images
```

Each pipeline stage is a separate module under `src/image_to_3mf/` with a pure
function interface: `quantize` → `trace` → `compose` → `extrude` → `export_3mf`
(or `export_stl`). Tests validate 3MF output with lib3mf in strict mode.
