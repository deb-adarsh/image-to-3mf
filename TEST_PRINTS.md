# Test prints (milestone 5)

Four small prints, one per sample image, each with at most four filaments so a
single AMS is enough. Build them with:

```bash
uv run python samples/make_test_prints.py
```

or, to open them as ready-to-print Bambu Studio projects (see the README):

```bash
uv run python samples/make_test_prints.py --bambu-project ~/path/to/template.3mf
```

The files land in `out/test-prints/` (not committed).

## The prints

| File | Source | Settings | Size | Filaments | What it tests |
|---|---|---|---|---|---|
| `1-logo.3mf` | `logo_bw.png` | raised, 2 mm margin, text "image-to-3mf" 6 mm | 56 x 65 x 2.5 mm | white plate, black | Basic two-colour raised print, letter counters, small text with dots and hyphens, a plate that joins artwork and text |
| `2-apple-inlay.3mf` | `apple.png` (transparent) | inlay, 2 mm plate, 1.5 mm margin | 51 x 53 x 2 mm | red, green, brown, white | Four colours set flush into the plate, colours touching each other, the plate taking the largest colour |
| `3-diagram.3mf` | `diagram.png` | raised | 48 x 44 x 2.5 mm | white plate, blue | Strokes 0.12-0.35 mm wide in the image, widened to the 0.8 mm minimum feature |
| `4-cartoon.3mf` | `cartoon.png` | raised | 66 x 54 x 2.5 mm | white plate, orange, dark, pink | Stress test: outlines between colours, 1 px whiskers, 0.5 mm eye highlights, a small nose |

Colours stand 1 mm on a 1.5 mm plate (raised) or sit 0.6 mm deep (inlay): at
0.2 mm layers, that is 5 and 3 colour layers.

## What to check

For every print, in this order:

1. **Opens right.** Bambu Studio (or OrcaSlicer) shows one object made of one
   part per colour, with each part on its own filament and no repair or
   "non-manifold" warning.
   - Without `--bambu-project`: note whether parts keep filaments 1..N or
     Bambu opens a colour-mapping dialog, and whether any warning appears.
   - With `--bambu-project`: printer, process and filaments are your
     template's, and filament colours match the image.
2. **Slices cleanly.** No warnings while slicing; the preview shows every colour
   region, including the thin ones.
3. **Prints and resembles the source.** Compare with the sample image.

Things worth looking at closely:

- `1-logo`: are the "3MF" counters and the dot on the "i" clean? Is the 6 mm
  text legible?
- `2-apple-inlay`: is the top flat, with no gaps or ridges between colours? Did
  the white highlight and the thin brown stem come out?
- `3-diagram`: are the 0.8 mm lines continuous, with clean corners and junctions?
- `4-cartoon`: do the whiskers read as whiskers at 0.8 mm? Did the eye
  highlights (0.5 mm holes showing the white plate) survive, or fill in? Any
  colour bleeding between the outline and the orange?

## Known limits going in

- Anything thinner than `--min-feature` (0.8 mm) is widened to it, so the
  whiskers and diagram lines come out bolder than in the images.
- Holes smaller than about 0.5 mm (the cat's eye highlights) are kept in the
  model but may close up when printed.
- When the artwork falls apart into separate pieces (the logo and its text), the
  plate becomes their convex hull, so plate shows around them.
- Nobody has opened these files in Bambu Studio yet (milestone 3 is unverified).

## Results

Fill in one row per print, and note anything to fix in the last column.

| File | Date | Printer / nozzle | Opens right? | Slices cleanly? | Resembles source? | Issues |
|---|---|---|---|---|---|---|
| `1-logo.3mf` | | | | | | |
| `2-apple-inlay.3mf` | | | | | | |
| `3-diagram.3mf` | | | | | | |
| `4-cartoon.3mf` | | | | | | |
