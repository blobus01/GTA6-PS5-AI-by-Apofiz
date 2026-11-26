"""Generate launcher icons from the OFFICIAL Apofiz mark (never redrawn).

Source: ~/Downloads/apofiz_brand/apofiz-mark-transparent.png (or argv[1]).
Outputs next to this file:
  icon.png        1024x1024 app icon (mark on a white rounded tile)
  icon.icns       macOS app icon (needs `iconutil`, macOS only)
  icon.ico        Windows app icon (16..256)
  tray.png        64x64 transparent mark for the tray / menu bar
  tray@2x.png     128x128 (retina menu bar)

Run:  python launcher/assets/make_icons.py [path/to/apofiz-mark-transparent.png]
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = Path.home() / "Downloads" / "apofiz_brand" / "apofiz-mark-transparent.png"


def square_mark(src: Image.Image) -> Image.Image:
    """Crop to the mark's alpha bbox and centre it on a transparent square."""
    src = src.convert("RGBA")
    bbox = src.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox() or (0, 0, *src.size)
    m = src.crop(bbox)
    side = max(m.size)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(m, ((side - m.width) // 2, (side - m.height) // 2), m)
    return out


def app_tile(mark: Image.Image, size: int = 1024) -> Image.Image:
    """macOS-style tile: 824px rounded white square + soft shadow, mark at ~64%."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tile = int(size * 824 / 1024)
    off = (size - tile) // 2
    radius = int(tile * 0.225)
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (off, off + size // 64, off + tile, off + tile + size // 64), radius, fill=(0, 0, 0, 70))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(size / 64)))
    body = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(body).rounded_rectangle((off, off, off + tile, off + tile), radius, fill=(255, 255, 255, 255))
    canvas.alpha_composite(body)
    inner = int(tile * 0.68)
    m = mark.resize((inner, inner), Image.LANCZOS)
    canvas.alpha_composite(m, ((size - inner) // 2, (size - inner) // 2 + size // 128))
    return canvas


def main() -> None:
    src_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    mark = square_mark(Image.open(src_path))
    icon = app_tile(mark)
    icon.save(HERE / "icon.png")
    icon.save(HERE / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    mark.resize((64, 64), Image.LANCZOS).save(HERE / "tray.png")
    mark.resize((128, 128), Image.LANCZOS).save(HERE / "tray@2x.png")
    if shutil.which("iconutil"):
        with tempfile.TemporaryDirectory() as tmp:
            iset = Path(tmp) / "icon.iconset"
            iset.mkdir()
            for s in (16, 32, 128, 256, 512):
                icon.resize((s, s), Image.LANCZOS).save(iset / f"icon_{s}x{s}.png")
                icon.resize((s * 2, s * 2), Image.LANCZOS).save(iset / f"icon_{s}x{s}@2x.png")
            subprocess.run(["iconutil", "-c", "icns", str(iset), "-o", str(HERE / "icon.icns")], check=True)
    print("icons written to", HERE)


if __name__ == "__main__":
    main()
