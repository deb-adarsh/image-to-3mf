# image-to-3mf

Convert flat artwork (logos, icons, clip art, simple diagrams) into a multi-colour,
print-ready 3MF that opens in Bambu Studio / OrcaSlicer with filaments already assigned.

This is a proof of concept. See [CLAUDE.md](CLAUDE.md) for the full plan, pipeline and milestones.

## Status

| Milestone | State |
|---|---|
| 1. Single colour: black-and-white logo → extruded STL | Done |
| 2. Multi-colour geometry: N colours → N watertight bodies in a core-spec 3MF | Next |
| 3. Bambu-ready: filaments pre-assigned in Bambu Studio | |
| 4. Polish: backing plate, margin, min-feature cleanup, text | |
| 5. Test prints | |

## Usage

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run image-to-3mf samples/logo_bw.png --width 80 --depths 2
```

This writes `out/logo_bw.stl`. The whole image is scaled to `--width`, so blank
margins around the artwork are kept.

| Option | Meaning | Default |
|---|---|---|
| `--width` | Output width in mm (height follows the aspect ratio) | 80 |
| `--depths` | Layer depth in mm (milestone 1 uses the first value) | 2 |
| `--smooth` | Tracing smoothness, 0 (sharp corners) to 1.334 | 1.0 |
| `-o`, `--output` | Output path | `out/<input>.stl` |

## Development

```bash
uv run pytest                            # tests
uv run python samples/make_samples.py    # regenerate sample images
```

Each pipeline stage is a separate module under `src/image_to_3mf/` with a pure
function interface: `quantize` → `trace` → `compose` → `extrude` → `export_*`.
