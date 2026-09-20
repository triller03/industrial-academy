"""Generate the ASAPA brand assets (Mufasa Corp).

Renders the ASAPA industrial monogram: a blue gear ring with an amber hub that
carries a circuit-styled letter "A", plus a light "PCB track" that crosses the
gear to an IC chip. Emits:

    assets/app.ico                 multi-size Windows icon (16..256)
    assets/asapa_logo.png          512px square mark
    assets/asapa_lockup.png        mark + "ASAPA" wordmark (docs / marketing)
    frontend/logo.png              128px mark (UI brand block)
    frontend/favicon.ico           browser tab icon
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")

S = 512
C = S // 2

BLUE = (25, 68, 130, 255)      # deep industrial blue
DARK = (10, 34, 70, 255)       # near-navy (glyph / wordmark)
AMBER = (245, 166, 35, 255)    # signal amber
LIGHT = (146, 190, 240, 255)   # light blue circuit track
CLEAR = (0, 0, 0, 0)


def _font(size: int, bold: bool = True):
    if bold:
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/ariblk.ttf",
            "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _rotated_rect(draw, cx, cy, angle, w1, w2, r1, r2, fill):
    """Draw a radial tooth (trapezoid) centred at angle (radians)."""
    pts = [
        (-w1, r1), (w1, r1), (w2, r2), (-w2, r2),
    ]
    cos, sin = math.cos(angle), math.sin(angle)
    poly = []
    for x, y in pts:
        rx = cx + x * cos - y * sin
        ry = cy + x * sin + y * cos
        poly.append((rx, ry))
    draw.polygon(poly, fill=fill)


def make_mark(size: int = S) -> Image.Image:
    img = Image.new("RGBA", (size, size), CLEAR)
    scale = size / S
    d = ImageDraw.Draw(img)

    def pt(x, y):
        return int(x * scale), int(y * scale)

    def rpx(v):
        return int(v * scale)

    # 1. gear teeth
    K = 16
    root_r, tip_r = 206, 236
    r1, r2 = root_r - 8, tip_r
    for k in range(K):
        ang = -math.pi / 2 + k * 2 * math.pi / K
        _rotated_rect(d, C, C, ang, 12, 13, r1, r2, BLUE)

    # 2. solid gear body + inner ring
    d.ellipse([C - root_r, C - root_r, C + root_r, C + root_r], fill=BLUE)

    # 3. amber hub
    hub = 118
    d.ellipse([C - hub, C - hub, C + hub, C + hub], fill=AMBER)

    # 4. bolt holes (cut to transparent)
    for k in range(6):
        ang = -math.pi / 2 + k * math.pi / 3
        hx = C + 68 * math.cos(ang)
        hy = C + 68 * math.sin(ang)
        hr = 9
        d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=CLEAR)

    # 5. circuit "A" glyph on the hub
    glyph = _font(120, bold=True)
    d.text((C, C + 12), "A", font=glyph, fill=DARK, anchor="mm")

    # 6. light PCB track ring across the gear
    track = 162
    d.ellipse([C - track, C - track, C + track, C + track],
              outline=LIGHT, width=6)

    # 7. IC chip + trace from the A's right foot
    d.rounded_rectangle([401, 213, 427, 231], radius=4, fill=AMBER)
    d.line([(326, 318), (326, 296), (401, 296), (401, 222)],
           fill=AMBER, width=6)
    d.ellipse([320, 312, 332, 324], fill=AMBER)

    # 8. left via pad (donut) for visual balance
    d.ellipse([145, 372, 167, 394], fill=AMBER)
    d.ellipse([151, 378, 161, 388], fill=BLUE)

    return img


def make_lockup() -> Image.Image:
    W, H = 560, 140
    img = Image.new("RGBA", (W, H), CLEAR)
    mark = make_mark(120)
    img.paste(mark, (10, 10), mark)
    d = ImageDraw.Draw(img)

    word = _font(58, bold=True)
    d.text((152, 58), "ASAPA", font=word, fill=DARK, anchor="lm")

    bar_y = 84
    d.rectangle([152, bar_y, 208, bar_y + 5], fill=AMBER)

    tagline = "INDUSTRIAL AUTOMATION TRAINING PLATFORM"
    f = _font(21, bold=False)
    track = 3
    x = 152
    y = 104
    for ch in tagline:
        d.text((x, y), ch, font=f, fill=BLUE)
        x += f.getlength(ch) + track
    return img


def main() -> None:
    os.makedirs(FRONTEND, exist_ok=True)

    mark = make_mark(512)
    mark.save(os.path.join(HERE, "asapa_logo.png"))
    mark.save(os.path.join(HERE, "app.ico"),
              format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])

    lockup = make_lockup()
    lockup.save(os.path.join(HERE, "asapa_lockup.png"))

    mark.resize((128, 128), Image.Resampling.LANCZOS).save(
        os.path.join(FRONTEND, "logo.png"))
    mark.resize((48, 48), Image.Resampling.LANCZOS).save(
        os.path.join(FRONTEND, "favicon.ico"), format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48)])

    for name in ("app.ico", "asapa_logo.png", "asapa_lockup.png"):
        print(f"wrote assets/{name}")
    print("wrote frontend/logo.png, frontend/favicon.ico")


if __name__ == "__main__":
    main()