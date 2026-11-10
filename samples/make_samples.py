"""Generate the sample test images, so samples stay reproducible and license-free.

Run with: uv run python samples/make_samples.py
"""

from __future__ import annotations

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
    import math

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


def main() -> None:
    logo_bw().save(HERE / "logo_bw.png")
    print(f"wrote {HERE / 'logo_bw.png'}")


if __name__ == "__main__":
    main()
