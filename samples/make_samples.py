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


def main() -> None:
    for name, image in [("logo_bw.png", logo_bw()), ("apple.png", apple())]:
        image.save(HERE / name)
        print(f"wrote {HERE / name}")


if __name__ == "__main__":
    main()
