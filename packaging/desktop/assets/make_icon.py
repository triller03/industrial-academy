"""Generate the desktop app icon (packaging/desktop/assets/app.ico)."""

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app.ico")

W = H = 256
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

draw.rounded_rectangle((8, 8, 248, 248), radius=52, fill=(10, 54, 92, 255))
draw.rectangle((40, 40, 216, 216), outline=(255, 255, 255, 255), width=10)
draw.polygon([(128, 78), (176, 172), (80, 172)], fill=(255, 255, 255, 255))
draw.polygon([(128, 104), (160, 166), (96, 166)], fill=(10, 54, 92, 255))

font_path = "C:/Windows/Fonts/arialbd.ttf"
for size in (48, 56, 64):
    font = ImageFont.truetype(font_path, size)
    draw.text((128, 122), "IA", font=font, fill=(255, 255, 255, 255), anchor="mm")
    break

img.save(OUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"icon written: {OUT}")