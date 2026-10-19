# Logo concepts for TrichoRendr, built on the caddisfly (Trichoptera, chrostík) larva and its case.
# python -I make_logos.py  ->  logo/*.svg + logo/concepts.html
import math, os, random

OUT = os.path.dirname(os.path.abspath(__file__))
GREEN, GREEN_HI, SAND, STONE, DARK, SUN = '#5fb36a', '#8fd17a', '#d8b878', '#9aa0a0', '#24302a', '#f2b33d'


def svg(body, view='0 0 64 64'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}">{body}</svg>'


def case_rows(n=6, top=12, bottom=56, w_top=22, w_bottom=8):
    """Tapered tube, open end at the top: (y, height, width) per segment."""
    h = (bottom - top) / n
    return [(top + i * h, h + 1.2, w_top + (w_bottom - w_top) * i / (n - 1)) for i in range(n)]


def larva(x, y, s=1.0, color=DARK):
    """Head and three pairs of legs peeking out of the case mouth."""
    legs = ''.join(f'<path d="M{x + dx * s} {y + 2 * s} q{dx * 1.6 * s} {-2.5 * s} {dx * 2.6 * s} {-1 * s}" '
                   f'stroke="{color}" stroke-width="{1.6 * s}" fill="none" stroke-linecap="round"/>'
                   for dx in (-3, -1.5, 1.5, 3))
    return f'{legs}<ellipse cx="{x}" cy="{y - 1.5 * s}" rx="{4.2 * s}" ry="{3.6 * s}" fill="{color}"/>'


# 1. Pebble case: the larva's tube of little stones and sand, tilted like it's crawling up.
def pebbles():
    random.seed(4)
    tones = [SAND, STONE, '#c9a56a', '#7f8a86', '#b9b08f', GREEN]
    parts = []
    for i, (y, h, w) in enumerate(case_rows()):
        dx = random.uniform(-1, 1)
        parts.append(f'<rect x="{32 - w / 2 + dx:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                     f'rx="{min(h, w) / 2:.1f}" fill="{tones[i % len(tones)]}" stroke="{DARK}" stroke-width="1.2"/>')
    return svg(f'<g transform="rotate(38 32 34)">{"".join(reversed(parts))}{larva(32, 12)}</g>')


# 2. Render tiles: the case is built from pixels that go from noisy grey (tip) to fully rendered (mouth),
#    like a progressive render refining.
def tiles():
    random.seed(7)
    cells, px = [], 4
    for row, (y, h, w) in enumerate(case_rows(n=11, top=12, bottom=56)):
        k = row / 10  # 0 at the mouth, 1 at the tip
        cols = max(2, round(w / px))
        x0 = 32 - cols * px / 2
        for c in range(cols):
            if random.random() < k * 0.45:  # unrendered: grey noise, some missing
                if random.random() < 0.5:
                    continue
                g = random.randint(70, 140)
                fill = f'rgb({g},{g},{g})'
            else:
                fill = random.choice([GREEN, GREEN_HI, '#4f9d5a', SAND])
            cells.append(f'<rect x="{x0 + c * px + .4:.1f}" y="{y + .4:.1f}" width="{px - .8}" height="{px - .8}" '
                         f'rx=".8" fill="{fill}"/>')
    return svg(f'<g transform="rotate(38 32 34)">{"".join(cells)}{larva(32, 12, color="#e9efe6")}</g>')


# 3. Line mark: one clean stroke drawing of the case with growth rings, a sun rising from the mouth.
def line(stroke='currentColor'):
    top, bottom, wt, wb = 22, 58, 22, 7
    outline = (f'M{32 - wt / 2} {top} C{32 - wt / 2} {top + 18} {32 - wb / 2 - 2} {bottom - 8} {32 - wb / 2} {bottom} '
               f'Q32 {bottom + 3} {32 + wb / 2} {bottom} '
               f'C{32 + wb / 2 + 2} {bottom - 8} {32 + wt / 2} {top + 18} {32 + wt / 2} {top}')
    rings = ''.join(
        f'<path d="M{32 - w / 2} {y} Q32 {y + 3} {32 + w / 2} {y}" stroke="{stroke}" stroke-width="2.2" '
        f'fill="none" stroke-linecap="round"/>'
        for y, w in ((31, 20.5), (40, 16.5), (48.5, 12)))
    rays = ''.join(
        f'<line x1="{32 + 13 * math.cos(a):.1f}" y1="{17 - 13 * math.sin(a):.1f}" '
        f'x2="{32 + 17 * math.cos(a):.1f}" y2="{17 - 17 * math.sin(a):.1f}" stroke="{SUN}" stroke-width="2.6" '
        f'stroke-linecap="round"/>' for a in [math.radians(d) for d in (25, 60, 90, 120, 155)])
    return svg(f'{rays}<circle cx="32" cy="20" r="8" fill="{SUN}"/>'
               f'<ellipse cx="32" cy="{top}" rx="{wt / 2}" ry="3.2" fill="{DARK}" stroke="{stroke}" stroke-width="2.6"/>'
               f'<path d="{outline}" stroke="{stroke}" stroke-width="2.6" fill="none" stroke-linejoin="round"/>{rings}')


# 4. Leaf case: the case wrapped from three leaf pieces, the classic chrostík look, green on green.
def leaves():
    leaf = lambda y, w, h, fill: (f'<path d="M{32 - w / 2} {y} Q32 {y - h * .9} {32 + w / 2} {y} Q32 {y + h * 1.1} '
                                  f'{32 - w / 2} {y}Z" fill="{fill}" stroke="{DARK}" stroke-width="1.3"/>'
                                  f'<path d="M{32 - w / 2 + 2} {y} L{32 + w / 2 - 2} {y}" stroke="{DARK}" '
                                  f'stroke-width=".9" opacity=".55"/>')
    body = (leaf(47, 11, 8, '#3f7f4a') + leaf(38, 16, 10, '#4f9d5a') + leaf(28, 21, 11, GREEN)
            + f'<circle cx="32" cy="52.5" r="2.2" fill="{SAND}" stroke="{DARK}" stroke-width="1"/>')
    return svg(f'<g transform="rotate(-30 32 36)">{body}{larva(32, 20, .9)}</g>')


CONCEPTS = [
    ('pebbles', 'Pebble case', pebbles(), 'The larva in its tube of little stones, crawling up. Warm, natural, '
     'friendly; reads as "garden / water / nature".'),
    ('tiles', 'Render tiles', tiles(), 'The case is made of pixels: grey noise at the tip, rendered colour at the '
     'mouth, the way a render refines. Nature + rendering in one picture.'),
    ('line', 'Line + sun', line(), 'One clean line drawing of the case with growth rings, a sun rising out of it '
     '(light = renderer). Most "professional software", works in one colour.'),
    ('leaves', 'Leaf case', leaves(), 'The case wrapped from leaf pieces, as many chrostíci build it. '
     'Strong green silhouette, closest to landscape architecture.'),
]

for key, _, body, _ in CONCEPTS:
    open(os.path.join(OUT, f'{key}.svg'), 'w', encoding='utf-8').write(body)

cards = ''.join(f'''
  <section>
    <h2>{i}. {title}</h2>
    <div class="row">
      <div class="tile dark">{body}</div>
      <div class="tile light">{body}</div>
      <div class="small dark"><div style="width:32px">{body}</div><div style="width:24px">{body}</div><div style="width:16px">{body}</div></div>
    </div>
    <div class="word dark"><div style="width:44px">{body}</div><b>Tricho<span>Rendr</span></b></div>
    <p>{text}</p>
  </section>''' for i, (key, title, body, text) in enumerate(CONCEPTS, 1))

open(os.path.join(OUT, 'concepts.html'), 'w', encoding='utf-8').write(f'''<!doctype html>
<meta charset="utf-8"><title>TrichoRendr logo concepts</title>
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
<h1>TrichoRendr: logo concepts (caddisfly larva case)</h1>
<div class="grid">{cards}</div>''')
print('written to', OUT)
