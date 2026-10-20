# One render: export (or reuse), then the launcher runs Blender; progress comes back via files.
module TrichoRendr
  def self.persist_settings(req)
    s = settings.merge(req.slice(*DEFAULTS.keys))
    s['width'] = s['width'].to_i.clamp(320, 7680)
    s['height'] = s['height'].to_i.positive? ? s['height'].to_i.clamp(240, 7680) : 0
    s['samples'] = s['samples'].to_i.clamp(1, 4096)
    s['mode'] = 'view' unless s['mode'] == 'scenes'
    s['look'] = clean_look(req['look'] || s['look'])
    s['words'] = clean_words(req['words'] || s['words'])
    s['presets'] = clean_presets(req['presets'] || s['presets'])
    # ascii_only: SketchUp's defaults store may mangle non-ASCII words like "bazén"
    Sketchup.write_default('TrichoRendr', 'settings', JSON.generate(s, ascii_only: true))
    s
  end

  # Start button. req: settings + mode ('view' | 'scenes'), scenes (names), folder.
  def self.start(req)
    return if @busy

    s = persist_settings(req)
    push(settings: s)
    return render(s) if s['mode'] == 'view'

    model = Sketchup.active_model
    names = Array(req['scenes']) & model.pages.map(&:name)
    return fail_with('Pick at least one scene.') if names.empty?

    folder = req['folder'].to_s.empty? ? @state[:folder] : req['folder']
    start_batch(s, names, folder)
  end

  # One render of the current view. on_finish.(:done | :cancelled | :failed) when it ends.
  def self.render(s, &on_finish)
    @on_finish = on_finish
    return fail_with('TrichoRendr is not installed completely (tricho_rendr.exe is missing). Install it again.') unless File.exist?(EXE)

    exe = blender or return fail_with('Blender is not installed. Install Blender 5 from blender.org, then render again.')
    major = exe[/Blender (\d+)\.\d+/, 1] # checked before the export: that can take a minute
    return fail_with("Blender #{major} is too old. Install Blender 5 or newer from blender.org.") if major && major.to_i < 5

    cmd = [EXE, JOB, exe, CYCLES_PY]

    model = Sketchup.active_model
    view = model.active_view
    cam = view.camera
    aspect = if s['height'].positive? then s['width'].to_f / s['height']
             elsif cam.aspect_ratio.positive? then cam.aspect_ratio
             else view.vpwidth.to_f / view.vpheight
             end
    vfov = cam.perspective? ? cam.fov : 35.0
    vfov = Math.atan(Math.tan(vfov.degrees / 2) / aspect).radians * 2 if cam.perspective? && !cam.fov_is_height?
    sun = model.shadow_info['SunDirection']
    frame = {
      width: s['width'], height: s['height'].positive? ? s['height'] : (s['width'] / aspect).round, vfov: vfov, samples: s['samples'],
      ortho: cam.perspective? ? nil : cam.height * 0.0254, # Parallel Projection: view height in meters
      eye: cam.eye.to_a, target: cam.target.to_a, up: cam.up.to_a, # inches
      sun: sun.z > 0 ? sun.to_a : nil, look: s['look'], words: s['words'], batch: !@batch.nil?
    }

    @busy = true
    @cancelled = false
    @steps = 3 # export, Blender builds the scene, render
    @started = now
    push(busy: true, error: nil, pct: nil, eta: nil, render: nil, status: 'Starting…')
    FileUtils.mkdir_p(JOB)
    old = Dir.glob(File.join(JOB, '*.{png,txt}')) + %w[scene.json cancel].map { |f| File.join(JOB, f) }
    old.each { |f| FileUtils.rm_f(f) } # bins + export.json stay for reuse

    vis = visibility(model)
    key = export_key(model, vis)
    go = lambda do |stats|
      @export_s = now - @started
      @job = { width: frame[:width], height: frame[:height], samples: frame[:samples], batch: frame[:batch],
               triangles: stats[:triangles].to_i, faceme: Array(stats[:faceme]).size }
      File.write(File.join(JOB, 'scene.json'), JSON.generate(frame.merge(stats)))
      push(status: 'Step 2/3 · Starting Blender…', pct: nil, eta: nil)
      launch(cmd)
    end
    unless key == @export_key && @stats
      @stats = saved_export(model, vis) # unchanged .skp exported in an earlier session?
      @export_key = @stats && key
    end
    @reused = key == @export_key && @stats
    log("render: settings=#{s.except('words', 'presets').inspect} frame=#{frame.except(:eye, :target, :up, :words).inspect} " \
        "page=#{model.pages.selected_page&.name.inspect} edits=#{edits} visibility=#{key[2][0, 8]} " \
        "reuse=#{@reused ? true : false}")
    return go.call(@stats) if @reused # nothing changed: skip the export

    @export_key = nil # the bins get overwritten; only a finished export is reusable
    FileUtils.rm_f(EXPORT_JSON)
    saved = saved_key(model, vis) # taken before the export: edits made meanwhile make it stale
    @exporter = Exporter.new(model, JOB)
    @exporter.start(->(text, pct, eta) { push(status: "Step 1/#{@steps} · #{text}", pct: pct, eta: eta) }) do |stats|
      @exporter = nil
      @stats = stats
      @export_key = key
      File.write(EXPORT_JSON, JSON.generate(key: saved, stats: stats)) if saved && saved == saved_key(model)
      go.call(stats)
    end
  end

  def self.finish(result)
    f = @on_finish
    @on_finish = nil
    f&.call(result)
  end

  def self.launch(cmd)
    logfile = File.join(JOB, 'log.txt')
    @pid = Process.spawn(*cmd, [:out, :err] => [logfile, 'w'])
    log("launch: pid=#{@pid} #{cmd.inspect}")
    @timer = UI.start_timer(0.5, true) do
      guard do
        exited = Process.waitpid(@pid, Process::WNOHANG)
        # launcher output + Blender's own log; either may be locked mid-write
        text = %w[log.txt blender.txt].map { |f| File.read(File.join(JOB, f)) rescue '' }.join("\n").scrub
        image = exited ? File.join(JOB, 'render.png') : Dir.glob(File.join(JOB, 'pass_*.png')).max
        push(render: "file:///#{image}?#{File.mtime(image).to_f}") if image && File.exist?(image)
        status = text.scan(/^TR: (.*)$/).flatten.last
        pct, eta = text.scan(/^TR_PROGRESS (\S+) (\S+)$/).last&.map(&:to_f)
        if !exited
          push(status: status || "Step 2/#{@steps} · Starting Blender…",
               pct: pct && pct >= 0 ? pct : nil, eta: eta && eta >= 0 ? eta : nil)
        else
          UI.stop_timer(@timer)
          @pid = nil
          @busy = false
          ok = $?.success?
          log("launch: exited #{$?.inspect} after #{(now - @started).round(1)} s, cancelled=#{@cancelled}")
          log("launch: log tail:\n#{text[-1500..] || text}") unless ok
          export = @reused ? 'export reused' : "export #{@export_s.round} s"
          if ok
            push(busy: false, pct: 100, eta: nil, status: "Done in #{(now - @started).round} s (#{export})")
          elsif @cancelled
            push(busy: false, pct: nil, eta: nil, status: 'Cancelled')
          else
            what, todo = PROBLEMS.find { |re, _, _| text.match?(re) }&.drop(1) || FAILED
            push(busy: false, pct: nil, eta: nil, status: "Render failed: #{what}", error: problem(what, todo, text))
          end
          result = ok ? :done : (@cancelled ? :cancelled : :failed)
          count_render(result, @job, now - @started)
          keep_logs(result)
          finish(result)
        end
      end
    end
  end

  def self.cancel
    log("cancel: busy=#{@busy ? true : false} exporting=#{!@exporter.nil?} batch=#{!@batch.nil?}")
    return unless @busy

    @cancelled = true
    @batch[:cancelled] = true if @batch
    if @exporter
      @exporter.cancel
      @exporter = nil
      @busy = false
      push(busy: false, pct: nil, eta: nil, status: 'Cancelled')
      finish(:cancelled)
    elsif @pid
      File.write(File.join(JOB, 'cancel'), '') # the launcher stops Blender
    end # else: a batch is switching scenes; wait_for_scene sees the flag
  end

  # Known failures in plain words: [pattern in the launcher + Blender log, what happened, what to do].
  # First match wins, so the graphics card comes before the general out-of-memory line.
  PROBLEMS = [
    [/(CUDA|OptiX|HIP|GPU|device)[^\n]*out of memory|out of (GPU|device) memory|cuMemAlloc|OPTIX_ERROR_\w*MEMORY|out of GPU/i,
     'The graphics card ran out of memory.',
     'Render a smaller size, hide big parts the camera does not see (tags), or close other programs that use the graphics card.'],
    [/MemoryError|Unable to allocate|bad_alloc|out of memory/i,
     'The computer ran out of memory.',
     'Close other programs or render a smaller size. Very big models need a lot of memory.'],
    [/No space left on device|Errno 28|not enough space on the disk/i,
     'The disk is full.',
     'Free some space on drive C:, then render again.'],
    [/EXCEPTION_ACCESS_VIOLATION|0xc0000005|Segmentation fault/i,
     'Blender crashed.',
     'This is often the graphics driver: update it, restart the computer and try again.'],
    [/os error \d+|Os \{ code/, # the launcher's spawn error (Rust prints main's error with Debug)
     'Blender could not be started.',
     'Install Blender 5 again from blender.org, into its default folder.'],
    [/Traceback \(most recent call last\)/,
     'Blender could not build this model.',
     'Another view or model may still work. Please copy the details and send them, so it can be fixed.']
  ].freeze
  FAILED = ['The render failed.', 'Try again. If it keeps failing, copy the details and send them, so it can be fixed.'].freeze

  # The window's error box: plain words, plus details to copy and send (versions, render, log tail).
  def self.problem(what, todo, log_text)
    head = "TrichoRendr #{Sketchup.extensions['TrichoRendr']&.version} · SketchUp #{Sketchup.version} · #{blender}"
    { what: what, todo: todo,
      details: [what, head, "Render: #{@job.inspect}", "Logs: #{LOG_DIR}", log_text[-3000..] || log_text].join("\n\n") }
  end

  # Every render's launcher and Blender output and its scene.json (settings and model numbers, no geometry).
  def self.keep_logs(result)
    dir = File.join(LOG_DIR, "#{Time.now.strftime('%Y-%m-%d %H%M%S')} render #{result}")
    FileUtils.mkdir_p(dir)
    %w[log.txt blender.txt scene.json].each do |f|
      FileUtils.cp(File.join(JOB, f), dir) if File.exist?(File.join(JOB, f))
    end
    prune_logs
  rescue StandardError => e
    log("keep_logs: #{e.class}: #{e.message}") # logs must never break a render
  end

  def self.open_logs
    FileUtils.mkdir_p(LOG_DIR)
    UI.openURL("file:///#{LOG_DIR}")
  end

  def self.fail_with(msg)
    @busy = false
    push(status: msg, busy: false)
    finish(:failed)
    nil
  end
end
