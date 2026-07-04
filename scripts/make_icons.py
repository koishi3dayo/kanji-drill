# -*- coding: utf-8 -*-
"""PWA用アイコンを生成する。青背景に白い「漢」の文字＋鉛筆の雰囲気。"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ICONS = BASE / 'icons'
ICONS.mkdir(exist_ok=True)

PRIMARY = (74, 144, 217)     # --primary
PRIMARY_DARK = (44, 111, 173)
WHITE = (255, 255, 255)

def find_font(size):
    candidates = [
        r"C:\Windows\Fonts\meiryob.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothB.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]
    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()

def make_icon(size, maskable=False):
    img = Image.new('RGB', (size, size), PRIMARY)
    d = ImageDraw.Draw(img)
    # 背景のグラデーション風（斜めの明暗）
    for y in range(size):
        t = y / size
        r = int(PRIMARY[0] * (1 - t) + PRIMARY_DARK[0] * t)
        g = int(PRIMARY[1] * (1 - t) + PRIMARY_DARK[1] * t)
        b = int(PRIMARY[2] * (1 - t) + PRIMARY_DARK[2] * t)
        d.line([(0, y), (size, y)], fill=(r, g, b))
    # 中央に「漢」
    # maskable は端が切られるので文字を少し小さめに
    ratio = 0.52 if maskable else 0.62
    font = find_font(int(size * ratio))
    text = "漢"
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    d.text((x, y), text, font=font, fill=WHITE)
    return img

sizes = [(192, 'icon-192.png', False),
         (512, 'icon-512.png', False),
         (512, 'icon-512-maskable.png', True),
         (180, 'icon-180.png', False)]  # apple-touch-icon

for size, name, maskable in sizes:
    img = make_icon(size, maskable)
    img.save(ICONS / name)
    print("saved", name)

print("done")
