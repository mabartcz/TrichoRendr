# Batch render: several scenes one after another into a folder, never overwriting.
module TrichoRendr
  def self.start_batch(s, names, folder)
    FileUtils.mkdir_p(folder)
    model = Sketchup.active_model
    @batch = { settings: s, folder: folder, i: 0, times: [], back_to: model.pages.selected_page&.name,
               items: names.map { |n| { name: n, status: 'waiting', pct: nil, file: nil } } }
    log("batch: #{names.size} scenes -> #{folder}")
    batch_next
  end

  def self.batch_state
    b = @batch
    { items: b[:items].map { |it| it.except(:t0) }, index: b[:i], folder: b[:folder], running: !b[:finished] }
  end

  def self.batch_next
    b = @batch
    return batch_finish if b[:cancelled] || b[:i] >= b[:items].size

    item = b[:items][b[:i]]
    model = Sketchup.active_model
    page = model.pages[item[:name]]
    unless page
      item[:status] = 'skipped'
      b[:i] += 1
      return batch_next
    end
    item[:status] = 'active'
    item[:t0] = now
    @busy = true # Start stays disabled and Cancel works while the scene transition runs
    @cancelled = false
    push(busy: true, error: nil, render: nil, pct: nil, status: 'Switching to the scene…', batch: batch_state)
    self.switching = true
    model.pages.selected_page = page
    wait_for_scene(page) do
      self.switching = false
      if b[:cancelled]
        batch_finish
      else
        log("batch: scene #{b[:i] + 1}/#{b[:items].size} #{item[:name].inspect}")
        snapshot # the Viewport tab follows the scene being rendered
        render(b[:settings]) { |result| batch_done(result) }
      end
    end
  end

  # Scene changes animate the camera; wait until the view sits on the scene's camera.
  def self.wait_for_scene(page, &blk)
    view = Sketchup.active_model.active_view
    started = now
    stable = 0
    timer = UI.start_timer(0.2, true) do
      done = begin
        c = view.camera
        pc = page.camera
        lens_ok = c.perspective? == pc.perspective? &&
                  (c.perspective? ? (c.fov - pc.fov).abs < 0.01 : (c.height - pc.height).abs < 0.01)
        same = !page.use_camera? || (c.eye.distance(pc.eye) < 0.01 && c.target.distance(pc.target) < 0.01 &&
                                     c.up.angle_between(pc.up) < 0.001 && lens_ok)
        stable = same ? stable + 1 : 0
        @batch.nil? || @batch[:cancelled] || stable >= 2 || now - started > 10
      rescue StandardError => e # a repeating timer that raises would never stop: the batch would hang
        log("batch: waiting for the scene failed: #{e.class}: #{e.message}")
        true
      end
      if done
        UI.stop_timer(timer)
        guard(&blk)
      end
    end
  end

  def self.batch_done(result)
    b = @batch
    item = b[:items][b[:i]]
    if result == :done
      file = unique_path(b[:folder], safe_name(item[:name]))
      FileUtils.cp(File.join(JOB, 'render.png'), file)
      item.merge!(status: 'done', pct: 100, file: "file:///#{file}")
      b[:times] << (now - item[:t0])
      log("batch: saved #{file}")
    else
      item[:status] = result.to_s # cancelled / failed
      item[:error] = @state[:status]
    end
    b[:cancelled] ||= result == :cancelled
    b[:i] += 1
    batch_next # a failed scene doesn't stop the others
  end

  def self.batch_finish
    b = @batch
    b[:finished] = true
    b[:items].each { |it| it[:status] = 'skipped' if %w[waiting active].include?(it[:status]) }
    model = Sketchup.active_model
    back = model.pages[b[:back_to]] if b[:back_to]
    model.pages.selected_page = back if back
    done = b[:items].count { |it| it[:status] == 'done' }
    log("batch: finished #{done}/#{b[:items].size} in #{b[:times].sum.round} s")
    state = batch_state
    @batch = nil
    @busy = false
    push(busy: false, pct: done.positive? ? 100 : nil, eta: nil, batch: state,
         status: "Batch finished: #{done} of #{state[:items].size} scenes saved#{b[:cancelled] ? ' (cancelled)' : ''}")
  end

  def self.safe_name(name)
    n = name.gsub(%r{[<>:"/\\|?*\x00-\x1f]}, '_').strip
    n.empty? ? 'scene' : n
  end

  def self.unique_path(folder, base)
    path = File.join(folder, "#{base}.png")
    n = 1
    path = File.join(folder, "#{base} (#{n += 1}).png") while File.exist?(path)
    path
  end

  # Status line and time left for the whole batch, from the current scene's numbers.
  def self.batch_view(changes)
    b = @batch
    return changes unless b && !b[:finished] && b[:i] < b[:items].size

    n = b[:items].size
    item = b[:items][b[:i]]
    out = changes.dup
    out[:status] = "Scene #{b[:i] + 1}/#{n} · #{item[:name]} · #{changes[:status]}" if changes.key?(:status)
    if changes.key?(:pct)
      item[:pct] = changes[:pct]
      out[:batch] = batch_state
    end
    if changes.key?(:eta)
      left = n - b[:i] - 1
      avg = b[:times].empty? ? nil : b[:times].sum / b[:times].size
      avg ||= (now - item[:t0]) + changes[:eta] if changes[:eta] # first scene: its own estimate
      out[:eta] = changes[:eta] && avg ? changes[:eta] + (left * avg) : nil
    end
    out
  end
end
