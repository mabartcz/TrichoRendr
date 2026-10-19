"""Round 3 logo: the caddisfly's home (chrostík case), flat and abstract: rounded stones, one glass, one leaf.

python -I docs/branding/make_logo3.py
writes plugin/tricho_rendr/images/icon.svg (variant ICON) and the preview docs/branding/logo3.html
"""

import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SAND, CLAY, STONE, SLATE = "#e6c07b", "#cf8a5a", "#a9b1b5", "#7c8a92"
GLASS, LEAF, HOLE = "#4fb8cc", "#6cb56a", "#2d3a40"
ICON = "lens"


def pill(cx, cy, w, h, fill, rot=0.0):
    return (
        f'<rect x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
        f'fill="{fill}" transform="rotate({rot:.0f} {cx:.1f} {cy:.1f})"/>'
    )


def ring_of(stones, r, hole=9.0, turn=0.0):
    """Stones (length, thickness, colour) laid around a circle of radius r, spaced by their length."""
    out = [f'<circle cx="32" cy="32" r="{hole}" fill="{HOLE}"/>'] if hole else []
    total = sum(w for w, _, _ in stones)
    a = turn - math.pi / 2
    for w, h, c in stones:
        mid = a + math.tau * w / total / 2
        out.append(pill(32 + r * math.cos(mid), 32 + r * math.sin(mid), w, h, c, math.degrees(mid) + 90))
        a += math.tau * w / total
    return out


def ring():
    """The case seen from its opening: eight even stones around the dark hole."""
    cols = [SAND, STONE, CLAY, GLASS, SLATE, SAND, LEAF, STONE]
    return ring_of([(15.5, 11.5, c) for c in cols], 19.5)


def pebbles():
    """Same ring, stones of different sizes like a real case."""
    stones = [(18, 12.5, SAND), (13, 10.5, SLATE), (16, 12, CLAY), (12.5, 10.5, STONE),
              (17.5, 12, GLASS), (13.5, 11, SAND), (16.5, 12.5, LEAF), (12, 10.5, STONE)]
    return ring_of(stones, 19.5, turn=0.2)


def double():
    """Two courses of stones, brick-laid, small opening."""
    outer = [(13, 9, c) for c in (SAND, STONE, CLAY, SLATE, GLASS, SAND, LEAF, STONE, CLAY, SLATE)]
    inner = [(10, 7.5, c) for c in (STONE, SAND, SLATE, CLAY, SAND, GLASS)]
    return ring_of(outer, 22.5, hole=6) + ring_of(inner, 12.5, hole=0, turn=0.5)


def lens():
    """The ring as a camera lens: glass in the opening with a glint (it is a renderer)."""
    out = ring()
    out.append(f'<circle cx="32" cy="32" r="5.5" fill="{GLASS}"/>')
    out.append('<circle cx="29.8" cy="29.8" r="1.8" fill="#ffffff"/>')
    return out


def sun():
    """The ring around a low sun instead of a dark hole: light coming through the home."""
    out = ring()
    out[0] = '<circle cx="32" cy="32" r="9" fill="#f4b63a"/>'
    return out


def spiral():
    """A spiral case (Helicopsyche builds these): stones growing along a spiral."""
    cols = [GLASS, SAND, SLATE, CLAY, STONE, LEAF, SAND, SLATE, CLAY, STONE, SAND]
    out = [f'<g transform="translate(2.5 1)"><circle cx="32" cy="32" r="4" fill="{HOLE}"/>']
    th = 0.0
    for c in cols:
        r = 7.0 + 1.9 * th
        w = 5.5 + 0.42 * r
        out.append(pill(32 + r * math.cos(th), 32 + r * math.sin(th), w, 0.6 * w + 2.5, c, math.degrees(th) + 90))
        th += (w + 2.2) / r
    out.append("</g>")
    return out


VARIANTS = {"ring": ring, "pebbles": pebbles, "double": double, "lens": lens, "sun": sun, "spiral": spiral}


def svg(name, size=64):
    body = "".join(VARIANTS[name]())
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}">{body}</svg>'


PAGE = """<!doctype html>
<meta charset="utf-8"><title>TrichoRendr logo, round 3</title>
<style>
  body { margin: 0; padding: 16px 24px; background: #f3f3f0; font: 14px "Segoe UI", sans-serif; }
  .row { display: flex; gap: 20px; align-items: end; margin-bottom: 14px; }
  .dark { background: #232528; padding: 8px; border-radius: 8px; }
  b { width: 60px; } svg { display: block; }
</style>
"""

if __name__ == "__main__":
    (ROOT / "plugin/tricho_rendr/images/icon.svg").write_text(svg(ICON) + "\n", encoding="utf-8", newline="\n")
    rows = []
    for name in VARIANTS:
        tiles = "".join(f"<div>{svg(name, n)}</div>" for n in (160, 64, 32, 24))
        dark = "".join(f'<div class="dark">{svg(name, n)}</div>' for n in (24, 64))
        rows.append(f'<div class="row"><b>{name}</b>{tiles}{dark}</div>')
    (ROOT / "docs/branding/logo3.html").write_text(PAGE + "".join(rows), encoding="utf-8", newline="\n")
    print("wrote icon.svg, logo3.html")
