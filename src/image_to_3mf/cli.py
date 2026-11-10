"""Command-line entry point: image in, multi-colour 3MF (or single-colour STL) out."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from image_to_3mf.compose import remove_specks, scale_to_mm
from image_to_3mf.export_3mf import Part, write_3mf
from image_to_3mf.export_stl import write_stl
from image_to_3mf.extrude import extrude_layers, to_mesh
from image_to_3mf.quantize import MAX_COLORS, load_image, quantize
from image_to_3mf.trace import MAX_SMOOTH, trace_layers

FORMATS = (".3mf", ".stl")


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
        "--width", type=float, default=80.0, help="output width in mm (default: 80)"
    )
    parser.add_argument(
        "--colors",
        type=int,
        help=f"number of colours, not counting the background (default: detect, up to {MAX_COLORS})",
    )
    parser.add_argument(
        "--depths",
        type=float,
        nargs="+",
        default=[2.0],
        help="depth in mm per colour, largest colour first; the last value repeats (default: 2)",
    )
    parser.add_argument(
        "--smooth",
        type=float,
        default=1.0,
        help=f"tracing smoothness, 0 (sharp) to {MAX_SMOOTH} (default: 1.0)",
    )
    return parser


def run(args: argparse.Namespace) -> Path:
    output = args.output or Path("out") / f"{args.input.stem}.3mf"
    if output.suffix.lower() not in FORMATS:
        raise ValueError(f"output must end in {' or '.join(FORMATS)}, got {output.name}")
    if any(d <= 0 for d in args.depths):
        raise ValueError("depths must be positive")

    rgba = load_image(args.input)
    height_px, width_px = rgba.shape[:2]
    colours = quantize(rgba, args.colors)
    layers_px = trace_layers([c.mask for c in colours], smooth=args.smooth)
    layers = remove_specks([scale_to_mm(g, width_px, height_px, args.width) for g in layers_px])

    kept = [(c, g) for c, g in zip(colours, layers) if not g.is_empty]
    if not kept:
        raise ValueError("nothing left to print after removing specks")
    colours = [c for c, _ in kept]
    layers = [g for _, g in kept]
    depths = [args.depths[min(i, len(args.depths) - 1)] for i in range(len(layers))]

    bodies = extrude_layers(layers, depths)
    meshes = [to_mesh(b) for b in bodies]
    if output.suffix.lower() == ".stl":
        write_stl(output, meshes)
    else:
        parts = [
            Part(name=f"Colour {i + 1} {c.hex}", color=c.color, mesh=m)
            for i, (c, m) in enumerate(zip(colours, meshes))
        ]
        write_3mf(output, parts, name=args.input.stem)

    boxes = np.array([b.bounding_box() for b in bodies])
    size = boxes[:, 3:].max(axis=0) - boxes[:, :3].min(axis=0)
    print(
        f"{args.input.name} -> {output}: {len(bodies)} colour(s), "
        f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm"
    )
    for i, (c, g, d) in enumerate(zip(colours, layers, depths)):
        print(f"  {i + 1}. {c.hex}  depth {d:g} mm  {len(g.geoms)} part(s)  {g.area:.1f} mm2")
    return output


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
