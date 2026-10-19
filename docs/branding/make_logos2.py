# Round 2: a few big tiles (render idea from concept 2) on a simple silhouette (from 3). The case is a
# slightly curved tube, not a cone, so it reads as a caddisfly case and not a trdelník.
# python -I make_logos2.py  ->  logo/r2_*.svg + logo/concepts2.html
import math, os

OUT = os.path.dirname(os.path.abspath(__file__))
GREEN, GREEN_HI, GREEN_LO, DARK, SUN = '#5fb36a', '#86cf78', '#3f8a4c', '#24302a', '#f2b33d'
GREYS = ['#6d7275', '#8b9093', '#a9adaf']


def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{body}</svg>'


def spine(t):
    """Case axis: a gentle curve from the mouth (t=0, upper right) to the tip (t=1, lower left)."""
    p0, p1, p2 = (49, 14), (42, 44), (13, 52)
    x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
    y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
    dx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
    dy = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
    return x, y, math.degrees(math.atan2(dy, dx))


ARC = sum(math.dist(spine(i / 200)[:2], spine((i + 1) / 200)[:2]) for i in range(200))


def head(color='#c9a25a'):
    """Larva head and front legs coming out of the mouth, pointing up-right."""
    x, y, a = spine(0)
    legs = ''.join(f'<path d="M{s * 3.4} -1 q{s * 3} -.5 {s * 4.2} 2.2" stroke="{color}" stroke-width="1.9" '
                   f'fill="none" stroke-linecap="round"/>' for s in (-1, 1))
    return (f'<g transform="translate({x} {y}) rotate({a - 90})">{legs}'
            f'<ellipse cx="0" cy="-3.2" rx="4.4" ry="3.8" fill="{color}"/></g>')


def segments(fills, n=4, w0=19, w1=12, gap=1.3, split=False):
    """n chunky blocks along the spine, tapering a little. split=True cuts each block in two tiles."""
    out = []
    for i in range(n):
        t = (i + .5) / n
        x, y, a = spine(t)
        w = w0 + (w1 - w0) * i / (n - 1)
        L = ARC / n - gap  # blocks cover the whole spine, thin gaps between them
        f = fills[i]
        if split:
            for k, side in enumerate((-1, 1)):
                out.append(f'<rect x="{-L / 2}" y="{(0 if side > 0 else -w / 2) + (gap / 2 if side > 0 else 0)}" '
                           f'width="{L}" height="{w / 2 - gap / 2}" rx="2" fill="{f[k]}" '
                           f'transform="translate({x:.2f} {y:.2f}) rotate({a:.1f})"/>')
        else:
            out.append(f'<rect x="{-L / 2}" y="{-w / 2}" width="{L}" height="{w}" rx="3.5" fill="{f}" '
                       f'transform="translate({x:.2f} {y:.2f}) rotate({a:.1f})"/>')
    return ''.join(out)


# A: four blocks, rendered green at the mouth fading to grey (unrendered) at the tip.
A = svg(segments([GREEN_HI, GREEN, GREYS[2], GREYS[1]]) + head())
# B: same, every block split in two tiles: still few enough to read at 16 px, a little more "pixel".
B = svg(segments([(GREEN_HI, GREEN), (GREEN, GREEN_LO), (GREEN_LO, GREYS[2]), (GREYS[2], GREYS[1])], split=True)
        + head())
# C: five blocks, all green except the last tile left grey = render nearly done; sun-yellow head.
C = svg(segments([GREEN_HI, GREEN, GREEN, GREEN_LO, GREYS[1]], n=5, w0=17, w1=10) + head()
        + f'<circle cx="55" cy="8" r="4.5" fill="{SUN}"/>')
# D: monochrome version of A for one-colour use (toolbar in light themes, print, favicon).
D = svg(segments(['currentColor'] * 4) + head('currentColor'))

CONCEPTS = [
    ('r2_blocks', 'A · Blocks', A, 'Four big blocks on a curved case: green (rendered) at the opening, grey '
     '(not rendered yet) at the tip. The simplest render + chrostík mix.'),
    ('r2_tiles', 'B · Split tiles', B, 'Each block cut in two tiles, so it reads a bit more as pixels, '
     'but still only 8 pieces.'),
    ('r2_sun', 'C · Blocks + sun', C, 'Five blocks, almost all rendered, with a small sun: light / renderer.'),
    ('r2_mono', 'D · One colour', D, 'A in a single colour, for places where colour is not available.'),
]
for key, _, body, _ in CONCEPTS:
    open(os.path.join(OUT, f'{key}.svg'), 'w', encoding='utf-8').write(body)

cards = ''.join(f'''
  <section>
    <h2>{title}</h2>
    <div class="row">
      <div class="tile dark">{body}</div>
      <div class="tile light">{body}</div>
      <div class="small dark"><div style="width:32px">{body}</div><div style="width:24px">{body}</div><div style="width:16px">{body}</div></div>
    </div>
    <div class="word dark"><div style="width:44px">{body}</div><b>Tricho<span>Rendr</span></b></div>
    <p>{text}</p>
  </section>''' for key, title, body, text in CONCEPTS)

open(os.path.join(OUT, 'concepts2.html'), 'w', encoding='utf-8').write(f'''<!doctype html>
<meta charset="utf-8"><title>TrichoRendr logo, round 2</title>
<style>
  body {{ margin: 0; padding: 24px; background: #121314; color: #e6e6e6; font: 14px "Segoe UI", system-ui, sans-serif; }}
  h1 {{ font-size: 18px; margin: 0 0 18px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 18px; }}
  section {{ background: #1b1c1e; border: 1px solid #34373b; border-radius: 10px; padding: 16px; }}
  h2 {{ font-size: 15px; margin: 0 0 12px; }}
  .row {{ display: flex; gap: 10px; align-items: stretch; }}
  .tile {{ width: 120px; height: 120px; border-radius: 8px; padding: 10px; box-sizing: border-box; }}
  .dark {{ background: #232528; color: #e6e6e6; }} .light {{ background: #f3f3f0; color: {DARK}; }}
  .small {{ flex: 1; border-radius: 8px; display: flex; gap: 12px; align-items: center; justify-content: center; }}
  .word {{ margin-top: 10px; border-radius: 8px; padding: 10px 14px; display: flex; gap: 10px; align-items: center; }}
  .word b {{ font-size: 22px; font-weight: 600; letter-spacing: .3px; }} .word span {{ color: {GREEN}; }}
  p {{ color: #9a9ca0; margin: 10px 0 0; line-height: 1.45; }}
  svg {{ display: block; width: 100%; height: auto; }}
</style>
<h1>TrichoRendr logo, round 2: few big tiles, curved case</h1>
<div class="grid">{cards}</div>''')
print('ok')
