//! TrichoRendr launcher: runs Blender for one render job without a console window.
//!
//! `tricho_rendr <job dir> <blender.exe> <cycles.py>`
//!
//! SketchUp's Ruby can't start a console program hidden, so the plugin starts this small GUI-subsystem exe,
//! which starts Blender with `CREATE_NO_WINDOW`. Blender's output goes to `<job>/blender.txt` (the plugin
//! reads progress from it); creating `<job>/cancel` stops the render.
#![windows_subsystem = "windows"] // no console window popping up when SketchUp spawns us

use std::{
    error::Error,
    fs,
    path::Path,
    process::{Command, ExitStatus},
    thread,
    time::Duration,
};

/// How the run ended.
#[derive(Debug, PartialEq)]
enum Outcome {
    Finished(ExitStatus),
    Cancelled,
}

/// Runs `cmd` with its output in `<job>/blender.txt` until it exits or `<job>/cancel` appears.
fn run(job: &Path, mut cmd: Command) -> Result<Outcome, Box<dyn Error>> {
    let out = fs::File::create(job.join("blender.txt"))?;
    cmd.stdout(out.try_clone()?) // the clone shares the file offset, so both streams append in order
        .stderr(out);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.spawn()?;
    loop {
        if let Some(status) = child.try_wait()? {
            return Ok(Outcome::Finished(status));
        }
        if job.join("cancel").exists() {
            child.kill()?;
            child.wait()?;
            return Ok(Outcome::Cancelled);
        }
        thread::sleep(Duration::from_millis(200));
    }
}

fn blender(exe: &str, script: &str, job: &Path) -> Command {
    let mut cmd = Command::new(exe);
    cmd.args(["-b", "--factory-startup", "--python-exit-code", "1", "--python", script, "--"]).arg(job);
    cmd
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().collect();
    let [_, job, exe, script] = args.as_slice() else {
        return Err("usage: tricho_rendr <job dir> <blender.exe> <cycles.py>".into());
    };
    let job = Path::new(job);
    match run(job, blender(exe, script, job))? {
        Outcome::Finished(status) if status.success() => Ok(()),
        Outcome::Finished(status) => Err(format!("Blender failed ({status})").into()),
        Outcome::Cancelled => Err("cancelled".into()),
    }
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;

    fn job_dir(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("tricho_launcher_test_{name}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn cmd(script: &str) -> Command {
        let mut c = Command::new("cmd");
        c.args(["/C", script]);
        c
    }

    #[test]
    fn captures_output_and_exit_code() {
        let job = job_dir("exit");
        let outcome = run(&job, cmd("echo TR: hello & exit 3")).unwrap();
        let Outcome::Finished(status) = outcome else { panic!("{outcome:?}") };
        assert_eq!(status.code(), Some(3));
        assert!(fs::read_to_string(job.join("blender.txt")).unwrap().contains("TR: hello"));
    }

    #[test]
    fn cancel_file_stops_the_child() {
        let job = job_dir("cancel");
        let flag = job.join("cancel");
        let t = std::time::Instant::now();
        let waiter = thread::spawn(move || {
            thread::sleep(Duration::from_millis(400));
            fs::write(flag, "").unwrap();
        });
        assert_eq!(run(&job, cmd("ping -n 30 127.0.0.1 >nul")).unwrap(), Outcome::Cancelled);
        waiter.join().unwrap();
        assert!(t.elapsed() < Duration::from_secs(10));
    }
}
