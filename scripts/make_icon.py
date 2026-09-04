"""Generate assets/KluteTimer.ico from Pillow (no external image assets).

Mirrors the in-app tray icon: a teal disc with a dark "K". Run this once to
(re)generate the icon; the .ico is committed so a normal build needs no
regeneration.

Usage:
    python scripts/make_icon.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

TEAL = (45, 212, 191, 255)
DARK = (13, 17, 23, 255)
SIZES = [16, 32, 48, 64, 128, 256]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(PROJECT_ROOT, "assets", "KluteTimer.ico")


def _load_font(px: int) -> ImageFont.FreeTypeFont:
    """Best-effort bold sans-serif; fall back to Pillow's bitmap default."""
    for name in ("arialbd.ttf", "seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _render(size: int) -> Image.Image:
    # Supersample 4x for smooth edges, then downscale.
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = int(s * 0.06)
    draw.ellipse([pad, pad, s - pad, s - pad], fill=TEAL)

    font = _load_font(int(s * 0.62))
    text = "K"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (s - tw) / 2 - bbox[0]
    ty = (s - th) / 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=DARK)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    # Render one high-res master; Pillow downsamples it to every requested size.
    master = _render(max(SIZES))
    master.save(OUT_PATH, format="ICO", sizes=[(sz, sz) for sz in SIZES])
    print(f"Wrote {OUT_PATH} ({', '.join(str(s) for s in SIZES)} px)")


if __name__ == "__main__":
    main()
