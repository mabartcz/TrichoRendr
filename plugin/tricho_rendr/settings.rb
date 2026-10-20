# Saved settings, look validation, and the keys that decide when an export can be reused.
module TrichoRendr
  def self.settings
    saved = JSON.parse(Sketchup.read_default('TrichoRendr', 'settings', '{}')) rescue {}
    saved.delete('width') unless saved.key?('height') # saved before fixed sizes existed: take the new default
    s = DEFAULTS.merge(saved.slice(*DEFAULTS.keys))
    s.merge('look' => clean_look(s['look']), 'words' => clean_words(s['words']),
            'presets' => clean_presets(s['presets']))
  end

  # Known keys only, numbers clamped to their range, choices from their list; anything else -> default.
  def self.clean_look(look)
    look = {} unless look.is_a?(Hash)
    LOOK.to_h do |k, d|
      v = look.fetch(k, d)
      v = if d == true || d == false then v == true
          elsif d.is_a?(String) then LOOK_CHOICES[k].include?(v) ? v : d
          else (Float(v) rescue d).clamp(*LOOK_RANGES[k])
          end
      [k, v]
    end
  end

  # Trimmed lower-case words without duplicates; a missing or broken list -> default (an empty one is kept).
  def self.clean_words(words)
    words = {} unless words.is_a?(Hash)
    WORDS.to_h do |k, d|
      v = words[k]
      [k, v.is_a?(Array) ? v.map { |w| w.to_s.strip.downcase }.reject(&:empty?).uniq : d]
    end
  end

  # Her own look presets: [{name, look}], named, unique names, looks validated like the Look tab.
  def self.clean_presets(presets)
    return [] unless presets.is_a?(Array)

    presets.filter_map do |p|
      name = p.is_a?(Hash) ? p['name'].to_s.strip[0, 40] : ''
      { 'name' => name, 'look' => clean_look(p['look']) } unless name.empty?
    end.uniq { |p| p['name'] }
  end

  # Besides geometry, the export depends on what is visible: tags, tag folders, hidden objects.
  # Scenes that show the same things therefore share one export (only camera and sun differ).
  # Walking every face is slow on a big model, so the result is kept until an edit, a scene change or a tag
  # change (hiding things is an edit; scenes hide things when selected).
  def self.visibility(model)
    walk = ->(f) { [f.visible?, f.folders.map(&walk)] }
    folders = model.layers.respond_to?(:folders) ? model.layers.folders.map(&walk) : []
    memo = [model.object_id, edits, model.pages.selected_page&.name, model.layers.map(&:visible?), folders]
    return @visibility[1] if @visibility&.first == memo

    hidden = model.entities.select(&:hidden?).map(&:entityID)
    model.definitions.each do |d|
      next if d.image? || d.count_instances.zero?

      d.instances.each { |i| hidden << i.entityID if i.hidden? } # nested groups and components too
      d.entities.grep(Sketchup::Face) { |f| hidden << f.entityID if f.hidden? } # scenes can hide nested faces
    end
    @visibility = [memo, Digest::MD5.hexdigest([model.layers.map(&:visible?), folders, hidden.sort].inspect)]
    @visibility[1]
  end

  # vis: visibility(model), passed in so one render walks the model once.
  def self.export_key(model, vis = visibility(model))
    [model.object_id, edits, vis, model.rendering_options['FaceFrontColor'].to_a]
  end

  # Same idea across SketchUp sessions: an unmodified model whose .skp is byte-for-byte the one
  # exported last time (same path, mtime, size) reuses the job folder. nil = not reusable.
  def self.saved_key(model, vis = nil)
    return nil if model.modified? || model.path.empty? || !File.exist?(model.path)

    [model.path, File.mtime(model.path).to_f, File.size(model.path), vis || visibility(model),
     model.rendering_options['FaceFrontColor'].to_a]
  end

  EXPORT_JSON = File.join(JOB, 'export.json')

  def self.saved_export(model, vis = nil)
    key = saved_key(model, vis)
    return nil unless key && File.exist?(EXPORT_JSON)
    return nil unless %w[pos uv mat inst].all? { |n| File.exist?(File.join(JOB, "#{n}.bin")) }

    data = JSON.parse(File.read(EXPORT_JSON), symbolize_names: true)
    return nil unless data[:key] == JSON.parse(JSON.generate(key))

    stats = data[:stats]
    return nil unless Array(stats[:materials]).all? { |m| !m[:texture] || File.exist?(m[:texture]) }

    stats
  rescue StandardError => e
    log("saved export unreadable: #{e.message}")
    nil
  end

  # Render statistics for the Stats tab: running totals kept on this PC, nothing is sent anywhere. Own file,
  # written after every render: SketchUp saves its defaults only when it closes cleanly, so a crash lost them.
  USAGE_JSON = File.join(File.dirname(LOG_DIR), 'usage.json')

  def self.usage
    @usage ||= begin
      text = File.exist?(USAGE_JSON) ? File.read(USAGE_JSON) : Sketchup.read_default('TrichoRendr', 'usage', '{}')
      u = JSON.parse(text)
      u.is_a?(Hash) ? u : {}
    rescue StandardError
      {}
    end
  end

  # result: :done | :failed | :cancelled; job: size, samples and export numbers of that render.
  def self.count_render(result, job, seconds)
    u = usage.dup
    today = Time.now.strftime('%Y-%m-%d')
    u['since'] ||= today
    u[result.to_s] = u[result.to_s].to_i + 1
    if result == :done
      px = job[:width] * job[:height]
      u['days'] = u['days'].to_i + 1 unless u['last'] == today
      u['last'] = today
      u['seconds'] = u['seconds'].to_f + seconds
      u['longest'] = [u['longest'].to_f, seconds].max
      u['pixels'] = u['pixels'].to_i + px
      u['paths'] = u['paths'].to_i + (px * job[:samples])
      u['triangles'] = u['triangles'].to_i + job[:triangles]
      u['biggest'] = [u['biggest'].to_i, job[:triangles]].max
      u['faceme'] = u['faceme'].to_i + job[:faceme]
      u['scenes'] = u['scenes'].to_i + 1 if job[:batch]
    end
    @usage = u
    FileUtils.mkdir_p(File.dirname(USAGE_JSON))
    File.write("#{USAGE_JSON}.tmp", JSON.generate(u))
    File.rename("#{USAGE_JSON}.tmp", USAGE_JSON) # a crash mid-write leaves the old file, not half a new one
    push(usage: u)
  rescue StandardError => e
    log("usage: #{e.class}: #{e.message}") # statistics must never break a render
  end

  def self.default_folder(model)
    return File.join(Dir.home, 'Documents', 'TrichoRendr renders').tr('\\', '/') if model.path.empty?

    File.join(File.dirname(model.path), "#{File.basename(model.path, '.skp')} renders").tr('\\', '/')
  end
end
