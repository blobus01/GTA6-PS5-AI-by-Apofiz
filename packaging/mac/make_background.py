"""DMG window background (660x420 @1x and @2x) in Apofiz colours.

Uses the official black wordmark from ~/Downloads/apofiz_brand (or the copy in
assets/) as-is; only the backdrop, arrow and caption are drawn here.
Layout must match build_dmg.sh: app icon at (170, 230), Applications at (490, 230).

    python make_background.py OUT_DIR
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 660, 420
REPO = Path(__file__).resolve().parents[2]
WORDMARK = [Path.home() / "Downloads/apofiz_brand/apofiz-wordmark-black.png", REPO / "assets/apofiz-wordmark-black.png"]
FONTS = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/HelveticaNeue.ttc",
         "/System/Library/Fonts/Helvetica.ttc"]


def font(size: int):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(scale: int) -> Image.Image:
    w, h = W * scale, H * scale
    img = Image.new("RGB", (w, h), (247, 248, 252))  # light: Finder draws icon labels in dark text
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((-w * 0.2, h * 0.25, w * 0.55, h * 1.3), fill=(59, 130, 246, 46))   # #3b82f6
    d.ellipse((w * 0.45, h * 0.2, w * 1.2, h * 1.25), fill=(139, 92, 246, 46))    # #8b5cf6
    img.paste(glow.filter(ImageFilter.GaussianBlur(90 * scale)), (0, 0), glow.filter(ImageFilter.GaussianBlur(90 * scale)))

    src = next((p for p in WORDMARK if p.exists()), None)
    if src:
        wm = Image.open(src).convert("RGBA")
        tw = 150 * scale
        wm = wm.resize((tw, round(wm.height * tw / wm.width)), Image.LANCZOS)
        img.paste(wm, ((w - tw) // 2, 34 * scale), wm)

    d = ImageDraw.Draw(img)
    f = font(15 * scale)
    title = "Play GTA6 · AI Remote"
    tw = d.textlength(title, font=f)
    d.text(((w - tw) / 2, 92 * scale), title, font=f, fill=(71, 80, 99))

    # arrow between the two icons (y = 230)
    y, x0, x1 = 230 * scale, 250 * scale, 410 * scale
    col = (99, 102, 241)
    d.line((x0, y, x1 - 14 * scale, y), fill=col, width=4 * scale)
    d.polygon([(x1, y), (x1 - 18 * scale, y - 11 * scale), (x1 - 18 * scale, y + 11 * scale)], fill=col)

    f2 = font(13 * scale)
    cap = "Drag to Applications to install"
    cw = d.textlength(cap, font=f2)
    d.text(((w - cw) / 2, 352 * scale), cap, font=f2, fill=(100, 110, 130))
    return img


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    render(1).save(out / "background.png")
    render(2).save(out / "background@2x.png")
    print(out / "background.png")


if __name__ == "__main__":
    main()
