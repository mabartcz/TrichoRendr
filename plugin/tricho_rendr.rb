require 'sketchup.rb'
require 'extensions.rb'

module TrichoRendr
  if file_loaded?(__FILE__)
    load File.join(__dir__, 'tricho_rendr', 'main.rb')
  else
    ext = SketchupExtension.new('TrichoRendr', 'tricho_rendr/main')
    ext.version = '0.4.2'
    ext.description = 'Nice, simple renders of SketchUp models with Blender Cycles: sun, sky, water, glass, face-me trees.'
    ext.creator = 'TrichoRendr'
    Sketchup.register_extension(ext, true)
    file_loaded(__FILE__)
  end
end
