# TrichoRendr: feasibility research

Date: 2026-10-15

## Verdict

**It's feasible.** Build it in two parts:

1. **A pure-Ruby SketchUp extension (`.rbz`).** It adds a menu and toolbar, exports the scene, launches the renderer and shows the result.
2. **A standalone `TrichoRendr.exe`** written in C++ and **CUDA 12.x**. It is a small progressive path tracer that writes a PNG.

Don't build a native Ruby C extension (`.so`). That approach is what killed Twilight. Twilight shipped a separate binary for each embedded Ruby version (its `init_twilight.rb` picks from `18/ 20/ 22/ 25/ 27/ 32/TwilightLibV2.so`). SketchUp has announced a move to **Ruby 3.4**, and every C extension will have to be rebuilt for it. A separate `.exe` only talks to SketchUp through files, so SketchUp upgrades don't break it. If the renderer crashes, SketchUp stays up.

## Your machine (checked)

| Item | Found | Note |
|---|---|---|
| GPU | GTX 1060 6GB (Pascal, sm_61) | Has no RT cores, so ray tracing runs in plain CUDA. That's fine for simple renders. |
| Driver | 536.99 (R535) | Update to the latest R580 driver. R580 is the last branch that supports Pascal. |
| Visual Studio | 2022 Community 17.12 | OK for building CUDA 12.x. |
| SketchUp | **not found** on this machine | Need to know which version you use (2025 or 2026?). |
| Twilight | Twilight Render 2024 installed | Useful as a reference for features. |

## Hard constraints and limitations

### GPU and CUDA
- **CUDA 13 removed Pascal (and Maxwell and Volta).** You must use **CUDA Toolkit 12.x**; 12.9 is the newest that still builds `sm_61`. Pin the version.
- **OptiX 9 needs a newer driver and gains little without RT cores.** OptiX 7/8 would work, but it adds a lot of boilerplate. A hand-written BVH (or the single-header `tinybvh`, MIT license) is simpler.
- **Optimus laptop:** CUDA always runs on the NVIDIA GPU, so you don't need to force the dGPU in Windows settings. If you used D3D or OpenGL instead, you'd have to.
- **Windows TDR (watchdog):** a GPU kernel running longer than about 2 s gets killed and the driver resets. Render progressively, one sample per pixel per kernel launch, so every launch stays short.
- **6 GB VRAM** is plenty for typical architectural models with 2D trees.
- **Denoising:** Intel Open Image Denoise (Apache-2.0) runs on the CPU. Its CUDA backend needs a newer GPU than Pascal, but CPU denoising of one frame takes about a second. Twilight already shipped OIDN.

### SketchUp Ruby API
- Embedded Ruby is **3.2** in SketchUp 2024–2026, with **3.4 announced**. Plain Ruby code isn't affected; only C extensions are.
- The **Live C API** gives read-only C access to the open model, but only through a Ruby C extension, which is the fragile route. You don't need it: Ruby is fast enough to export a scene.
- **Face-me (2D tree) bug:** in SketchUp 2024 and 2025 with the new graphics engine, `ComponentInstance#transformation` is **not updated** when the camera moves. This affects both the Ruby and C APIs. **Workaround:** compute the face-me rotation yourself at export time. Rotate each instance about its own blue (Z) axis so its front faces the render camera. This is only a few lines, and it's needed anyway because the render camera is the authority.
- **SketchUp has no native lights.** You have to define them yourself, for example as a component carrying a `TrichoRendr` attribute dictionary, or as a material flagged "emissive".
- **Units:** the API always works in inches internally. Convert to meters on export.
- **Running the `.exe`:** use `Process.spawn` + `Process.detach`, or `UI.openURL`. `system` would freeze SketchUp's UI. Check this early on your SketchUp version.
- **Distribution:** a `.rbz` (zip) can contain the `.exe`. Personal use works unsigned; set Extension Loading Policy to allow unsigned extensions. Extension Warehouse would require signing.

### Freebies from SketchUp 2025+
- **PBR materials** (2025.0): `Material#roughness_factor`, `#metallic_factor`, `#normal_texture`, `#roughness_texture`, `#metallic_texture`, `#ao_texture`, `#workflow`. Users edit "simple mats" in **SketchUp's own material editor**, so you don't need a custom material UI.
- **Environments / IBL** (2025.0): `Model#environments`, `Environment#write_hdr(path)`, `#rotation`, `#skydome_exposure`. This gives a free HDR sky for lighting.

## Ruby API reference (what the exporter uses)

| Need | API |
|---|---|
| Walk the scene | `Model#entities`, recursing into `Group#definition.entities` / `ComponentInstance#definition.entities`, multiplying `#transformation` |
| Visibility | `Drawingelement#visible?`, `#layer.visible?` (tags), `Model#pages.selected_page` |
| Triangles + UVs + normals | `Face#mesh(7)` → `Geom::PolygonMesh`: `#points`, `#polygons`, `#uv_at(i, true)`, `#normal_at` |
| Texture files incl. distorted/colorized | `Sketchup::TextureWriter#load(face, front)`, `#write_all(dir, false)`, plus `Face#get_UVHelper` |
| Material | `Material#color`, `#alpha`, `#use_alpha?`, `#texture` (`#image_rep`, `#width`, `#height`), PBR methods above |
| Material inheritance | A face with a `nil` material takes the material of its parent group/instance. Back faces use `Face#back_material`. |
| Face-me trees | `ComponentDefinition#behavior.always_face_camera?` (then compute your own rotation) |
| Camera | `View#camera`: `#eye`, `#target`, `#up`, `#fov`, `#fov_is_height?`, `#aspect_ratio`, `#perspective?` |
| Sun | `Model#shadow_info['SunDirection']`, `['Light']`, `['Dark']`, `['DisplayShadows']` |
| Sky / HDR | `Model#environments.current` → `#write_hdr`, `#rotation`, `#skydome_exposure` |
| Custom data (lights, settings) | `Entity#get_attribute` / `#set_attribute` (attribute dictionary `"TrichoRendr"`) |
| UI | `UI::Toolbar`, `UI.menu('Extensions')`, `UI::HtmlDialog` (CEF 137 in 2026) |
| Progress polling | `UI.start_timer(0.5, true) { ... }` |

## Proposed architecture

```
SketchUp  ──(Ruby .rbz)──►  %TEMP%\TrichoRendr\job\
   menu/toolbar               scene.json   camera, sun, sky, materials, lights, settings
   HtmlDialog settings        mesh.bin     float32 positions/normals/uvs + uint32 indices + material ids
   exporter                   tex\*.png    textures written by TextureWriter
   Process.spawn ──────────►  TrichoRendr.exe job\   (C++ + CUDA 12.x)
                                 build BVH → progressive path trace → OIDN → tonemap
                                 rewrites out.png every N samples + progress.txt
   HtmlDialog ◄── polls ─────  out.png / progress.txt
```

Renderer features, kept intentionally simple:
- Diffuse plus one GGX glossy lobe, driven by roughness/metallic. Texture colors and alpha.
- **Alpha-cutout textures**, needed for the 2D trees: the ray skips the hit when texture alpha is below 0.5.
- Sun (directional, small angular radius so shadows are soft), sky (simple gradient or the SketchUp HDR environment), emissive materials, point lights.
- Filmic/ACES tonemap, exposure, OIDN denoise, PNG output.
- Skipped on purpose: refraction/glass (alpha < 1 renders as simple transparency), caustics, motion blur, volumes, DOF. Add any of these only if you miss them.

Rough speed on a GTX 1060, as a guess until we measure: a 1920×1080 frame at 64 spp plus denoise should take tens of seconds for a typical house-with-trees model.

## Dependencies (all permissive, header-only or one DLL)
- CUDA Toolkit 12.9 (build only; users need just the driver)
- `stb_image` / `stb_image_write` (public domain): PNG/JPG/HDR textures and output
- `tinybvh` (MIT): BVH build. Optional; a ~150-line SAH BVH also works.
- Intel OIDN (Apache-2.0): denoise DLLs
- JSON: `nlohmann/json` single header (MIT)

## Milestones
1. **Exporter + minimal renderer:** geometry, base colors, sun + sky, face-me trees with alpha cutout → PNG. This proves the whole pipeline.
2. **Materials:** textures, roughness/metallic, emissive, point-light component.
3. **Polish:** OIDN, HtmlDialog with live preview and settings, render all Scenes (pages) in a batch.

## Open questions for you
1. Which SketchUp version do you use? It's not installed on this machine, and 2025+ gives free PBR materials and HDR skies.
2. Are your 2D trees face-me components with PNG alpha textures, or images with a cut-out outline?
3. How do you want to place lights: a "TrichoRendr light" component, or glowing materials (or both)?

## Visual reference: landscape studio visualisations, 2026-10

What published Czech landscape studio visualisations (competition and park projects) have in common:

- Airy daylight: pale, hazy sky; distant trees fade into the air; low contrast, slightly muted colors;
  soft, dappled shadows. -> style Soft (AgX Low Contrast), Haze, preset Airy day.
- Evening versions ("večer", "večerní režim"): blue-hour sky, warm lamps and lit windows. -> sky Evening
  (sun 6 degrees below the horizon, no sun lamp), preset Blue hour with stronger glowing materials.
- Warm, low-sun images with a soft glow. -> preset Warm sunset.
- Plans: light, flat colors, soft tree shadows on white. -> preset Soft plan (Parallel Projection already
  renders on white).

Their renders add people, fountains/mist and atmosphere in post; that stays in Photoshop.
Not done: lit interiors behind glass (needs interior lights; a glowing material named e.g. "svit" works).

## Sources
- [Blender manual: mist pass](https://docs.blender.org/manual/en/latest/render/layers/passes.html)
- [Blender manual: AgX looks / color management](https://docs.blender.org/manual/en/latest/render/color_management.html)
- [Blender manual: Sky texture](https://docs.blender.org/manual/en/latest/render/shader_nodes/textures/sky.html)
- [Twilight render replacement (SketchUp forum)](https://forums.sketchup.com/t/twilight-render-replacement/340311)
- [Does the now discontinued Twilight Render work with SU 2023?](https://forums.sketchup.com/t/does-the-now-discontinued-twilight-render-work-with-su-2023/258588)
- [Download Twilight Render to 2024 SketchUp Pro](https://forums.sketchup.com/t/download-twilight-render-to-2024-sketchup-pro/270895)
- [SketchUp Ruby API release notes](https://ruby.sketchup.com/file.ReleaseNotes.html)
- [Ruby API: Sketchup::Material](https://ruby.sketchup.com/Sketchup/Material.html)
- [Ruby API: Sketchup::Environment](https://ruby.sketchup.com/Sketchup/Environment.html)
- [Important – Upcoming Ruby Update (3.4)](https://forums.sketchup.com/t/important-upcoming-ruby-update/348793)
- [Exist this path when I install SketchUp? (ruby320 DLL)](https://forums.sketchup.com/t/exist-this-path-when-i-install-sketchup/340844)
- [SketchUp developer: NVIDIA CUDA](https://developer.sketchup.com/nvidiacuda)
- [SketchUp Live C API examples](https://github.com/SketchUp/sketchup-live-c-api)
- [SketchUp Ruby C extension examples](https://github.com/sketchup/ruby-c-extension-examples)
- [Transformation bug with always face camera](https://forums.sketchup.com/t/transformation-bug-with-always-face-camera/340417)
- [NVIDIA CUDA features archive (13.0 drops Maxwell/Pascal/Volta)](https://docs.nvidia.com/cuda/cuda-features-archive/index.html)
- [PyTorch notice: CUDA 13 drops Pascal](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432)
