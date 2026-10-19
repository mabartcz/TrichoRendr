# Architecture

TrichoRendr is three small programs talking through a job folder. For an illustrated, interactive walkthrough
(3D basics, measured timings, why each part is built this way) open [architecture.html](architecture.html)
in a browser.

```
SketchUp (Ruby plugin)                 tricho_rendr.exe (Rust)            Blender (Python)
──────────────────────                 ───────────────────────            ────────────────
window (HtmlDialog) ─ Start ─┐
                             ▼
Exporter (Fiber, 0.1 s slices) ─ writes ─▶ %TEMP%\TrichoRendr\  (job folder)
                             │            scene.json, *.bin
                             └─ spawns ─▶ launcher ── CREATE_NO_WINDOW ─▶ blender -b --python cycles.py -- <job>
                                             │ polls <job>\cancel          │ builds the scene, renders passes
UI timer (0.5 s) ◀─ reads ── blender.txt ◀───┘ (stdout+stderr)  ◀─────────┘ TR: / TR_PROGRESS lines,
             └─ shows pass_N.png / render.png in the window                    pass_N.png, render.png
```

## Why it is split like this

- **SketchUp's Ruby runs on the UI thread and is not thread-safe.** Every API call must happen there, so the
  export is a `Fiber` that yields every `SLICE` (0.1 s) and is resumed from `UI.start_timer`. Never yield
  inside a SketchUp iterator (`entities.each`): iterate `entities.to_a` instead, the model can change while
  paused.
- **Ruby can't start a console program hidden.** `blender.exe` is a console app; started from SketchUp it
  pops a console window. The Rust launcher (`windows_subsystem = "windows"`) starts it with
  `CREATE_NO_WINDOW`, sends its output to `blender.txt` and kills it when `cancel` appears.
- **Blender Cycles does the rendering** (OptiX on NVIDIA, OIDN denoiser, AgX). CUDA 13 dropped Pascal, and
  the GTX 1060 this was built on has no ray-query support in wgpu, so a homemade GPU path tracer was out.

## Plugin files (`plugin/tricho_rendr/`)

| File | Role |
|---|---|
| `../tricho_rendr.rb` | SketchUp loader: registers the extension (name, version). |
| `main.rb` | Entry: requires the rest, adds the menu item and toolbar button. |
| `config.rb` | Paths, `LOOK` defaults/ranges/choices, `WORDS` (material names), `DEFAULTS`, `blender`, `log`. |
| `exporter.rb` | `Exporter`: model → job folder, sliced. |
| `observers.rb` | Edit counter (export reuse), view observer (live viewport snapshot), app observer (new/opened model). |
| `settings.rb` | Saved settings, `clean_look`, `clean_words`, export reuse keys, render statistics (`usage`, Stats tab; `%LOCALAPPDATA%\TrichoRendr\usage.json`, written after every render). |
| `render.rb` | `start` (Start button), `render` (one view), `launch` (progress polling), `cancel`. |
| `batch.rb` | Batch of scenes: switch scene, wait for the transition, render, save with a unique name. |
| `dialog.rb` | The window: `open`, `snapshot`, `push` (state → page), callbacks, `guard`. |
| `blender/cycles.py` | Runs inside Blender: job folder → Blender scene → progressive passes. |
| `ui/window.{html,css,js}` | The window page. Ruby calls `update(state)`; the page calls `sketchup.<name>`. |
| `bin/tricho_rendr.exe` | The launcher, built by `cargo xtask build` (not in git). |

## Job folder format

All little-endian. Positions are definition-local inches; transforms are SketchUp's column-major `to_a`.

| File | Content |
|---|---|
| `pos.bin` | f64 × 9 per triangle |
| `uv.bin` | f32 × 12 per triangle: front UVs (3 × u,v), then back UVs |
| `mat.bin` | i32 × 2 per triangle: front, back material index; −1 = inherit from the instance |
| `inst.bin` | 140 bytes per instance: u32 mesh, i32 material, i32 face-me index (−1 = none), f64 × 16 transform |
| `scene.json` | camera (`eye`, `target`, `up` in inches, `vfov` degrees, `ortho` view height in meters or null), `width`, `height`, `samples`, `sun` (direction or null), `look`, `words` (material name lists), `batch` (true = no preview passes), `materials` (`name`, sRGB `color`, `alpha`, `texture` path), `meshes` (`first`, `count` triangle ranges), `faceme` (world transforms) |
| `export.json` | Reuse key of the last export (see below) |
| `blender.txt` | Blender's output: progress lines + log |
| `pass_N.png`, `render.png` | Progressive passes and the final image |
| `cancel` | Created by the plugin to stop the render |

Each component definition is written once; instances reference it. Face-me components (2D trees) are not
pre-turned: SketchUp 2024+ keeps stale transforms for them, so the renderer turns each one about its blue
axis to face the camera (`face_camera` in `cycles.py`). Mirrored instances (det < 0) swap front/back.

`tests/fixtures/make_job.py` writes a small job in this format; `cargo xtask smoke` renders it.

## Progress protocol

`cycles.py` prints `TR: <status>` (shown in the window's status line) and `TR_PROGRESS <percent> <eta s>`
(−1 = unknown). The plugin parses the last of each from `blender.txt` every 0.5 s. Steps: 1/3 export
(plugin), 2/3 Blender builds the scene, 3/3 rendering passes (a 4-sample preview, 32 more when the setting
is above 64, then the full count; batch renders only the full count; persistent data keeps the BVH between
passes).

## Export reuse

The export takes about a minute on a big garden model (650k faces), so it is skipped when nothing changed:

- **In a session:** key = model, edit counter (`observers.rb`, ignores our own scene switches), visibility
  fingerprint (tags, tag folders, hidden objects), default face color. Camera and look are not in the key.
- **Across sessions:** `export.json` stores path, mtime and size of an unmodified `.skp` plus visibility.

Scenes that show the same tags/objects share one export in a batch.

## Look settings

One setting lives in three places; keep them in sync when adding one:

1. `config.rb`: `LOOK` (default), `LOOK_RANGES` or `LOOK_CHOICES` (validation in `clean_look`).
2. `ui/window.js`: `LOOK_UI` (label, range, step, unit; builds the Look tab).
3. `blender/cycles.py`: where it is used, via `LOOK.get(key, fallback)` / `pct(key, fallback)`.

Presets (`PRESETS` in `window.js`) set every Look key (`MOOD`, built from `LOOK_UI`); a key a built-in preset
leaves out takes the value of `BASIC` (the tuned look; the slider defaults are neutral: 100 %, 0 EV). Haze is a compositor mix toward a fixed color
per time of day, driven by the (denoised) mist pass; it is off for plans.

## Material rules (cycles.py, by SketchUp material name, case-insensitive)

A material is special when its name **contains** one of the words, ignoring case and accents (both are
lower-cased and stripped of diacritics with NFD, so `bazén` = `bazen`) (plain substring: `_`, digits
and compound names like `Voda_bazén2` must match; a word-boundary regex was tried and lost real materials
such as `[Translucent_Glass_Sky_Reflection]`). The lists are edited on the window's Materials tab and sent as
`words` in `scene.json`; defaults live in `config.rb` `WORDS` and, for jobs without `words`, in `cycles.py`.

- Water (default words `water`, `voda`, `вода`, `vodn`, `pool`, `bazén`, `jezír`, `pond`,
  `lake`, `river`, `potok`): checked first, also for textured materials.
- Glass (`glass`, `glas`, `sklo`, `sklen`, `skleněný`, `okno`, `steklo`, `стекло`, `vidro`): only with opacity < 100 %. Any
  untextured material with opacity < 100 % is glass anyway; the words make textured ones glass too.
- Glowing (`glow`, `emit`, `svit`, `lamp`, `lampa`, `osvětlení`, `oheň`).
- Textured PNGs with alpha are cut out (plants); `Sun through leaves` adds translucency to them.
