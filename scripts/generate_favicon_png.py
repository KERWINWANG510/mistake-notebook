# -*- coding: utf-8 -*-
"""生成浏览器标签页用 PNG 图标（需 Pillow: pip install Pillow）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "frontend" / "public"


def draw_icon(size: int):
    from PIL import Image, ImageDraw, ImageFont

    radius = max(3, round(size * 0.28))
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(99 + (139 - 99) * t)
        g = int(102 + (92 - 102) * t)
        b = int(241 + (246 - 241) * t)
        bg_draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img = Image.composite(bg, img, mask)

    draw = ImageDraw.Draw(img)
    hl = max(2, round(size * 0.22))
    draw.rounded_rectangle(
        (max(1, round(size * 0.06)), max(1, round(size * 0.06)), hl, hl),
        radius=max(1, hl // 4),
        fill=(255, 255, 255, 38),
    )

    text = "错"
    font_size = max(10, round(size * 0.52))
    font = None
    for name in ("msyhbd.ttc", "msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] - round(size * 0.02)
    draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)
    return img


def main() -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("请先安装: pip install Pillow", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size, name in ((16, "favicon-16.png"), (32, "favicon-32.png"), (180, "apple-touch-icon.png")):
        out = OUT_DIR / name
        draw_icon(size).save(out, "PNG")
        print(f"已生成 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
