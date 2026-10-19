# Model and view observers: edit counting (export reuse) and live viewport snapshots.
module TrichoRendr
  # Counts committed edits per model so an unchanged model reuses the last export.
  class Watch < Sketchup::ModelObserver
    def onTransactionCommit(_model)
      TrichoRendr.edits += 1 unless TrichoRendr.switching # our own scene switches don't count
    end

    def onTransactionUndo(_model)
      TrichoRendr.edits += 1 unless TrichoRendr.switching # our own scene switches don't count
    end

    def onTransactionRedo(_model)
      TrichoRendr.edits += 1 unless TrichoRendr.switching # our own scene switches don't count
    end
  end

  # Refreshes the viewport snapshot in the window shortly after the camera stops moving.
  class ViewWatch < Sketchup::ViewObserver
    def onViewChanged(_view)
      TrichoRendr.view_changed
    end
  end

  # Rebinds observers and refreshes the window when the user opens or creates a model.
  class AppWatch < Sketchup::AppObserver
    def onNewModel(_model)
      TrichoRendr.model_changed
    end

    def onOpenModel(_model)
      TrichoRendr.model_changed
    end

    def onActivateModel(_model)
      TrichoRendr.model_changed
    end
  end

  class << self
    attr_accessor :edits, :switching
  end
  self.edits = 0
end
