require 'sketchup.rb'
require 'extensions.rb'

module TrichoRendr
  unless file_loaded?(__FILE__)
    ext = SketchupExtension.new('TrichoRendr', 'tricho_rendr/main')
    ext.version = '0.3.1'
    ext.description = 'Nice, simple renders of SketchUp models with Blender Cycles: sun, sky, water, glass, face-me trees.'
    ext.creator = 'TrichoRendr'
    Sketchup.register_extension(ext, true)
    file_loaded(__FILE__)
  end
end
