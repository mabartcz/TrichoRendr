# The render window (HtmlDialog): state pushed to the page, callbacks from it, viewport snapshots.
module TrichoRendr
  # The extension button: open the window with an instant viewport preview and the settings.
  def self.open
    unless @app_watched
      @app_watched = true
      Sketchup.add_observer(AppWatch.new)
    end
    @state ||= { status: 'Ready', pct: nil, eta: nil, view: nil, render: nil, error: nil, busy: false, batch: nil }
    @folders ||= {}
    bind_model
    log("open: model=#{Sketchup.active_model.path.inspect} pages=#{@state[:pages].size} folder=#{@state[:folder]}")
    show_dialog # the viewport snapshot follows once the page is up ('ready'), so the window shows at once
  end

  def self.bind_model
    model = Sketchup.active_model
    return unless model

    unless (@watched ||= []).include?(model) # holds the models, so their object_ids stay unique
      @watched << model
      model.add_observer(Watch.new)
      model.active_view.add_observer(ViewWatch.new)
    end
    @state.merge!(version: Sketchup.extensions['TrichoRendr']&.version, settings: settings, look_defaults: LOOK,
                  words_defaults: WORDS, usage: usage, pages: model.pages.map(&:name),
                  current_page: model.pages.selected_page&.name,
                  folder: @folders[model.path] ||= default_folder(model))
  end

  def self.model_changed
    guard do
      if @state && !@busy
        @state.merge!(render: nil, batch: nil, error: nil, pct: nil, eta: nil, status: 'Ready')
        bind_model
        snapshot if @dialog&.visible?
      end
    end
  end

  # What the viewport snapshot depends on. Reopening the window with an unchanged view reuses the last
  # snapshot: write_image redraws the whole model offscreen and blocks SketchUp (4 s on a 3M-triangle garden).
  def self.view_key
    model = Sketchup.active_model
    view = model.active_view
    cam = view.camera
    si = model.shadow_info
    [model.object_id, edits, cam.eye.to_a, cam.target.to_a, cam.up.to_a, cam.perspective? ? cam.fov : cam.height,
     @frame || settings.values_at('width', 'height'), view.vpwidth, view.vpheight, model.layers.map(&:visible?),
     si['DisplayShadows'], si['ShadowTime'].to_i, model.styles.selected_style&.name]
  end

  def self.snapshot
    view = Sketchup.active_model.active_view
    @snapshot_key = view_key
    FileUtils.mkdir_p(VIEW_DIR)
    old = Dir.glob(File.join(VIEW_DIR, 'view_*')).sort
    old[0...-2].each { |f| File.delete(f) rescue nil } # keep the last two: the window may still be loading one
    path = File.join(VIEW_DIR, "view_#{(now * 1000).to_i}.jpg")
    # The preview has the render's shape: a fixed size like 3000x1300 shows the frame that gets rendered.
    fw, fh = @frame || settings.values_at('width', 'height')
    w = 1000
    h = (fh.to_i.positive? ? w * fh.to_f / fw : w * view.vpheight.to_f / view.vpwidth).round
    started = now
    @ignore_view_until = now + 1e9 # write_image redraws the view, which fires onViewChanged
    begin
      ok = view.write_image(filename: path, width: w, height: h, antialias: true, compression: 0.9)
    ensure
      @ignore_view_until = now + 0.5
    end
    took = now - started
    @snapshot_slow = took > 1.0 # write_image redraws the whole model: same ~4 s at any size on a big garden
    log("snapshot: #{w}x#{h} ok=#{ok} #{File.exist?(path) ? File.size(path) : 0} B in #{(took * 1000).round} ms")
    push(view: "file:///#{path}", view_stale: false, aspect: view.vpwidth.to_f / view.vpheight,
         current_page: Sketchup.active_model.pages.selected_page&.name)
  end

  def self.view_changed
    return unless @dialog&.visible?
    return if @batch || now < (@ignore_view_until || 0) # scene switching in a batch moves the view

    # Big model: don't freeze SketchUp after every orbit. Rendering: no snapshot now. The window offers Refresh.
    if @snapshot_slow || @busy
      push(view_stale: true) unless @state[:view_stale]
      return
    end

    @view_changed_at = now
    @view_timer ||= UI.start_timer(0.25, true) do
      guard do
        next if now - @view_changed_at < 0.4

        UI.stop_timer(@view_timer)
        @view_timer = nil
        snapshot
      end
    end
  end

  def self.save_as(pinned = nil)
    src = pinned.to_s.sub(%r{\Afile:///}, '').sub(/\?.*\z/, '')
    batch_image = !src.empty? && File.exist?(src)
    src = File.join(JOB, 'render.png') unless batch_image
    src = Dir.glob(File.join(JOB, 'pass_*.png')).max unless File.exist?(src)
    return unless src && File.exist?(src)

    model = Sketchup.active_model
    scene = batch_image ? File.basename(src, '.png') : model.pages.selected_page&.name # batch files are named after their scene
    name = [File.basename(model.path, '.skp'), scene].compact.reject(&:empty?).join('_')
    dir = model.path.empty? ? '' : File.dirname(model.path)
    path = UI.savepanel('Save render', dir, "#{name.empty? ? 'render' : name}.png") or return
    path += '.png' unless path.downcase.end_with?('.png')
    FileUtils.cp(src, path)
    push(status: "Saved #{path}")
  end

  def self.pick_folder
    dir = UI.select_directory(title: 'Save renders to', directory: @state[:folder])
    return unless dir

    @folders[Sketchup.active_model.path] = dir.tr('\\', '/')
    push(folder: @folders[Sketchup.active_model.path])
  end

  def self.open_folder
    FileUtils.mkdir_p(@state[:folder])
    UI.openURL("file:///#{@state[:folder]}")
  end

  def self.show_dialog
    if @dialog&.visible?
      @dialog.bring_to_front
      return log('dialog: already visible')
    end

    # A fresh dialog every time: SketchUp drops the action callbacks of a closed dialog, so a reopened
    # one would show the page but every button (and the ready/log calls) would go nowhere.
    @dialog = begin
      d = UI::HtmlDialog.new(dialog_title: 'TrichoRendr', preferences_key: 'TrichoRendr.window2',
                             width: 1400, height: 900, min_width: 900, min_height: 600, style: UI::HtmlDialog::STYLE_DIALOG)
      d.add_action_callback('ready') do
        log('dialog: ready')
        push({})
        # A moment later, so the page paints before the snapshot blocks SketchUp.
        UI.start_timer(0.05, false) do
          guard do
            last = @state[:view].to_s.delete_prefix('file:///')
            snapshot unless @snapshot_key == view_key && File.exist?(last)
          end
        end
      end
      d.add_action_callback('log') { |_, msg| log("js: #{msg}") }
      d.add_action_callback('start') do |_, json|
        log("dialog: start #{json}")
        guard { start(JSON.parse(json)) }
      end
      d.add_action_callback('cancel') { guard { cancel } }
      d.add_action_callback('save') { |_, file| guard { save_as(file) } }
      d.add_action_callback('refresh') { guard { snapshot } }
      d.add_action_callback('frame') do |_, json|
        guard do
          f = JSON.parse(json)
          @frame = [f['width'].to_i, f['height'].to_i]
          snapshot unless @busy
        end
      end
      d.add_action_callback('pick_folder') { guard { pick_folder } }
      d.add_action_callback('open_folder') { guard { open_folder } }
      d.add_action_callback('open_logs') { guard { open_logs } }
      d.add_action_callback('save_settings') do |_, json|
        guard { persist_settings(JSON.parse(json)) }
      end
      d.set_on_closed { cancel }
      d
    end
    @dialog.set_file(HTML)
    @dialog.show
    log("dialog: shown, visible=#{@dialog.visible?}")
    UI.start_timer(1.5, false) { push({}) } # in case the page missed earlier updates
  end

  def self.push(changes)
    changes = batch_view(changes)
    changed = changes.reject { |k, v| @state[k] == v || %i[pct eta batch].include?(k) }
    @state.merge!(changes)
    sent = @dialog&.visible? ? true : false
    @dialog.execute_script("update(#{JSON.generate(@state)})") if sent
    log("push: #{changed.inspect} sent=#{sent}") unless changed.empty?
  end

  # Errors in callbacks and timers only show up in the Ruby Console, so surface them.
  def self.guard
    yield
  rescue Exception => e
    @busy = false
    self.switching = false
    UI.stop_timer(@timer) if @timer
    msg = "#{e.class}: #{e.message}\n#{e.backtrace.first(8).join("\n")}"
    log("ERROR #{msg}")
    if @state
      push(busy: false, status: 'Something went wrong in TrichoRendr',
           error: problem('Something went wrong in TrichoRendr.', FAILED[1], msg))
    else
      UI.messagebox("TrichoRendr error:\n#{msg}")
    end
    @batch[:cancelled] = true if @batch # stop the batch: an exception is not a per-scene problem
    finish(:failed)
  end
end
