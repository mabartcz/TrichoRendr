# Roadmap and feature ideas

From a survey of other SketchUp renderers and forum threads (SketchUp forum, SketchUcation, vendor forums;
October 2026). Not promises: a list to pick from. Effort assumes Blender Cycles as the backend.

## What users want (forums, most frequent first)

1. **Free or one-time price.** Subscriptions (Enscape ~$600/yr, Lumion ~$1000+/yr) for occasional use are the
   top complaint; Twilight's ~€100 lifetime licence is the benchmark. *We: free.*
2. **Simple, few settings.** "As easy as Twilight was." Rayscaper (also Cycles inside SketchUp, ~$200, where
   most Twilight users went) is criticised for too many options. *We: presets, plain English.*
3. **Runs on modest GPUs / CPU.** D5 and Lumion need RTX; laptops can't. *We: GTX 10xx works, CPU fallback.*
4. **Colours as picked in SketchUp.** Twilight was praised for exact colours; Enscape/Twinmotion drift,
   Twinmotion loses materials on re-sync. *We: check with a side-by-side swatch test (AgX, warmth).*
5. **Grass and vegetation.** Grass "isn't feasible" in SketchUp, people paste it in Photoshop or buy Skatter.
   Enscape's "material named grass becomes 3D grass" is popular. *We: gap.*
6. **Sections and plans.** Enscape lights sections as if the building were whole, V-Ray hangs with sections.
   Plans need readable shadows. *We: gap (section planes are ignored).*
7. **Non-photo-real looks:** white model with soft shadows ("looks professional"), sketch, watercolour.
   *We: Soft plan preset; White model (clay) since 0.4.0.*
8. **Entourage:** people, cars, plants in a library.
9. **Consistent batches:** each scene's tags respected, same look across scenes. *We: tags yes; check that
   exposure is locked across a batch.*
10. **Water and glass that look right without tuning.** *We: by material name.*
11. **Night lighting** that is easy to find and adjust. *We: glowing materials slider.*
12. Seasons/weather (mostly vendor marketing, not forum asks), Mac support.

## Ideas, by value for a landscape architect

Effort: S = a day or less, M = a few days, L = weeks.

| Idea | Effort | Notes |
|---|---|---|
| ~~White model / clay render~~ | S | Done in 0.4.0. |
| Grass by material name (`tráva`, `trávník`, `grass`, `lawn`) | M | Short hair particles on those faces; or displacement as a cheap first step. Meadow variant later. |
| Seasons for PNG trees: summer / autumn / winter | S | Hue shift and thinning of leaf cut-outs; only Lumion has seasons. |
| 360° panorama | S | Cycles panoramic (equirectangular) camera. |
| HDRI sky with rotation (real clouds) | S | Blender's sky has no clouds; SketchUp 2025 Environments already store an HDRI to reuse. |
| Depth of field, focus at the SketchUp camera target | S | |
| Photoshop layers: material/object ID mask, depth pass | S | Collage post-production is common in landscape work. |
| Section planes cut the render, lit correctly, optional poché | M | Competitors are weak here. |
| Plan shadows with their own direction (not the real sun) | S–M | Readable site plans. |
| Outline / sketch look (Freestyle lines) | M | Diagrams. |
| PNG people (and cars) pack | S | Works like trees; the work is finding images with a usable licence. |
| PBR maps from SketchUp 2025 Photoreal Materials | M | Normal / roughness. |
| Material library: grass, paving, gravel, water types | M | |
| Volumetric fog / god rays | S–M | Slow renders. |
| Night sky with stars / moon | S | |
| LUT / colour grading | S | |
| Region render | S | |
| Render settings saved per scene | S | Podium has it. |
| Sun-study / time-lapse sequence | S–M | |
| Walkthrough video along scenes | M | Long render times. |
| Scatter / brush (ground cover, meadows) | M–L | |
| AI upscaler (render at half size) | M | Faster on old GPUs. |

**Not now:** 3D plant library, animated people, VR / web viewer, live viewport, AI "reimagine", weather
(rain, snow), GIS terrain, cloud sharing. Large, and not asked for in forums for stills.

## Competitors in short (2025–2026)

- **Enscape** (subscription): real-time, Chaos Cosmos assets, clouds, fog, video/360/VR, AI enhancer for people
  and plants, sketch and watercolour modes.
- **D5 Render** (free non-commercial, Pro $360/yr): path tracing, weather, HDRI, LUT, IES, scatter brush, AI
  planting design with plant schedule, AI materials from photos, 16K stills, video.
- **Twinmotion** (free for small firms): seasons and weather sliders, 62 growable trees, animated people and
  cars, path tracer, video/VR.
- **Lumion** (~$1000–1500/yr, Lumion View plugin in SketchUp): big nature library, seasons, ray-traced water,
  styles (sketch etc.), AI upscaler.
- **V-Ray 7** (Chaos): scatter, LightMix (relight after render), AI material and upscaler, Vantage live link.
- **Thea / Maxwell:** interactive region render, section planes as cuts, relight after render.
- **SU Podium:** HDRI, 45k component browser, settings per scene. **Brighter3D:** CPU, $175, 360° camera.
- **Rayscaper:** Cycles in SketchUp, ~$200 perpetual, live render window; the closest to us.
- **SketchUp itself:** 2025 Environments (HDRI) and Photoreal Materials; Diffusion (AI image from a snapshot).
- **Twilight Render:** discontinued; users liked its simplicity, exact colours, templates, batch scenes.

## Sources

Enscape: https://www.chaos.com/enscape/features, https://learn.enscape3d.com/blog/knowledgebase/rendering_styles ·
D5: https://forum.d5render.com/t/what-s-new-in-d5-render-2-11/60053 ·
Twinmotion: https://dev.epicgames.com/documentation/twinmotion/twinmotion-2025-1-preview-release-notes ·
Lumion: https://lumion.com/news/lumion-2025-release ·
V-Ray: https://www.chaos.com/press/chaos-launches-v-ray-7-for-sketchup-and-rhino ·
Maxwell: https://nextlimitsupport.atlassian.net/wiki/spaces/maxwell/pages/22691886/SketchUp+-+Version+History ·
SketchUp: https://help.sketchup.com/en/release-notes/sketchup-desktop-20260 ·
Forums: https://forums.sketchup.com/t/alternative-to-twilight-render/253878,
https://forums.sketchup.com/t/render-package-similar-to-twilight-render/280066,
https://forums.sketchup.com/t/rendering-solution-for-specific-needs/116043,
https://forums.sketchup.com/t/rendered-sections-and-axo-plans-v-ray-vs-enscape/155580,
https://community.sketchucation.com/topic/163513/rayscaper/47,
https://forums.sketchup.com/t/rayscaper-a-new-render-extension-for-sketchup/257875?page=2
