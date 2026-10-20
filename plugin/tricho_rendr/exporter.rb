# Model -> job folder export (binary geometry + scene.json), sliced so SketchUp stays responsive.
module TrichoRendr
  # Writes the job folder:
  #   scene.json  camera, sun, settings, materials, meshes (tri ranges), faceme (world transforms)
  #   pos.bin     f64 x9 per triangle, definition-local inches
  #   uv.bin      f32 x12 per triangle (front UVs, then back UVs)
  #   mat.bin     i32 x2 per triangle (front, back material; -1 = inherit from instance)
  #   inst.bin    per instance: u32 mesh, i32 material, i32 face-me index (-1 = none), f64 x16 transform
  # Textures go to TEX_CACHE (absolute paths in scene.json).
  # Each component definition is written once; instances only reference it.
  # Nothing depends on the camera, so the export is reused until the model changes.
  #
  # SketchUp's Ruby runs on the UI thread, so the walk runs inside a Fiber that pauses every
  # SLICE seconds (even mid-component) and resumes from a UI timer: SketchUp stays responsive.
  class Exporter
    SLICE = 0.1 # work per slice; the timer gap between slices is ~30 ms, so smaller slices waste more

    def initialize(model, dir)
      @model = model
      @dir = dir
      @mats = { nil => 0 }
      @mat_list = [{ name: 'default', color: rgb(model.rendering_options['FaceFrontColor']), alpha: 1.0, texture: nil }]
      @meshes = {}
      @mesh_list = []
      @faceme = []
      @tris = 0
      @instances = 0
      @faces_done = 0
      @faces_total = nil
      @ticks = 0
      @slowest = 0.0
      @textures = 0
      @texture_s = 0.0
      @visible_tags = model.layers.to_h { |l| [l, tag_visible?(l)] }
    end

    # on_progress.(text, percent or nil, seconds left or nil); on_done.(stats)
    def start(on_progress, &on_done)
      FileUtils.mkdir_p(TEX_CACHE)
      cutoff = Time.now - (14 * 86_400)
      Dir.glob(File.join(TEX_CACHE, '*.png')).each { |f| File.delete(f) if File.mtime(f) < cutoff rescue nil }
      @on_progress = on_progress
      @on_done = on_done
      @files = %w[pos uv mat inst].to_h { |n| [n, File.open(File.join(@dir, "#{n}.bin"), 'wb')] }
      @t0 = TrichoRendr.now
      @fiber = Fiber.new do
        count_faces
        @t_walk = TrichoRendr.now
        TrichoRendr.log("export: counted #{@faces_total} faces in #{(@t_walk - @t0).round(2)} s")
        walk
        :done
      end
      TrichoRendr.log("export: start, #{@model.definitions.size} definitions")
      tick
    end

    def cancel
      @cancelled = true
    end

    private

    def tick
      return close if @cancelled

      started = TrichoRendr.now
      @deadline = started + SLICE
      result = @fiber.resume
      took = TrichoRendr.now - started
      @ticks += 1
      if took > @slowest
        @slowest = took
        TrichoRendr.log("export: slowest slice so far #{(took * 1000).round} ms (#{@current})") if took > 0.15
      end
      if TrichoRendr.now - (@last_log ||= 0) > 2
        @last_log = TrichoRendr.now
        TrichoRendr.log("export: #{@faces_done}/#{@faces_total} faces, #{@tris} tris, #{@ticks} slices")
      end
      if result == :done
        close
        TrichoRendr.log("export: done in #{(TrichoRendr.now - @t0).round(2)} s, #{@tris} tris, " \
                        "#{@instances} instances, #{@mesh_list.size} meshes, #{@mat_list.size} materials, " \
                        "#{@faceme.size} face-me, #{@textures} new textures (#{@texture_s.round(2)} s), " \
                        "#{@ticks} slices, slowest #{(@slowest * 1000).round} ms")
        @on_done.call(materials: @mat_list, meshes: @mesh_list, faceme: @faceme,
                      triangles: @tris, instances: @instances)
      else
        report
        UI.start_timer(0, false) { TrichoRendr.guard { tick } }
      end
    rescue Exception
      close
      raise
    end

    def pause
      Fiber.yield if TrichoRendr.now > @deadline
    end

    def close
      @files.each_value { |f| f.close unless f.closed? }
    end

    def report
      return @on_progress.call('Preparing export (counting faces)…', nil, nil) unless @faces_total

      p = @faces_total.zero? ? 1.0 : [@faces_done.to_f / @faces_total, 1.0].min
      elapsed = TrichoRendr.now - @t_walk
      eta = p > 0.03 ? elapsed / p * (1 - p) : nil
      @on_progress.call("Exporting geometry (#{@tris} triangles)", 100 * p, eta)
    end

    # Rough work estimate for the progress bar: faces of every used definition, counted once.
    def count_faces
      total = @model.entities.grep(Sketchup::Face).size
      @model.definitions.to_a.each do |d|
        pause
        next if d.image? || d.count_instances.zero? || d.instances.none? { |i| visible?(i) }

        total += d.entities.grep(Sketchup::Face).size
      end
      @faces_total = total
    end

    def rgb(c)
      [c.red / 255.0, c.green / 255.0, c.blue / 255.0]
    end

    def tag_visible?(tag)
      return false unless tag.visible?

      folder = tag.respond_to?(:folder) && tag.folder
      while folder
        return false unless folder.visible?

        folder = folder.folder
      end
      true
    end

    def visible?(e)
      e.visible? && @visible_tags[e.layer]
    end

    def mat_id(m)
      @mats[m] ||= begin
        @mat_list << { name: m.display_name, color: rgb(m.color), alpha: m.alpha.to_f,
                       texture: m.texture && texture_file(m) }
        @mat_list.size - 1
      end
    end

    # ponytail: cache key ignores edits to the image itself with the same name/size; clear TEX_CACHE if stale
    def texture_file(m)
      t = m.texture
      key = Digest::MD5.hexdigest([@model.guid, m.name, t.filename, t.image_width, t.image_height,
                                   m.colorize_type, m.color.to_a].join('|'))
      path = File.join(TEX_CACHE, "#{key}.png")
      if File.exist?(path)
        File.utime(nil, nil, path) rescue nil # still in use: keep it out of the 14-day cleanup
        return path
      end

      @current = "texture #{m.display_name} #{t.image_width}x#{t.image_height}"
      started = TrichoRendr.now
      ok = t.write(path, true)
      took = TrichoRendr.now - started
      @textures += 1
      @texture_s += took
      TrichoRendr.log("export: wrote #{@current} in #{(took * 1000).round} ms ok=#{ok}") if took > 0.2 || !ok
      ok ? path : nil
    end

    # Triangles of the faces directly in `entities`, written once per definition.
    def mesh_id(key, entities)
      return @meshes[key] if @meshes.key?(key)

      @current = "mesh #{key == :root ? 'model root' : key.name}"
      pos = []
      uv = []
      mats = []
      entities.to_a.each do |f| # to_a: we pause inside, the model may change meanwhile
        next unless f.is_a?(Sketchup::Face)

        pause
        @faces_done += 1
        next unless visible?(f)

        front = f.material ? mat_id(f.material) : -1
        back = f.back_material ? mat_id(f.back_material) : -1
        need_f = front < 0 || !@mat_list[front][:texture].nil?
        need_b = back < 0 || !@mat_list[back][:texture].nil?
        flags = (need_f ? 1 : 0) | (need_b ? 2 : 0)
        m = f.mesh(flags) # points + only the UVQ sides that can carry a texture
        pts = m.points
        if flags.zero?
          m.polygons.each do |poly|
            poly.each { |i| pos.concat(pts[i.abs - 1].to_a) }
            uv.push(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            mats.push(front, back)
          end
        else
          sides = [need_f ? m.uvs(true) : nil, need_b ? m.uvs(false) : nil]
          m.polygons.each do |poly|
            poly.each { |i| pos.concat(pts[i.abs - 1].to_a) }
            sides.each do |uvs|
              if uvs
                poly.each do |i|
                  q = uvs[i.abs - 1]
                  q.z.zero? ? uv.push(0.0, 0.0) : uv.push(q.x / q.z, q.y / q.z)
                end
              else
                uv.push(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
              end
            end
            mats.push(front, back)
          end
        end
      end
      count = mats.size / 2
      return @meshes[key] = nil if count.zero?

      @files['pos'].write(pos.pack('E*'))
      @files['uv'].write(uv.pack('e*'))
      @files['mat'].write(mats.pack('l<*'))
      @mesh_list << { first: @tris, count: count }
      @tris += count
      @meshes[key] = @mesh_list.size - 1
    end

    def walk
      stack = [[@model.entities, :root, Geom::Transformation.new, 0, -1]]
      until stack.empty?
        entities, key, tr, inherited, fm = stack.pop
        mesh = mesh_id(key, entities)
        if mesh
          @files['inst'].write([mesh, inherited, fm].pack('L<l<l<') + tr.to_a.pack('E16'))
          @instances += 1
        end
        entities.to_a.each do |e|
          next unless (e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)) && visible?(e)

          pause
          t = tr * e.transformation
          child_fm = fm
          if e.definition.behavior.always_face_camera?
            child_fm = @faceme.size # the renderer turns it (and its content) to the camera
            @faceme << t.to_a
          end
          stack << [e.definition.entities, e.definition, t, e.material ? mat_id(e.material) : inherited, child_fm]
        end
      end
    end
  end
end
