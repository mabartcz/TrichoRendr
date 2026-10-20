# CLAUDE.md

TrichoRendr: a SketchUp extension that renders the current view or a batch of scenes with Blender Cycles.
Built for a landscape architect (Czech; material names are often Czech, sometimes Russian): she needs nice
water, glass, shadows, light, textures and 2D face-me PNG trees, not photo-realism. The owner (Martin)
programs Python and Rust; Ruby only because SketchUp requires it.

Read `docs/ARCHITECTURE.md` before changing how the parts talk (job folder format, progress protocol,
export reuse, look settings).
`docs/DISTRIBUTION.md` has the decisions on shipping Blender, standalone Cycles and licensing (users
install Blender themselves for now).

## Layout

- `plugin/tricho_rendr.rb` loader (extension name + **version**, must equal the Cargo workspace version;
  `cargo xtask lint` checks it). `plugin/tricho_rendr/`: Ruby by topic (`config`, `exporter`, `observers`,
  `settings`, `render`, `batch`, `dialog`, `main`), `blender/cycles.py`, `ui/window.{html,css,js}`,
  `images/icon.svg`, `bin/` (built launcher, gitignored).
- `launcher/`: Rust crate `tricho_rendr` = `tricho_rendr.exe <job> <blender.exe> <cycles.py>`; hides
  Blender's console, polls `<job>/cancel`.
- `xtask/`: all project tasks. `tests/fixtures/make_job.py`: generated test job. `tools/look_variants.py`:
  look tuning against the last real job. `docs/`: architecture, research, distribution, README images.

## Commands

`cargo xtask build | install | package | lint | fmt | test | smoke | ci | clean` (`make <task>` too).
After changing plugin files: `cargo xtask install`, then the user restarts SketchUp (no hot reload).
`cargo xtask smoke` needs Blender; it is the fastest end-to-end check of `cycles.py` (~10 s).

## Environment facts

- Windows 10, SketchUp 2026 (Ruby 3.2.2, CEF 137 HtmlDialog), Blender 5.1 at
  `C:\Program Files\Blender Foundation\Blender 5.1`, GTX 1060 6 GB (Pascal: OptiX works, CUDA 13 doesn't).
- Installed plugin: `%APPDATA%\SketchUp\SketchUp 2026\SketchUp\Plugins\tricho_rendr\`.
- **No Ruby, rubocop or ruff on this machine.** Ruby can't be run locally: edit it with extreme care (a
  syntax error disables the whole extension; it happened once). CI runs `ruby -wc` + rubocop and ruff.
  `node --check plugin/tricho_rendr/ui/window.js` works locally for the JS.
- Shell: heredocs with quotes and backticks break easily in this Bash; for multi-line edits write a Python
  script with the Write tool and run it with `python -I`.

## Debugging

- Logs: `%LOCALAPPDATA%\TrichoRendr\logs\` (window: Open logs folder; max 10 MB, oldest deleted first).
  `plugin.log` = this SketchUp session (every push to the window, JS errors `js: error`, export timings,
  launches); `<date> session.log` = earlier sessions; `<date> render <result>\` = each render's `blender.txt`,
  `log.txt`, `scene.json`. On a user's PC: ask them to zip the folder and send it.
- Last job: `%TEMP%\TrichoRendr\` (`scene.json`, bins, `blender.txt`, `render.png`). Re-run Blender on it
  directly: `blender -b --factory-startup --python plugin/tricho_rendr/blender/cycles.py -- <job>`
  (`TR_SAMPLES=4` for speed). Copy the bins first if the user may render meanwhile.
- The window page can be opened in the browser pane (`.claude/launch.json` serves `plugin/tricho_rendr/ui`)
  with a stub `window.sketchup = {log(){}, ready(){}, start(j){}, …}` and a hand-made `update({...})`.

## SketchUp rules that bit us

- All API calls on the main thread; long work = Fiber + `UI.start_timer` slices. Never yield inside a
  SketchUp iterator (iterate `.to_a`).
- A closed `UI::HtmlDialog` loses its action callbacks: create a new dialog each time the window opens.
- `view.write_image` fires `onViewChanged`: ignore view events around snapshots (`@ignore_view_until`).
- Face-me component transforms are stale in SketchUp 2024+: the renderer turns them to the camera.
- Selecting a page animates the camera: `wait_for_scene` waits until the view matches `page.camera`.
- Errors in callbacks/timers are silent: wrap entry points in `TrichoRendr.guard`.

## Conventions

- Keep it simple: the smallest change that works, no speculative options. Comments explain why, not what.
- A new look setting goes in three places (see ARCHITECTURE.md › Look settings).
- User-facing text is plain English for a non-programmer; the window must never show a console or freeze.
- Bump the version in both `Cargo.toml` (workspace) and `plugin/tricho_rendr.rb`, and add a CHANGELOG entry.
- Release: after that commit, `git tag v<version>` + `git push --tags`; `.github/workflows/release.yml` builds the
  `.rbz` and publishes it with that version's `## <version>` CHANGELOG section as notes.
