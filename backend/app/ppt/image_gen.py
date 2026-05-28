"""Generate decorative PNG images for PPT slides using Pillow."""
from __future__ import annotations

import math
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ppt.styles import Theme

Rgb = tuple[int, int, int]


def _blend(c1: Rgb, c2: Rgb, t: float) -> Rgb:
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


# ─── Title slide background decoration ────────────────────────────────────

def make_title_deco(theme: "Theme", width_px: int = 700, height_px: int = 520) -> BytesIO | None:
    """Abstract overlapping-circles PNG for the title slide right panel."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w, h = width_px, height_px

        accent  = theme.accent
        accent2 = theme.accent2
        title_bg = theme.title_bg

        # Blend towards the slide background colour so circles feel soft
        c1 = (*_blend(accent, title_bg, 0.45),  55)
        c2 = (*_blend(accent2, title_bg, 0.35), 65)
        c3 = (*_blend(accent, (255, 255, 255), 0.3), 35)

        # Large circle — top-right overflow
        d.ellipse([int(w * 0.22), int(h * -0.30), int(w * 1.10), int(h * 0.85)], fill=c1)
        # Medium circle — bottom-right
        d.ellipse([int(w * 0.50), int(h * 0.55), int(w * 1.20), int(h * 1.45)], fill=c2)
        # Small highlight circle
        d.ellipse([int(w * 0.60), int(h * -0.05), int(w * 0.95), int(h * 0.38)], fill=c3)

        # Subtle diagonal grid lines
        line_col = (*_blend(accent, title_bg, 0.55), 18)
        for offset in range(0, w + h, 45):
            d.line([(offset, 0), (0, offset)], fill=line_col, width=1)

        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


# ─── Content / chart / table slide corner decoration ─────────────────────

def make_corner_deco(theme: "Theme", size_px: int = 280) -> BytesIO | None:
    """Soft overlapping circles for slide body corners."""
    try:
        from PIL import Image, ImageDraw

        s = size_px
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        accent  = theme.accent
        accent2 = theme.accent2
        bg      = theme.slide_bg

        c1 = (*_blend(accent, bg, 0.55),  40)
        c2 = (*_blend(accent2, bg, 0.50), 35)
        c3 = (*_blend(accent, bg, 0.65),  25)

        d.ellipse([0,          0,          int(s*0.75), int(s*0.75)], fill=c1)
        d.ellipse([int(s*0.30), int(s*0.30), s,          s          ], fill=c2)
        d.ellipse([int(s*0.12), int(s*0.55), int(s*0.70), s         ], fill=c3)

        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


# ─── Summary slide background decoration ─────────────────────────────────

def make_summary_deco(theme: "Theme", width_px: int = 600, height_px: int = 480) -> BytesIO | None:
    """Decorative element for the summary / key-takeaways slide."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w, h = width_px, height_px

        accent   = theme.accent
        accent2  = theme.accent2
        title_bg = theme.title_bg

        # Three overlapping, partially transparent rings
        for (cx_pct, cy_pct, r_pct, alpha) in [
            (0.80, 0.20, 0.55, 45),
            (0.60, 0.75, 0.38, 38),
            (0.95, 0.65, 0.30, 30),
        ]:
            cx = int(w * cx_pct)
            cy = int(h * cy_pct)
            r  = int(min(w, h) * r_pct)
            fill = (*_blend(accent, title_bg, 0.5), alpha)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

        # A small bright accent circle
        cx2, cy2, r2 = int(w * 0.85), int(h * 0.15), int(min(w, h) * 0.14)
        d.ellipse([cx2-r2, cy2-r2, cx2+r2, cy2+r2],
                  fill=(*_blend(accent2, (255,255,255), 0.25), 70))

        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


# ─── Thin horizontal rule image (divider) ────────────────────────────────

def make_divider(theme: "Theme", width_px: int = 900, height_px: int = 6) -> BytesIO | None:
    """A simple 1-px gradient line for use as a visual divider."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        accent = theme.accent
        for x in range(width_px):
            alpha = int(220 * (1 - abs(x / width_px - 0.5) * 1.4))
            alpha = max(0, min(255, alpha))
            d.point((x, 2), fill=(*accent, alpha))
            d.point((x, 3), fill=(*accent, alpha))

        buf = BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None
