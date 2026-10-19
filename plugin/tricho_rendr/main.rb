# TrichoRendr entry point, loaded by ../tricho_rendr.rb. See docs/ARCHITECTURE.md.
require 'json'
require 'digest'
require 'fileutils'

require_relative 'config'
require_relative 'exporter'
require_relative 'observers'
require_relative 'settings'
require_relative 'render'
require_relative 'batch'
require_relative 'dialog'

module TrichoRendr
  unless file_loaded?(__FILE__)
    start_log
    log("loaded: SketchUp #{Sketchup.version}, Ruby #{RUBY_VERSION}, blender=#{blender.inspect}")
    cmd = UI::Command.new('TrichoRendr') { guard { open } }
    cmd.tooltip = 'TrichoRendr'
    cmd.status_bar_text = 'Open the TrichoRendr render window.'
    cmd.small_icon = cmd.large_icon = ICON
    UI.menu('Extensions').add_item(cmd)
    tb = UI::Toolbar.new('TrichoRendr')
    tb.add_item(cmd)
    tb.get_last_state == TB_NEVER_SHOWN ? tb.show : tb.restore
    file_loaded(__FILE__)
  end
end
