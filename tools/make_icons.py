"""
make_icons.py - draw the Taki icons from the shapes of web/public/favicon.svg.

    pip install pillow
    python tools/make_icons.py

Writes web/public/icons/ (the next `npm run build` copies it into server/static):

    icon-32.png, icon-192.png, icon-512.png    the rounded blue square with the bolt
    icon-maskable-512.png                      the same to the edges, bolt inside the safe area,
                                               for systems that cut icons to a shape of their own
    apple-touch-icon.png                       180 px, to the edges (iOS rounds it itself)
    taki.ico                                   16 to 256 px in one file, for the Windows shortcuts

Each size is drawn on its own, four times too large and then reduced, so the small
ones stay sharp. The files are kept in the repository; run this only if the logo changes.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "public", "icons")
BLUE, WHITE = (0, 75, 135, 255), (255, 255, 255, 255)
# favicon.svg, on a 32 x 32 grid: <rect rx="7"> and the path M18.5 4 8 18h6.5L12.5 28 24 13h-7z
BOLT = [(18.5, 4), (8, 18), (14.5, 18), (12.5, 28), (24, 13), (17, 13)]
RADIUS = 7.0
SS = 4                                   # draw this many times too large


def draw(size: int, bleed: bool = False, bolt_scale: float = 1.0) -> Image.Image:
    """One icon. bleed: colour to the edges instead of a rounded square on a clear background."""
    n = size * SS
    img = Image.new("RGBA", (n, n), BLUE if bleed else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = n / 32.0
    if not bleed:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=RADIUS * k, fill=BLUE)
    d.polygon([((16 + (x - 16) * bolt_scale) * k, (16 + (y - 16) * bolt_scale) * k) for x, y in BOLT], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for size in (32, 192, 512):
        draw(size).save(os.path.join(OUT, f"icon-{size}.png"), optimize=True)
    draw(512, bleed=True, bolt_scale=0.66).save(os.path.join(OUT, "icon-maskable-512.png"), optimize=True)
    draw(180, bleed=True, bolt_scale=0.86).convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    images = [draw(s) for s in sizes]
    images[-1].save(os.path.join(OUT, "taki.ico"), format="ICO", sizes=[(s, s) for s in sizes],
                    append_images=images[:-1])
    for name in sorted(os.listdir(OUT)):
        print(f"{name:28s} {os.path.getsize(os.path.join(OUT, name)):>7d} bytes")


if __name__ == "__main__":
    main()
