# Paths, defaults and small helpers shared by the whole plugin.
module TrichoRendr
  EXE = File.join(__dir__, 'bin', 'tricho_rendr.exe') # launcher, built by `cargo xtask build`
  CYCLES_PY = File.join(__dir__, 'blender', 'cycles.py')
  HTML = File.join(__dir__, 'ui', 'window.html')
  ICON = File.join(__dir__, 'images', 'icon.svg')
  JOB = File.join(Sketchup.temp_dir, 'TrichoRendr')
  VIEW_DIR = File.join(Sketchup.temp_dir, 'TrichoRendr_view')
  TEX_CACHE = File.join(Sketchup.temp_dir, 'TrichoRendr_tex') # survives between renders
  # Look settings for Cycles (cycles.py reads them from scene.json; percentages: 100 = normal). Light and image
  # start neutral; the tuned look is the Basic preset (window.js).
  LOOK = {
    'shadows' => true, 'time' => 'day', 'sun' => 100, 'softness' => 0, 'sky' => 100,
    'style' => 'natural', 'exposure' => 0, 'saturation' => 100, 'warmth' => 60, 'glow' => 0, 'flare' => 0, 'haze' => 0, 'background' => 'sky',
    'clay' => false, 'water_tint' => 50, 'waves' => 50, 'glass' => 100, 'leaves' => 20, 'lamps' => 100
  }.freeze
  LOOK_RANGES = {
    'sun' => [0, 300], 'softness' => [0, 100], 'sky' => [0, 300], 'exposure' => [-3, 3], 'saturation' => [0, 200],
    'warmth' => [-100, 100], 'glow' => [0, 100], 'flare' => [0, 100], 'haze' => [0, 100], 'water_tint' => [0, 100], 'waves' => [0, 200], 'glass' => [0, 200],
    'leaves' => [0, 100], 'lamps' => [0, 500]
  }.freeze
  LOOK_CHOICES = { 'time' => %w[day sunset evening], 'style' => %w[natural soft punchy contrast vivid], 'background' => %w[sky white transparent] }.freeze
  # Material names that get a special shader: parts of the name, edited on the Materials page. cycles.py
  # matches ignoring case and accents (bazén = bazen) and has the same defaults for jobs without words.
  WORDS = {
    'water' => %w[water voda vodn вода pool bazén jezír pond lake river potok],
    'glass' => %w[glass glas sklo sklen skleněný okno steklo стекло vidro],
    'glow' => %w[glow emit svit lamp lampa osvětlení oheň]
  }.freeze
  # height 0 = follow the viewport's shape
  DEFAULTS = { 'width' => 3000, 'height' => 1300, 'samples' => 32, 'mode' => 'view',
               'look' => LOOK, 'words' => WORDS, 'presets' => [] }.freeze

  def self.blender
    env = ENV['BLENDER']
    return env if env && File.exist?(env)

    Dir.glob('C:/Program Files/Blender Foundation/Blender */blender.exe')
       .max_by { |p| Gem::Version.new(p[/Blender ([\d.]+)/, 1]) }
  end

  def self.now
    Process.clock_gettime(Process::CLOCK_MONOTONIC)
  end

  # Logs: %LOCALAPPDATA%/TrichoRendr/logs. plugin.log is this session; earlier sessions and every render's
  # Blender output stay beside it until the folder passes LOG_LIMIT, oldest go first. Forward slashes: Dir.glob.
  LOG_DIR = File.join(ENV['LOCALAPPDATA'] || Sketchup.temp_dir, 'TrichoRendr', 'logs').tr('\\', '/')
  LOG = File.join(LOG_DIR, 'plugin.log')
  LOG_LIMIT = 10 * 1024 * 1024

  # When SketchUp loads the extension: the last session's plugin.log becomes "<date time> session.log".
  def self.start_log
    FileUtils.mkdir_p(LOG_DIR)
    File.rename(LOG, File.join(LOG_DIR, "#{File.mtime(LOG).strftime('%Y-%m-%d %H%M%S')} session.log")) if File.size?(LOG)
    prune_logs
  rescue StandardError
    nil
  end

  # Deletes the oldest entries until the folder fits LOG_LIMIT; names start with the date, so they sort by age.
  def self.prune_logs
    size = lambda do |p|
      File.directory?(p) ? Dir.glob(File.join(p, '**', '*')).sum { |f| File.file?(f) ? File.size(f) : 0 } : File.size(p)
    end
    total = size.call(LOG_DIR)
    (Dir.children(LOG_DIR) - ['plugin.log']).sort.each do |name|
      break if total <= LOG_LIMIT

      path = File.join(LOG_DIR, name)
      total -= size.call(path)
      FileUtils.rm_rf(path)
    end
  end

  def self.log(msg)
    File.open(LOG, 'a') { |f| f.puts("#{Time.now.strftime('%H:%M:%S.%L')} #{msg}") }
  rescue StandardError
    nil
  end
end
