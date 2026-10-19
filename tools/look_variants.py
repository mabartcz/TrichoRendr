"""Renders small variants of the last real TrichoRendr job with different Look settings, for tuning
cycles.py or the defaults side by side.

    python tools/look_variants.py <out dir> [variant ...]      (default: all variants)

Uses the job SketchUp exported last (%TEMP%/TrichoRendr), so render something in SketchUp first.
PERSP=1 swaps in a perspective garden camera (useful when the last job was a plan view).
BLENDER overrides the Blender path. Output: <out dir>/<variant>.png
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugin", "tricho_rendr", "blender", "cycles.py")
SRC = os.path.join(os.environ.get("TEMP", "/tmp"), "TrichoRendr")

# Changes against the defaults cycles.py falls back to when a key is missing (100 % = normal).
VARIANTS = {
    "default": {},
    "sunset": {"time": "sunset"},
    "punchy": {"style": "punchy"},
    "contrast": {"style": "contrast"},
    "vivid": {"style": "vivid"},
    "satglow": {"saturation": 150, "glow": 50},
    "warm": {"warmth": 60},
    "cool": {"warmth": -60},
    "noshadow": {"shadows": False},
    "soft": {"softness": 40, "sun": 150},
    "leaves": {"leaves": 80},
    "transparent": {"background": "transparent"},
    "materials": {"water_tint": 100, "waves": 200, "glass": 200},
    "bright": {"exposure": 1.0, "sky": 200},
}


def blender():
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    found = glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe")
    if not found:
        sys.exit("Blender not found; set BLENDER")
    return max(found, key=lambda p: [int(x) for x in p.split("Blender ")[-1].split("\\")[0].split(".")])


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "target", "looks")
    names = sys.argv[2:] or list(VARIANTS)
    job = os.path.join(out, "job")
    os.makedirs(job, exist_ok=True)
    for f in ("pos.bin", "uv.bin", "mat.bin", "inst.bin"):
        shutil.copy(os.path.join(SRC, f), job)  # always fresh: a new SketchUp render changes them
    base = json.load(open(os.path.join(SRC, "scene.json"), encoding="utf-8"))
    base.update(width=900, height=390, samples=16)
    if os.environ.get("PERSP"):  # a garden view of the test model
        base.update(ortho=None, vfov=35.0, eye=[985.67, 425.10, 60.15], target=[-650.98, 629.47, 115.23],
                    up=[0.0331, -0.0041, 0.9994], sun=[0.4094, -0.2766, 0.8694])
    exe = blender()
    for n in names:
        json.dump(dict(base, look=VARIANTS[n]), open(os.path.join(job, "scene.json"), "w", encoding="utf-8"))
        t = time.time()
        r = subprocess.run([exe, "-b", "--factory-startup", "--python-exit-code", "1", "--python", SCRIPT, "--", job],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 0 and os.path.exists(os.path.join(job, "render.png"))
        if ok:
            shutil.move(os.path.join(job, "render.png"), os.path.join(out, f"{n}.png"))
        else:
            print((r.stdout + r.stderr)[-2500:])
        print(n, "ok" if ok else "FAILED", f"{time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
