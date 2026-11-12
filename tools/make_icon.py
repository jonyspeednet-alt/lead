"""Generate the DriveAutomation application icon (Google-Drive inspired, lightning bolt).

Produces a multi-resolution .ico so the Desktop/Start Menu shortcut looks sharp
on every Windows scale factor.
"""
import os
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
OUT_ICO = os.path.join(OUT_DIR, "DriveAutomation.ico")
OUT_PNG = os.path.join(OUT_DIR, "DriveAutomation.png")

S = 1024  # master canvas
GREEN = (15, 157, 88)
YELLOW = (244, 180, 0)
BLUE = (66, 133, 244)
DARK = (30, 41, 59)


def rounded_bg():
    """White rounded square with a soft drop shadow."""
    pad = 64
    card = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=190, fill=(255, 255, 255, 255))

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    ds.rounded_rectangle([pad + 10, pad + 26, S - pad + 10, S - pad + 26], radius=190, fill=(15, 23, 42, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(shadow)
    out.alpha_composite(card)
    return out


def drive_triangle():
    """The three-panel Drive triangle, centred on the card."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    top = (512, 250)
    left = (270, 560)
    right = (754, 560)
    mid = (512, 560)

    d.polygon([top, left, mid], fill=GREEN + (255,))
    d.polygon([top, right, mid], fill=BLUE + (255,))
    d.polygon([left, (392, 790), (632, 790)], fill=YELLOW + (255,))
    return img


def badge():
    """Navy badge with a yellow lightning bolt, bottom-right of the card."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy, r = 726, 726, 152
    d.ellipse([cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16], fill=(255, 255, 255, 255))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DARK + (255,))

    bolt = [
        (cx + 26, cy - 92), (cx - 52, cy + 12), (cx - 4, cy + 12),
        (cx - 30, cy + 96), (cx + 54, cy - 18), (cx + 6, cy - 18),
    ]
    d.polygon(bolt, fill=YELLOW + (255,))
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    base = rounded_bg()
    base.alpha_composite(drive_triangle())
    base.alpha_composite(badge())

    base.save(OUT_PNG)
    base.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon written:", OUT_ICO)
    print("preview written:", OUT_PNG)


if __name__ == "__main__":
    main()
