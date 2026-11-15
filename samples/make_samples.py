"""Generate the sample test images, so samples stay reproducible and license-free.

Run with: uv run python samples/make_samples.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SUPERSAMPLE = 4  # draw large, then downsample for realistic anti-aliased edges


def logo_bw(size: int = 512) -> Image.Image:
    """Sample 1: a two-colour badge (ring, star and text) on a white background."""
    s = size * SUPERSAMPLE
    im = Image.new("RGB", (s, s), "white")
    d = ImageDraw.Draw(im)
    ink = (20, 20, 20)

    # Outer ring.
    m = s // 16
    d.ellipse([m, m, s - m, s - m], outline=ink, width=s // 20)

    # Five-pointed star in the upper half.
    cx, cy, r_out, r_in = s / 2, s * 0.38, s * 0.2, s * 0.08
    star = [
        (
            cx + (r_out if i % 2 == 0 else r_in) * math.sin(i * math.pi / 5),
            cy - (r_out if i % 2 == 0 else r_in) * math.cos(i * math.pi / 5),
        )
        for i in range(10)
    ]
    d.polygon(star, fill=ink)

    # Text with counters (holes) in the letters.
    font = ImageFont.load_default(size=s // 7)
    d.text((s / 2, s * 0.72), "3MF", font=font, fill=ink, anchor="mm")

    return im.resize((size, size), Image.Resampling.LANCZOS)


def apple(size: int = 512) -> Image.Image:
    """Sample 2: a four-colour apple (body, highlight, stem, leaf) on a transparent background."""
    s = size * SUPERSAMPLE
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    red, white, brown, green = (200, 30, 40), (250, 250, 250), (110, 70, 30), (60, 160, 60)

    # Body: two overlapping lobes.
    d.ellipse([0.10 * s, 0.26 * s, 0.58 * s, 0.92 * s], fill=red)
    d.ellipse([0.42 * s, 0.26 * s, 0.90 * s, 0.92 * s], fill=red)
    # Highlight.
    d.ellipse([0.22 * s, 0.38 * s, 0.32 * s, 0.56 * s], fill=white)
    # Stem, slightly tilted, sitting in the top of the body.
    d.polygon([(0.46 * s, 0.38 * s), (0.52 * s, 0.38 * s), (0.58 * s, 0.10 * s), (0.53 * s, 0.09 * s)], fill=brown)
    # Leaf: a rotated ellipse touching the stem and the body.
    cx, cy, rx, ry, angle = 0.66 * s, 0.22 * s, 0.15 * s, 0.065 * s, math.radians(-30)
    leaf = [
        (
            cx + rx * math.cos(t) * math.cos(angle) - ry * math.sin(t) * math.sin(angle),
            cy + rx * math.cos(t) * math.sin(angle) + ry * math.sin(t) * math.cos(angle),
        )
        for t in (2 * math.pi * i / 180 for i in range(180))
    ]
    d.polygon(leaf, fill=green)

    return im.resize((size, size), Image.Resampling.LANCZOS)


def diagram(size: int = 512) -> Image.Image:
    """Sample 3: a two-colour line diagram with strokes 1-3 px wide, on white.

    At the default 80 mm width a pixel is 0.16 mm, so every stroke here is
    thinner than the 0.8 mm minimum feature and has to be thickened.
    """
    s = size * SUPERSAMPLE
    im = Image.new("RGB", (s, s), "white")
    d = ImageDraw.Draw(im)
    blue = (30, 60, 160)
    px = SUPERSAMPLE  # one output pixel

    # Three boxes with 2 px outlines.
    boxes = [(0.10, 0.12), (0.60, 0.12), (0.35, 0.62)]
    w, h = 0.28 * s, 0.22 * s
    for bx, by in boxes:
        d.rectangle([bx * s, by * s, bx * s + w, by * s + h], outline=blue, width=2 * px)
    # Connectors, 1 px wide.
    d.line([(0.38 * s, 0.23 * s), (0.60 * s, 0.23 * s)], fill=blue, width=px)
    d.line([(0.24 * s, 0.34 * s), (0.42 * s, 0.62 * s)], fill=blue, width=px)
    d.line([(0.74 * s, 0.34 * s), (0.56 * s, 0.62 * s)], fill=blue, width=px)
    # A 3 px ring in the middle box.
    cx, cy, r = 0.49 * s, 0.73 * s, 0.06 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=blue, width=3 * px)

    return im.resize((size, size), Image.Resampling.LANCZOS)


def cartoon(size: int = 512) -> Image.Image:
    """Sample 4: a cartoon cat with small details, on white (deliberate stress test).

    Outlines between colours, 1 px whiskers, 2 px eye highlights in the
    background colour, and a nose a few pixels across. Orange, dark and pink
    on white: four filaments with the white plate.
    """
    s = size * SUPERSAMPLE
    im = Image.new("RGB", (s, s), "white")
    d = ImageDraw.Draw(im)
    orange, dark, pink = (235, 135, 40), (45, 35, 35), (240, 150, 170)
    px = SUPERSAMPLE
    outline = 4 * px

    # Ears, drawn first so the head covers their bases.
    for side in (-1, 1):
        tip = (0.5 * s + side * 0.27 * s, 0.10 * s)
        base = [(0.5 * s + side * 0.08 * s, 0.32 * s), (0.5 * s + side * 0.38 * s, 0.38 * s)]
        d.polygon([tip, *base], fill=orange, outline=dark, width=outline)
        inner_tip = (0.5 * s + side * 0.255 * s, 0.17 * s)
        inner = [(0.5 * s + side * 0.15 * s, 0.33 * s), (0.5 * s + side * 0.32 * s, 0.36 * s)]
        d.polygon([inner_tip, *inner], fill=pink)

    # Head and muzzle.
    d.ellipse([0.14 * s, 0.24 * s, 0.86 * s, 0.86 * s], fill=orange, outline=dark, width=outline)
    for side in (-1, 1):
        cx = 0.5 * s + side * 0.07 * s
        d.ellipse([cx - 0.10 * s, 0.58 * s, cx + 0.10 * s, 0.74 * s], fill="white")

    # Eyes with tiny highlights.
    for side in (-1, 1):
        cx = 0.5 * s + side * 0.15 * s
        d.ellipse([cx - 0.055 * s, 0.42 * s, cx + 0.055 * s, 0.55 * s], fill=dark)
        hx, hy = cx + side * 0.015 * s - 0.015 * s, 0.45 * s
        d.ellipse([hx - 2 * px, hy - 2 * px, hx + 2 * px, hy + 2 * px], fill="white")

    # Nose and mouth.
    d.polygon([(0.465 * s, 0.585 * s), (0.535 * s, 0.585 * s), (0.5 * s, 0.625 * s)], fill=pink)
    d.arc([0.42 * s, 0.58 * s, 0.50 * s, 0.68 * s], 20, 160, fill=dark, width=2 * px)
    d.arc([0.50 * s, 0.58 * s, 0.58 * s, 0.68 * s], 20, 160, fill=dark, width=2 * px)

    # Whiskers, 1 px, reaching past the head.
    for side in (-1, 1):
        for dy in (-0.03, 0.0, 0.03):
            start = (0.5 * s + side * 0.17 * s, 0.65 * s + dy * s)
            end = (0.5 * s + side * 0.47 * s, 0.62 * s + 2 * dy * s)
            d.line([start, end], fill=dark, width=px)

    return im.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    samples = [
        ("logo_bw.png", logo_bw()),
        ("apple.png", apple()),
        ("diagram.png", diagram()),
        ("cartoon.png", cartoon()),
    ]
    for name, image in samples:
        image.save(HERE / name)
        print(f"wrote {HERE / name}")


if __name__ == "__main__":
    main()
