"""Build the milestone 5 test-print files from the sample images.

Run with: uv run python samples/make_test_prints.py [--bambu-project TEMPLATE.3mf]

Writes one 3MF per sample to test-prints/. See TEST_PRINTS.md for what
each print tests and what to check.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from image_to_3mf.cli import main as convert

HERE = Path(__file__).parent
OUT = HERE.parent / "test-prints"

# (output name, sample, options): small prints, at most four filaments each.
PRINTS = [
    ("1-logo", "logo_bw.png", ["--width", "60", "--margin", "2", "--text", "image-to-3mf", "--text-size", "6"]),
    ("2-apple-inlay", "apple.png", ["--width", "60", "--style", "inlay", "--base", "2", "--margin", "1.5"]),
    ("3-diagram", "diagram.png", ["--width", "60"]),
    ("4-cartoon", "cartoon.png", ["--width", "70"]),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bambu-project",
        type=Path,
        help="project saved by Bambu Studio with at least four filaments (see README)",
    )
    args = parser.parse_args()

    extra = ["--bambu-project", str(args.bambu_project)] if args.bambu_project else []
    failed = []
    for name, sample, options in PRINTS:
        output = OUT / f"{name}.3mf"
        if convert([str(HERE / sample), "-o", str(output), *options, *extra]) != 0:
            failed.append(name)
        print()
    if failed:
        print(f"failed: {', '.join(failed)}")
        return 1
    print(f"wrote {len(PRINTS)} test prints to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
