# Changelog

## 0.4.0

- Look: **White model (clay)**: everything white except water, glass, glowing materials and the outline of
  PNG trees, to show form, light and shadow. Also as the preset White model · clay, soft shadows.
- Released on GitHub (Releases page, `.rbz` download); licensed GPL-3.0-or-later.

## 0.3.1

- Graphics card fails to render (e.g. a driver too old for this Blender: "Invalid kernel image"): renders on the
  processor instead, slower, and says to update the driver.

## 0.3.0

- New logo: the caddisfly's (chrostík) stone home seen from its opening, a ring of stones around a lens.
- Stats tab: how many renders, time spent rendering, megapixels, light paths, triangles, trees and batch scenes. Counted on this PC only (`%LOCALAPPDATA%\TrichoRendr\usage.json`), nothing is sent anywhere.
- Errors in plain words: the graphics card or the computer ran out of memory, full disk, Blender crashed,
  could not start or is too old; what to do; Copy details (versions, render, log) to send. Blender's
  version is checked before the export.
- Logs kept in `%LOCALAPPDATA%\TrichoRendr\logs` (Open logs folder in the error box and on the Stats tab):
  earlier SketchUp sessions and every render's Blender log and settings, at most 10 MB, oldest deleted first.
- Look: sliders start neutral (100 %, Brightness 0 EV, Warmth 60); the former tuned defaults are the new Basic
  preset (Brightness 0.8 EV), which the other presets build on. Presets set every Look setting, also background
  and materials. Resolution: 640 px.
- Look: lens flare (halo, ghosts, sun beams) when the sun is in the picture.
- Look: presets Airy day, Warm sunset, Blue hour, Soft plan; Haze in the
  distance (mist pass); Evening sky (blue hour, no sun); Soft style (AgX Low Contrast).
- Look: the preset list shows which preset is active (or Custom settings); save your own named presets
  and delete them (built-in ones stay).
- Materials tab: the words that make a material water, glass or glowing can be edited and are saved;
  explains what else is found automatically (plans, PNG trees, face-me components).
- Material words ignore case and accents (`bazén` = `bazen`). New defaults: glass `okno`, `skleněný`;
  glowing `lampa`, `osvětlení`, `oheň`.
- Faster: the Blender scene builds ~25 % faster (pair lookup), batch renders skip preview passes, single
  renders do one 4-sample preview; the export skips texture coordinates for untextured faces.
- Batch: waits for the scene's field of view, projection and roll too; a scene that hides faces inside groups
  gets its own export.
- Save as… saves the batch image you are looking at, not always the last render.
- Settings are saved when changed, not only on Start. Opening another model updates the window.
- The window opens at once; the viewport snapshot comes after (seconds on big models) and is reused when
  the view hasn't changed since the last one.
- Big models (preview slower than 1 s): moving the camera shows a Refresh preview button instead of
  freezing SketchUp after every orbit.
- GPU: falls back from OptiX to CUDA/HIP automatically. `BLENDER` env var for a Blender elsewhere.
- Plain-colour materials use the exact sRGB conversion (dark colours slightly lighter).

## 0.2.0

- Project structure: Cargo workspace (launcher + xtask), plugin split by topic, window split into
  HTML/CSS/JS, CI, lint configs, `.rbz` packaging, generated test scene and Blender smoke test.
- Removed the CPU "Quick" preview renderer; the Rust exe is now only the Blender launcher.
- Look tab: sun, shadow softness, sky light, day/sunset, style, brightness, saturation, warmth, glow,
  background (sky / white / transparent), water color and ripples, glass reflections, sun through leaves,
  glowing materials.
- Batch render of scenes into a folder without overwriting; Parallel Projection (plans).
- Fixed: the window did nothing after it was closed and opened again.

## 0.1.0

- First working version: export with live progress, Blender Cycles render with progressive preview.
