//! Project tasks: `cargo xtask <task>` (also behind `make`). See README.md › Development.

use std::{
    env,
    error::Error,
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::Command,
};

type Result<T = ()> = std::result::Result<T, Box<dyn Error>>;

const HELP: &str = "\
usage: cargo xtask <task>

  build     release launcher -> plugin/tricho_rendr/bin/tricho_rendr.exe
  install   build, then copy the plugin into SketchUp's Plugins folder (newest SketchUp,
            or the folder in SKETCHUP_PLUGINS); restart SketchUp afterwards
  package   build, then write dist/tricho_rendr-<version>.rbz (Extension Manager > Install)
  lint      rustfmt check, clippy, version check, ruff and rubocop when installed
  fmt       format Rust (and Python with ruff when installed)
  test      cargo test
  smoke     render tests/fixtures (generated) with Blender: the whole Blender side end to end
  ci        lint + test (what CI runs, minus the jobs that need Ruby/Python tools)
  clean     remove dist/, the built launcher in the plugin and target/
";

fn main() {
    let task = env::args().nth(1).unwrap_or_default();
    let result = match task.as_str() {
        "build" => build(),
        "install" => build().and_then(|()| install()),
        "package" => build().and_then(|()| package()),
        "lint" => lint(),
        "fmt" => fmt(),
        "test" => cargo(&["test", "--workspace"]),
        "smoke" => smoke(),
        "ci" => lint().and_then(|()| cargo(&["test", "--workspace"])),
        "clean" => clean(),
        _ => {
            print!("{HELP}");
            std::process::exit(i32::from(!task.is_empty() && task != "help"));
        }
    };
    if let Err(e) = result {
        eprintln!("xtask {task}: {e}");
        std::process::exit(1);
    }
}

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn plugin() -> PathBuf {
    root().join("plugin")
}

fn run(cmd: &mut Command) -> Result {
    eprintln!("> {cmd:?}");
    let status = cmd.status().map_err(|e| format!("{}: {e}", cmd.get_program().display()))?;
    if status.success() { Ok(()) } else { Err(format!("{} failed ({status})", cmd.get_program().display()).into()) }
}

fn cargo(args: &[&str]) -> Result {
    run(Command::new(env::var("CARGO").unwrap_or("cargo".into())).args(args).current_dir(root()))
}

/// Optional tool (ruff, rubocop): run it when installed, otherwise say so and carry on (CI has them).
fn optional(tool: &str, args: &[&str]) -> Result {
    if Command::new(tool).arg("--version").output().is_err() {
        eprintln!("- {tool} not installed, skipped (CI runs it)");
        return Ok(());
    }
    run(Command::new(tool).args(args).current_dir(root()))
}

fn clean() -> Result {
    for dir in [root().join("dist"), plugin().join("tricho_rendr/bin")] {
        if dir.exists() {
            fs::remove_dir_all(&dir)?;
        }
    }
    cargo(&["clean"])
}

fn build() -> Result {
    cargo(&["build", "--release", "-p", "tricho_rendr"])?;
    let exe = if cfg!(windows) { "tricho_rendr.exe" } else { "tricho_rendr" };
    let bin = plugin().join("tricho_rendr/bin");
    fs::create_dir_all(&bin)?;
    fs::copy(root().join("target/release").join(exe), bin.join(exe))?;
    eprintln!("built {}", bin.join(exe).display());
    Ok(())
}

/// SketchUp's user Plugins folder: SKETCHUP_PLUGINS, else the newest %APPDATA%\SketchUp\SketchUp <year>.
fn plugins_dir() -> Result<PathBuf> {
    if let Ok(dir) = env::var("SKETCHUP_PLUGINS") {
        return Ok(dir.into());
    }
    let base = PathBuf::from(env::var("APPDATA")?).join("SketchUp");
    let newest = fs::read_dir(&base)?
        .filter_map(|e| e.ok()?.file_name().into_string().ok())
        .filter(|n| n.starts_with("SketchUp 20"))
        .max()
        .ok_or_else(|| format!("no SketchUp found in {}", base.display()))?;
    Ok(base.join(newest).join("SketchUp/Plugins"))
}

fn install() -> Result {
    let dest = plugins_dir()?;
    let folder = dest.join("tricho_rendr");
    // Our own folder: drop files that no longer exist in the repo. While SketchUp runs it may hold the
    // folder (or a file) open, so remove what we can and let copy_tree overwrite the rest.
    if let Ok(entries) = fs::read_dir(&folder) {
        for e in entries.flatten() {
            let p = e.path();
            let _ = if p.is_dir() { fs::remove_dir_all(&p) } else { fs::remove_file(&p) };
        }
    }
    copy_tree(&plugin().join("tricho_rendr"), &folder)?;
    fs::copy(plugin().join("tricho_rendr.rb"), dest.join("tricho_rendr.rb"))?;
    eprintln!("installed to {}; restart SketchUp", dest.display());
    Ok(())
}

fn copy_tree(from: &Path, to: &Path) -> Result {
    fs::create_dir_all(to)?;
    for e in fs::read_dir(from)? {
        let e = e?;
        let target = to.join(e.file_name());
        if e.file_type()?.is_dir() {
            copy_tree(&e.path(), &target)?;
        } else if !skipped(&e.path()) {
            copy_retrying(&e.path(), &target)?;
        }
    }
    Ok(())
}

/// A running SketchUp (its web helper reading the window files) can lock a file for a moment.
fn copy_retrying(from: &Path, to: &Path) -> Result {
    for attempt in 1.. {
        match fs::copy(from, to) {
            Ok(_) => return Ok(()),
            Err(e) if attempt < 5 => {
                eprintln!("- {} busy ({e}), retrying", to.display());
                std::thread::sleep(std::time::Duration::from_millis(400));
            }
            Err(e) => return Err(format!("{}: {e}", to.display()).into()),
        }
    }
    unreachable!()
}

/// Files that never ship: Python caches and editor droppings.
fn skipped(path: &Path) -> bool {
    path.components().any(|c| c.as_os_str() == "__pycache__")
        || path.extension().is_some_and(|x| x == "pyc")
        || path.file_name().is_some_and(|n| n == ".gitkeep")
}

/// The extension version lives in the loader (SketchUp shows it); it must match the workspace version.
fn plugin_version() -> Result<String> {
    let loader = fs::read_to_string(plugin().join("tricho_rendr.rb"))?;
    let v = loader
        .lines()
        .find_map(|l| l.trim().strip_prefix("ext.version = '")?.strip_suffix('\''))
        .ok_or("no ext.version in plugin/tricho_rendr.rb")?;
    if v != env!("CARGO_PKG_VERSION") {
        return Err(format!("plugin version {v} != Cargo workspace version {}", env!("CARGO_PKG_VERSION")).into());
    }
    Ok(v.to_string())
}

fn package() -> Result {
    let version = plugin_version()?;
    let dist = root().join("dist");
    fs::create_dir_all(&dist)?;
    let path = dist.join(format!("tricho_rendr-{version}.rbz"));
    let mut zip = zip::ZipWriter::new(fs::File::create(&path)?);
    let opts = zip::write::SimpleFileOptions::default();
    let base = plugin();
    let mut files = vec![base.join("tricho_rendr.rb")];
    collect(&base.join("tricho_rendr"), &mut files)?;
    for f in files {
        let name = f.strip_prefix(&base)?.to_string_lossy().replace('\\', "/");
        zip.start_file(name, opts)?;
        zip.write_all(&fs::read(&f)?)?;
    }
    // The GPL wants its text shipped with every copy.
    zip.start_file("tricho_rendr/LICENSE", opts)?;
    zip.write_all(&fs::read(root().join("LICENSE"))?)?;
    zip.finish()?;
    eprintln!("packaged {}", path.display());
    Ok(())
}

fn collect(dir: &Path, out: &mut Vec<PathBuf>) -> Result {
    for e in fs::read_dir(dir)? {
        let p = e?.path();
        if p.is_dir() {
            collect(&p, out)?;
        } else if !skipped(&p) {
            out.push(p);
        }
    }
    Ok(())
}

fn lint() -> Result {
    cargo(&["fmt", "--all", "--check"])?;
    cargo(&["clippy", "--workspace", "--all-targets", "--", "-D", "warnings"])?;
    plugin_version()?;
    optional("ruff", &["check", "."])?;
    optional("ruff", &["format", "--check", "."])?;
    optional("rubocop", &["plugin"])
}

fn fmt() -> Result {
    cargo(&["fmt", "--all"])?;
    optional("ruff", &["format", "."])
}

/// Newest Blender in Program Files, or BLENDER.
fn blender() -> Result<PathBuf> {
    if let Ok(b) = env::var("BLENDER") {
        return Ok(b.into());
    }
    let base = Path::new(r"C:\Program Files\Blender Foundation");
    let mut found: Vec<(Vec<u32>, PathBuf)> = fs::read_dir(base)?
        .filter_map(|e| {
            let name = e.ok()?.file_name().into_string().ok()?;
            let version = name
                .strip_prefix("Blender ")?
                .split('.')
                .map(str::parse)
                .collect::<std::result::Result<_, _>>()
                .ok()?;
            Some((version, base.join(name).join("blender.exe")))
        })
        .collect();
    found.sort();
    found.pop().map(|(_, p)| p).ok_or_else(|| format!("no Blender in {}; set BLENDER", base.display()).into())
}

/// Generates the fixture job with Blender's own Python (no system Python needed), renders it with the
/// shipped cycles.py, and checks that render.png came out.
fn smoke() -> Result {
    let blender = blender()?;
    let job = root().join("target/smoke");
    let _ = fs::remove_dir_all(&job);
    fs::create_dir_all(&job)?;
    let py = |script: PathBuf| {
        let mut c = Command::new(&blender);
        c.args(["-b", "--factory-startup", "--python-exit-code", "1", "--python"]).arg(script).arg("--").arg(&job);
        c
    };
    run(&mut py(root().join("tests/fixtures/make_job.py")))?;
    run(py(plugin().join("tricho_rendr/blender/cycles.py")).env("TR_SAMPLES", "8"))?;
    let png = job.join("render.png");
    if !png.exists() {
        return Err(format!("no {}", png.display()).into());
    }
    eprintln!("smoke ok: {}", png.display());
    Ok(())
}
