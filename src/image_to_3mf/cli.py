"""Command-line entry point.

Milestone 1: a black-and-white image becomes a single extruded STL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from image_to_3mf.compose import scale_to_mm
from image_to_3mf.extrude import extrude, to_mesh
from image_to_3mf.export_stl import write_stl
from image_to_3mf.quantize import binarize, load_image
from image_to_3mf.trace import MAX_SMOOTH, trace_mask


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-to-3mf",
        description="Convert flat artwork into a print-ready 3D model.",
    )
    parser.add_argument("input", type=Path, help="input image (PNG, JPEG, ...)")
    parser.add_argument(
        "-o", "--output", type=Path, help="output file (default: out/<input name>.stl)"
    )
    parser.add_argument(
        "--width", type=float, default=80.0, help="output width in mm (default: 80)"
    )
    parser.add_argument(
        "--depths",
        type=float,
        nargs="+",
        default=[2.0],
        help="layer depth in mm per colour (default: 2)",
    )
    parser.add_argument(
        "--smooth",
        type=float,
        default=1.0,
        help=f"tracing smoothness, 0 (sharp) to {MAX_SMOOTH} (default: 1.0)",
    )
    return parser


def run(args: argparse.Namespace) -> Path:
    output = args.output or Path("out") / f"{args.input.stem}.stl"

    rgba = load_image(args.input)
    height_px, width_px = rgba.shape[:2]
    layer = binarize(rgba)
    outline_px = trace_mask(layer.mask, smooth=args.smooth)
    outline_mm = scale_to_mm(outline_px, width_px, height_px, args.width)
    solid = extrude(outline_mm, height=args.depths[0])
    write_stl(output, to_mesh(solid))

    (xmin, ymin, zmin), (xmax, ymax, zmax) = _bounds(solid)
    print(
        f"{args.input.name}: {len(outline_mm.geoms)} part(s), "
        f"{xmax - xmin:.1f} x {ymax - ymin:.1f} x {zmax - zmin:.1f} mm, "
        f"{solid.num_tri()} triangles -> {output}"
    )
    return output


def _bounds(solid):
    box = solid.bounding_box()
    return box[:3], box[3:]


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
