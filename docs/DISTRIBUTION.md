# Distribution, Blender and licensing

Decision (0.2.0): **users install Blender themselves** (5.0 or newer, default location), then install the
TrichoRendr `.rbz`. Blender does a lot for us (scene building through `bpy`, AgX color management, the
compositor for glow and saturation, the sky), so that is worth one extra install step. This page keeps what
we found about the alternatives, so we don't have to research it again.

Not legal advice: check the licensing part with a lawyer before selling.

## What users need on their PC

| Piece | Runs on | User installs |
|---|---|---|
| Ruby plugin | SketchUp's built-in Ruby | nothing (the `.rbz`) |
| `blender/cycles.py` | Blender's own Python (3.13 in Blender 5.1, with numpy) | Blender |
| `bin/tricho_rendr.exe` (launcher) | standalone Windows exe | nothing |
| `tools/`, `tests/` | system Python | developers only |

No system Python is needed on users' PCs.

## Option A: bundle Blender in the `.rbz` (rejected)

- Blender 5.1 installed is 977 MB (portable zip ~400 MB download); our `.rbz` is ~1 MB.
- Every TrichoRendr update would re-ship Blender.
- Distributing Blender ourselves means GPL duties for it (license text, source offer).

## Option B: download Blender on first use (good next step, ~1 day)

If no suitable Blender is found, the window offers "Set up renderer": download the official portable zip
from `download.blender.org`, pinned to the tested version, verify the published SHA-256, unpack to
`%LOCALAPPDATA%\TrichoRendr\blender-<version>` (no admin rights). Pros: one install step for users, the
exact Blender version `cycles.py` is tested with, no conflict with a Blender the user already has, and the
user downloads Blender from blender.org, so we don't redistribute it. Work: download with progress,
checksum, unzip, error handling; `blender` in `config.rb` looks there first.

## Option C: standalone Cycles instead of Blender (possible later, ~2 weeks)

Cycles is also published on its own: <https://projects.blender.org/blender/cycles> (Apache-2.0).

**Size** (measured from the Blender 5.1 install; the standalone total is an estimate, NVIDIA + CPU only):

| Part | Size |
|---|---|
| Whole Blender 5.1 | 977 MB |
| OpenImageDenoise (core 45 MB + CUDA 3 MB + CPU) | ~50 MB |
| Embree (CPU ray tracing) | 26 MB |
| NVIDIA kernels (sm_60/sm_61 cubin, OptiX + compute_75 PTX, zstd) | ~8 MB |
| OpenColorIO, OpenEXR, TBB | ~7 MB |
| Cycles itself (exe/lib with CPU kernels) | ~50 MB? |
| **Estimated package** | **~150 MB unpacked, ~60–80 MB download** |

Not needed from Blender: its Python (224 MB), datafiles (126 MB), video codecs, UI, oneAPI/HIP kernels.

**What Blender does for us today that we would have to replace:**

1. Scene building (`cycles.py` via `bpy`): a small C++ host linking libcycles that reads our job folder
   directly and writes the same `TR:` / `TR_PROGRESS` lines and `pass_N.png`. The `cycles` standalone app
   reads an XML scene format, but that is a test tool, too limited for us.
2. Color management (AgX view, looks, exposure, white balance): our own post-process on the linear image
   (check the license of whichever AgX implementation we use).
3. Compositor (bloom glow, saturation): our own post-process, simple in Rust.
4. Materials (water, glass, leaves, glow) and sky: these are Cycles shader nodes either way, they port
   almost one to one. Check that the 5.x multiple-scattering sky is in standalone Cycles.

**Building on Windows:** Visual Studio 2022 and CMake (installed here), Cycles' precompiled libraries
(`make update`, several GB), CUDA Toolkit **12.x** (CUDA 13 dropped Pascal, e.g. the GTX 1060), NVIDIA
OptiX SDK (free, needs an NVIDIA developer account). Every Cycles update means a rebuild and GPU re-test.

**Effort:** build and render `tests/fixtures` on the GTX 1060: 1–2 days (do this spike first and measure the
real size); port scene, materials and look: ~1 week; packaging and CI for the C++ build: a few days. The
plugin barely changes: it already talks to a separate exe through the job folder; only that exe changes.

## Licensing

- **Blender is GPL-2.0-or-later.** The Blender Foundation treats Python scripts that use its API (`bpy`)
  as part of Blender, so when distributed they must be GPL. That covers `blender/cycles.py`.
- **The Ruby plugin and the Rust launcher** only start Blender as a separate program and exchange files,
  normally treated as separate programs (could have another license), but that line is grey. Simplest
  clean choice while we use Blender: the whole project under **GPL-3.0-or-later** (done: `LICENSE`,
  Cargo `license`).
- **Selling GPL software is allowed** (many Blender add-ons are sold this way). Buyers get the source and
  may pass it on, so people pay for the ready package, updates and support. Open source and sold = the GPL
  model.
- **Closed source** is only possible without Blender: Option C (standalone Cycles is Apache-2.0; its
  dependencies OIDN, Embree, OIIO, OpenEXR, OCIO, TBB are permissive).
- **"Blender" is a trademark:** "powered by Blender Cycles" is fine; not in the product name or logo.
- **Selling channels:** SketchUp Extension Warehouse (Trimble review, signing, their licensing API) or
  selling the `.rbz` directly (Gumroad, own site), possibly with a free version on Extension Warehouse.
