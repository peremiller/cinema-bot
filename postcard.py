"""Build a single 'postcard' image collaging the films now playing nearby.

Sent as the FIRST message when a user checks movies, so they get an at-a-glance
overview before the individual detail cards. Uses Pillow; downloads poster
thumbnails from TMDB and tiles them under a header with the user's city.
"""
from __future__ import annotations

import math
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Brand palette (matches the landing page / bot cards).
BG = (11, 14, 20)
CARD_BG = (20, 25, 37)
GOLD = (229, 185, 78)
TEXT = (232, 236, 243)
MUTED = (154, 164, 181)

POSTER_W, POSTER_H = 300, 450
CAPTION_H = 80
GAP = 24
MARGIN = 30
HEADER_H = 132
COLS = 3
MAX = 6

_FONTS = {
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",       # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",    # Linux (VM)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",  # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (VM)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in _FONTS["bold" if bold else "regular"]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _poster(url: str | None):
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        src = Image.open(BytesIO(r.content)).convert("RGB")
        return ImageOps.fit(src, (POSTER_W, POSTER_H), Image.LANCZOS)
    except Exception:
        return None


def _draw_star(draw, cx: float, cy: float, r: float, fill) -> None:
    """Draw a filled 5-point star centred at (cx, cy) — fonts can't be trusted
    to carry the ★ glyph, so we render it as a polygon."""
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        rad = r if k % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def _truncate(draw, text: str, font, max_w: int) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return (text + "…") if text else "…"


def build_postcard(movies: list[dict], city: str) -> BytesIO:
    """Return an in-memory JPEG collaging up to MAX films (title + rating)."""
    movies = movies[:MAX]
    n = len(movies)
    cols = min(COLS, n) or 1
    rows = (n + cols - 1) // cols

    width = MARGIN * 2 + cols * POSTER_W + (cols - 1) * GAP
    cell_h = POSTER_H + CAPTION_H
    height = HEADER_H + rows * cell_h + (rows - 1) * GAP + MARGIN

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(48, bold=True)
    f_sub = _font(28)
    draw.text((MARGIN, 32), "NOW PLAYING", font=f_title, fill=GOLD)
    if city:
        draw.text((MARGIN, 92), f"in cinemas near {city}", font=f_sub, fill=MUTED)

    f_name = _font(25, bold=True)
    f_rate = _font(23)
    for i, m in enumerate(movies):
        col, row = i % cols, i // cols
        x = MARGIN + col * (POSTER_W + GAP)
        y = HEADER_H + row * (cell_h + GAP)

        poster = _poster(m.get("poster_url"))
        if poster:
            img.paste(poster, (x, y))
        else:
            draw.rounded_rectangle(
                [x, y, x + POSTER_W, y + POSTER_H], radius=12, fill=CARD_BG
            )
            label = _truncate(draw, m.get("title", "?"), f_name, POSTER_W - 24)
            draw.text((x + 14, y + POSTER_H // 2 - 12), label, font=f_name, fill=TEXT)

        ty = y + POSTER_H + 10
        title = _truncate(draw, m.get("title", "Untitled"), f_name, POSTER_W)
        draw.text((x, ty), title, font=f_name, fill=TEXT)
        rating = m.get("rating10") or 0
        if rating:
            _draw_star(draw, x + 9, ty + 47, 10, GOLD)
            draw.text((x + 24, ty + 34), f"{rating:.1f}", font=f_rate, fill=GOLD)

    bio = BytesIO()
    img.save(bio, "JPEG", quality=88)
    bio.seek(0)
    bio.name = "now_playing.jpg"
    return bio
