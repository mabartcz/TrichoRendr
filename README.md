<p align="center">
  <img src="plugin/tricho_rendr/images/icon.svg" width="128" alt="TrichoRendr logo">
</p>

<h1 align="center">TrichoRendr</h1>

<p align="center">
  <a href="https://github.com/mabartcz/TrichoRendr/actions/workflows/ci.yml"><img src="https://github.com/mabartcz/TrichoRendr/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/dynamic/toml?url=https://raw.githubusercontent.com/mabartcz/TrichoRendr/main/Cargo.toml&query=%24.workspace.package.version&label=version&color=4fb8cc" alt="version">
  <img src="https://img.shields.io/badge/SketchUp-2024%2B-005F9E?logo=sketchup&logoColor=white" alt="SketchUp 2024+">
  <img src="https://img.shields.io/badge/Blender_Cycles-5.0%2B-E87D0D?logo=blender&logoColor=white" alt="Blender 5.0+">
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4" alt="Windows 10 | 11">
  <br>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-e6c07b" alt="License: GPL-3.0-or-later"></a>
  <img src="https://img.shields.io/badge/Ruby-3.2-CC342D?logo=ruby&logoColor=white" alt="Ruby">
  <img src="https://img.shields.io/badge/Rust-launcher-000000?logo=rust&logoColor=white" alt="Rust">
  <img src="https://img.shields.io/badge/Python-Blender_script-3776AB?logo=python&logoColor=white" alt="Python">
  <a href="https://github.com/mabartcz/TrichoRendr/commits/main"><img src="https://img.shields.io/github/last-commit/mabartcz/TrichoRendr?color=a9b1b5" alt="last commit"></a>
</p>

<p align="center"><img src="docs/images/window.png" alt="The TrichoRendr window in SketchUp"></p>

Nice, simple renders of SketchUp models: sun and sky, water, glass, shadows, textures and 2D face-me trees.
Not photo-real on purpose: the look of a landscape architecture visualisation, in a few clicks. It replaces
Twilight Render, which no longer works in current SketchUp.

TrichoRendr is a SketchUp extension. The rendering is done by [Blender Cycles](https://www.blender.org/)
on the GPU, started in the background; you never see Blender.

## Requirements

- Windows 10/11, SketchUp 2024 or newer (built on SketchUp 2026)
- [Blender](https://www.blender.org/download/) 5.0 or newer in `C:\Program Files\Blender Foundation`, or set `BLENDER`
  to its `blender.exe` (built on 5.1; uses the 5.x sky and compositor)
- A GPU: NVIDIA (GTX 10xx and up, OptiX, else CUDA) or AMD (HIP), picked automatically; without one it
  renders on the CPU (slow). `TR_DEVICE=OPTIX|CUDA|HIP` forces one.

## Install

Download `tricho_rendr-<version>.rbz` (CI artifact or `cargo xtask package`), then in SketchUp:
**Extensions → Extension Manager → Install Extension** and pick the file. Restart SketchUp.

## Use

Click the **TrichoRendr** toolbar button (or **Extensions → TrichoRendr**). The window shows the current view.

- **Output tab:** render the current view or a batch of **Scenes**, the output folder, size (default
  3000 × 1300) and quality (samples). The Viewport tab shows exactly the frame that gets rendered.
- **Look tab:** presets (Airy day, Warm sunset, Blue hour, Soft plan, plus your own saved ones), sun and shadows, day, sunset or
  evening sky, haze in the distance, style (natural, soft, punchy, …), brightness, saturation, warmth, glow,
  lens flare (when the sun is in the picture), background (sky, white, or transparent PNG for Photoshop),
  water, glass, leaves, glowing materials. A dot marks what you changed; double-click a slider to reset it.
- **Materials tab:** which words in a material name mean water, glass or glowing (editable, saved in
  SketchUp), and what is found automatically: plans (Parallel Projection), PNG trees, face-me components.
- **Start render:** the image refines live with % and time left. **Save as…** writes a PNG. Batch renders
  are saved as `<scene>.png`; nothing is overwritten (`(2)`, `(3)`, …).

The sun position comes from SketchUp's **Shadows** settings. The first render of a model exports it (about
a minute for a big garden); after that, camera and look changes reuse the export.

### Materials are found by name

| Material name contains | Renders as |
|---|---|
| `voda`, `water`, `pool`, `bazén`, `jezírko`, `pond`, `potok`, … | water (refraction, ripples) |
| `sklo`, `glass`, `okno`, … (see-through only) or any see-through color | thin glass |
| `svit`, `lamp`, `osvětlení`, `oheň`, `glow` | glowing material |
| PNG texture with transparency | cut-out (trees, plants) |

Add your own words (e.g. `rybník`) on the **Materials** tab; part of a name is enough, case and accents
don't matter (`bazén` = `bazen`).

## Troubleshooting

- **Nothing happens / an error / render failed:** the window says what went wrong; **Copy details** or
  **Open logs folder** (`%LOCALAPPDATA%\TrichoRendr\logs`: the SketchUp sessions and every render's Blender log,
  at most 10 MB, oldest deleted first). Zip that folder to send it.
- **Old textures after editing an image:** delete `%TEMP%\TrichoRendr_tex`.

## Development

```
cargo xtask build      # launcher -> plugin/tricho_rendr/bin/
cargo xtask install    # build + copy into SketchUp's Plugins folder, then restart SketchUp
cargo xtask package    # dist/tricho_rendr-<version>.rbz
cargo xtask lint       # rustfmt, clippy, version check (+ ruff, rubocop when installed)
cargo xtask test       # Rust tests
cargo xtask smoke      # renders a generated test scene with Blender (end-to-end Blender side)
```

`make <task>` does the same. Needs Rust (stable). Optional: `pip install ruff`, `gem install rubocop`.
Layout, the job folder format and how the parts talk: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the
interactive walkthrough [docs/architecture.html](docs/architecture.html) (open it in a browser).
Background research: [docs/RESEARCH.md](docs/RESEARCH.md). Blender vs. standalone Cycles, bundling
and licensing: [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md). License: [GPL-3.0-or-later](LICENSE). Tuning the look against a real model:
`python tools/look_variants.py`.
