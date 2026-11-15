"""Command-line entry point: image in, multi-colour 3MF (or single-colour STL) out."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from image_to_3mf.bambu import load_bambu_project
from image_to_3mf.compose import (
    MIN_FEATURE,
    add_to_layer,
    backing_plate,
    place_below,
    remove_specks,
    scale_to_mm,
    thicken,
)
from image_to_3mf.export_3mf import Part, write_3mf
from image_to_3mf.export_stl import write_stl
from image_to_3mf.extrude import extrude_layers, to_mesh, union
from image_to_3mf.quantize import MAX_COLORS, load_image, quantize
from image_to_3mf.text import render_text
from image_to_3mf.trace import MAX_SMOOTH, trace_layers

FORMATS = (".3mf", ".stl")
STYLES = ("raised", "inlay")
DEFAULT_DEPTH = {"raised": 1.0, "inlay": 0.6}  # mm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-to-3mf",
        description="Convert flat artwork into a multi-colour, print-ready 3MF.",
    )
    parser.add_argument("input", type=Path, help="input image (PNG, JPEG, ...)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output .3mf, or .stl for a single-colour mesh (default: out/<input name>.3mf)",
    )
    parser.add_argument(
        "--width", type=float, default=80.0, help="width of the image in mm (default: 80)"
    )
    parser.add_argument(
        "--colors",
        type=int,
        help=f"number of colours, not counting the background (default: detect, up to {MAX_COLORS})",
    )
    parser.add_argument(
        "--style",
        choices=STYLES,
        default="raised",
        help="raised: colours stand on the plate; inlay: colours are set into the plate, "
        "flush with its top (default: raised)",
    )
    parser.add_argument(
        "--depths",
        type=float,
        nargs="+",
        help="colour depth in mm, largest colour first; the last value repeats "
        f"(default: {DEFAULT_DEPTH['raised']:g} raised, {DEFAULT_DEPTH['inlay']:g} inlay)",
    )
    parser.add_argument(
        "--base",
        type=float,
        default=1.5,
        help="backing plate thickness in mm, 0 for none (default: 1.5)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.0,
        help="border of backing plate around the artwork in mm (default: 0)",
    )
    parser.add_argument(
        "--min-feature",
        type=float,
        default=MIN_FEATURE,
        help=f"thinnest printable feature in mm; thinner strokes are widened (default: {MIN_FEATURE})",
    )
    parser.add_argument(
        "--smooth",
        type=float,
        default=1.0,
        help=f"tracing smoothness, 0 (sharp) to {MAX_SMOOTH} (default: 1.0)",
    )
    parser.add_argument("--text", help="a line of text to set below the artwork")
    parser.add_argument("--font", type=Path, help="TrueType/OpenType font file for --text")
    parser.add_argument(
        "--text-size", type=float, default=8.0, help="text size in mm (default: 8)"
    )
    parser.add_argument(
        "--bambu-project",
        type=Path,
        metavar="TEMPLATE.3mf",
        help="a project saved by Bambu Studio for your printer, with at least as many filaments "
        "as colours: the output reuses its printer, process and filament settings, with the "
        "filament colours set from the image",
    )
    return parser


def run(args: argparse.Namespace) -> Path:
    output = args.output or Path("out") / f"{args.input.stem}.3mf"
    _check_args(args, output)
    project = load_bambu_project(args.bambu_project) if args.bambu_project else None

    # Stages 1-2: colours and outlines.
    rgba = load_image(args.input)
    height_px, width_px = rgba.shape[:2]
    palette = quantize(rgba, args.colors)
    layers_px = trace_layers([c.mask for c in palette], smooth=args.smooth)

    # Stage 3: physical size, text, printability.
    layers = [scale_to_mm(g, width_px, height_px, args.width) for g in layers_px]
    colours = [c.color for c in palette]
    base_colour = palette.background or colours[0]
    text_layer = None
    if args.text:
        text = render_text(args.text, args.text_size, args.font)
        text_layer = _most_contrasting(colours, base_colour)
        layers = add_to_layer(layers, text_layer, place_below(text, layers, args.text_size / 2))
    layers = remove_specks(layers, args.min_feature)
    layers = remove_specks(thicken(layers, args.min_feature), args.min_feature)

    kept = [i for i, g in enumerate(layers) if not g.is_empty]
    if not kept:
        raise ValueError("nothing left to print after removing specks")
    layers = [layers[i] for i in kept]
    colours = [colours[i] for i in kept]
    depth_list = args.depths or [DEFAULT_DEPTH[args.style]]
    depths = [depth_list[min(i, len(depth_list) - 1)] for i in range(len(layers))]
    if args.style == "inlay" and max(depths) > args.base:
        raise ValueError(f"inlay depth {max(depths):g} mm is deeper than the {args.base:g} mm plate")

    # Stage 4: solids. The plate goes first, so colours sit on it or are cut into it.
    names = [f"Colour {i + 1} {_hex(c)}" for i, c in enumerate(colours)]
    if args.base > 0:
        plate = backing_plate(layers, args.margin)
        tops = [args.base] * len(layers) if args.style == "raised" else [args.base - d for d in depths]
        bodies = extrude_layers([plate] + layers, [args.base] + depths, [0.0] + tops)
        colours = [base_colour] + colours
        names = [f"Base {_hex(base_colour)}"] + names
    else:
        bodies = extrude_layers(layers, depths)

    # Stage 5: export. Parts of the same colour share a filament.
    slot_of: dict[tuple[int, int, int], int] = {}
    for c in colours:
        slot_of.setdefault(c, len(slot_of) + 1)
    meshes = [to_mesh(b) for b in bodies]
    if output.suffix.lower() == ".stl":
        write_stl(output, to_mesh(union(bodies)))
    else:
        parts = [
            Part(name=n, color=c, mesh=m, filament=slot_of[c])
            for n, c, m in zip(names, colours, meshes)
        ]
        write_3mf(output, parts, name=args.input.stem, project=project)

    _report(args, output, bodies, layers, colours, depths, slot_of, text_layer, project)
    return output


def _check_args(args: argparse.Namespace, output: Path) -> None:
    if output.suffix.lower() not in FORMATS:
        raise ValueError(f"output must end in {' or '.join(FORMATS)}, got {output.name}")
    if args.depths and any(d <= 0 for d in args.depths):
        raise ValueError("depths must be positive")
    if args.base < 0 or args.margin < 0 or args.min_feature < 0:
        raise ValueError("--base, --margin and --min-feature must not be negative")
    if args.style == "inlay" and args.base <= 0:
        raise ValueError("inlay style needs a backing plate: set --base above 0")
    if args.bambu_project and output.suffix.lower() != ".3mf":
        raise ValueError("--bambu-project needs a .3mf output")


def _most_contrasting(colours, against) -> int:
    """Index of the colour whose brightness differs most from ``against``."""

    def luma(c):
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    return max(range(len(colours)), key=lambda i: abs(luma(colours[i]) - luma(against)))


def _hex(colour) -> str:
    return "#{:02X}{:02X}{:02X}".format(*colour)


def _report(args, output, bodies, layers, colours, depths, slot_of, text_layer, project) -> None:
    boxes = np.array([b.bounding_box() for b in bodies])
    size = boxes[:, 3:].max(axis=0) - boxes[:, :3].min(axis=0)
    print(
        f"{args.input.name} -> {output}: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm, "
        f"{args.style}, {len(slot_of)} filament(s)"
    )
    if project:
        print(f"  Bambu Studio project: settings from {args.bambu_project.name}")
    artwork = colours
    if args.base > 0:
        base_colour, artwork = colours[0], colours[1:]
        print(f"  base plate: filament {slot_of[base_colour]} {_hex(base_colour)}  {args.base:g} mm")
    for i, (c, g, d) in enumerate(zip(artwork, layers, depths)):
        print(
            f"  filament {slot_of[c]}: {_hex(c)}  depth {d:g} mm  "
            f"{len(g.geoms)} part(s)  {g.area:.1f} mm2"
        )
    if text_layer is not None:
        print(f"  text in {_hex(artwork[text_layer]) if text_layer < len(artwork) else 'removed colour'}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
