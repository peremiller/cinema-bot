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
CAPTION_H = 108
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


# MTRCB family-friendliness on a 0-10 scale (higher = more permissive audience).
_PG_SCORE = {"G": 10, "PG": 8, "SPG": 6, "R-13": 5, "R13": 5,
             "R-16": 3, "R16": 3, "R-18": 1, "R18": 1, "X": 0}


def _pg_score(mtrcb: str) -> float:
    return _PG_SCORE.get((mtrcb or "").upper().replace(" ", ""), 5)


def _best_index(movies: list) -> int:
    """Index of the film with the best audience + parental-guidance combo,
    among films that actually have an audience rating. -1 if none qualify."""
    best_i, best_score = -1, -1.0
    for i, m in enumerate(movies):
        r = m.get("rating10")
        if not r:
            continue
        score = r + _pg_score(m.get("mtrcb"))
        if score > best_score:
            best_score, best_i = score, i
    return best_i


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
    f_genre = _font(21)
    f_ribbon = _font(20, bold=True)
    best_i = _best_index(movies)
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

        # Emphasise the best audience + parental-guidance pick.
        if i == best_i:
            draw.rounded_rectangle(
                [x - 5, y - 5, x + POSTER_W + 5, y + POSTER_H + 5],
                radius=8, outline=GOLD, width=6,
            )
            rib = "TOP PICK"
            rw = draw.textlength(rib, font=f_ribbon)
            sx = x + 8 + 12 + 9          # star centre
            tx = sx + 9 + 8              # text start
            draw.rounded_rectangle([x + 8, y + 8, tx + rw + 12, y + 44],
                                   radius=8, fill=GOLD)
            _draw_star(draw, sx, y + 26, 9, BG)
            draw.text((tx, y + 15), rib, font=f_ribbon, fill=BG)

        ty = y + POSTER_H + 8
        title = _truncate(draw, m.get("title", "Untitled"), f_name, POSTER_W)
        draw.text((x, ty), title, font=f_name, fill=TEXT)
        cy = ty + 32
        # Genre first, then the rating below it.
        genres = m.get("genres_text")
        if genres:
            short = ", ".join(g.strip() for g in genres.split(",")[:2])
            short = _truncate(draw, short, f_genre, POSTER_W)
            draw.text((x, cy), short, font=f_genre, fill=MUTED)
            cy += 28
        # One line: parental-guidance rating (MTRCB) left, audience ★ rating right.
        pg = m.get("mtrcb")
        if pg:
            pg = str(pg)
            pw = draw.textlength(pg, font=f_rate)
            draw.rounded_rectangle([x, cy - 1, x + pw + 14, cy + 25], radius=5,
                                   outline=MUTED, width=2)
            draw.text((x + 7, cy), pg, font=f_rate, fill=TEXT)
        rating = m.get("rating10") or 0
        if rating:
            rtxt = f"{rating:.1f}"
            tw = draw.textlength(rtxt, font=f_rate)
            tx = x + POSTER_W - tw
            draw.text((tx, cy), rtxt, font=f_rate, fill=GOLD)
            _draw_star(draw, tx - 16, cy + 12, 10, GOLD)

    bio = BytesIO()
    img.save(bio, "JPEG", quality=88)
    bio.seek(0)
    bio.name = "now_playing.jpg"
    return bio
