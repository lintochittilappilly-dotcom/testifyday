"""Branded 1200x630 Open Graph card for a public wall (and sane fallbacks).

Rendered on demand so every /wall/<slug> link can unfurl with the business name
and testimonial count instead of one generic company image. Output is a PNG,
which is what Twitter/X, LinkedIn, Slack and iMessage all expect.
"""
import io
import math
import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = (10, 10, 10)
FG = (250, 250, 250)
MUTED = (160, 160, 160)

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _hex_to_rgb(value: str, fallback=(255, 87, 34)):
    value = (value or "").strip()
    if len(value) == 7 and value.startswith("#"):
        try:
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            return fallback
    return fallback


def _truncate(draw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    out = text
    while out and draw.textlength(out + ellipsis, font=font) > max_width:
        out = out[:-1]
    return (out + ellipsis).strip()


def _star(draw, cx: float, cy: float, radius: float, fill, points: int = 5):
    """Filled star polygon — font glyphs for ★ are not guaranteed to exist."""
    inner = radius * 0.42
    coords = []
    for i in range(points * 2):
        r = radius if i % 2 == 0 else inner
        angle = -math.pi / 2 + i * math.pi / points
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(coords, fill=fill)


def render_wall_card(business_name: str, count: int, accent: str = "#ff5722") -> bytes:
    accent_rgb = _hex_to_rgb(accent)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)

    # Soft accent glow, then the content layer on top.
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for step, alpha in ((0, 10), (90, 10), (180, 12), (270, 14)):
        gdraw.ellipse((-420 + step, -480 + step, 760 - step, 340 - step), fill=(*accent_rgb, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, HEIGHT - 14, WIDTH, HEIGHT), fill=accent_rgb)

    name_font = _font(64)
    label_font = _font(24)
    count_font = _font(40)
    small_font = _font(26)

    draw.text((72, 64), "WALL OF LOVE", font=label_font, fill=accent_rgb)

    name = _truncate(draw, business_name or "Testimonials", name_font, WIDTH - 144)
    draw.text((72, 116), name, font=name_font, fill=FG)

    line = f"What {count} {'customer' if count == 1 else 'customers'} say about {business_name or 'us'}"
    line = _truncate(draw, line, count_font, WIDTH - 144)
    draw.text((72, 240), line, font=count_font, fill=FG)

    for i in range(5):
        _star(draw, 72 + 18 + i * 46, 340, 18, accent_rgb)

    draw.text((72, HEIGHT - 110), "testify.day", font=small_font, fill=MUTED)
    draw.text((WIDTH - 320, HEIGHT - 110), "Collected with Testify", font=small_font, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_default_card() -> bytes:
    return render_wall_card("Testify", 0, "#ff5722")
