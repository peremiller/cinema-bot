"""Render the Cinema Finder logo to PNG with Pillow (no native libs needed).

Produces:
  web/logo-512.png  – transparent mark (for app stores, overlays)
  web/icon-512.png  – square dark badge (upload to BotFather as the bot avatar)
"""
import math

from PIL import Image, ImageDraw

GOLD = (233, 186, 78, 255)
DARK = (11, 14, 20, 255)
BLUE = (79, 134, 214, 255)
BADGE_BG = (22, 28, 44, 255)

SS = 3  # supersample factor for smooth edges


def mark_image(size: int) -> Image.Image:
    """The pin + play-button mark on a transparent canvas."""
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def s(v: float) -> float:
        return v * W / 512.0

    # Pin: circular head + tangent triangle forming the teardrop tip.
    cx, cy, r = 256, 190, 150
    d.ellipse([s(cx - r), s(cy - r), s(cx + r), s(cy + r)], fill=GOLD)
    tip_y = 442
    dist = tip_y - cy
    alpha = math.acos(r / dist)              # half-angle of the tangent
    a1 = math.pi / 2 - alpha
    a2 = math.pi / 2 + alpha
    tp1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
    tp2 = (cx + r * math.cos(a2), cy + r * math.sin(a2))
    d.polygon(
        [(s(tp1[0]), s(tp1[1])), (s(cx), s(tip_y)), (s(tp2[0]), s(tp2[1]))],
        fill=GOLD,
    )

    # Dark inset screen + blue accent ring.
    ix, iy, ir = 256, 188, 98
    d.ellipse([s(ix - ir), s(iy - ir), s(ix + ir), s(iy + ir)], fill=DARK)
    d.ellipse(
        [s(ix - ir), s(iy - ir), s(ix + ir), s(iy + ir)],
        outline=BLUE, width=int(s(8)),
    )

    # Play button.
    d.polygon(
        [(s(232), s(142)), (s(232), s(234)), (s(314), s(188))], fill=GOLD
    )

    return img.resize((size, size), Image.LANCZOS)


def main():
    mark_image(512).save("web/logo-512.png")

    W = 512 * SS
    badge = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ImageDraw.Draw(badge).rounded_rectangle(
        [0, 0, W - 1, W - 1], radius=int(116 * SS), fill=BADGE_BG
    )
    badge = badge.resize((512, 512), Image.LANCZOS)
    mk = mark_image(364)
    badge.alpha_composite(mk, (74, 62))
    badge.convert("RGB").save("web/icon-512.png", "PNG")
    print("wrote web/logo-512.png and web/icon-512.png")


if __name__ == "__main__":
    main()
