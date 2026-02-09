"""Worker classes for background sampling tasks."""

from PySide6.QtCore import QObject, QRunnable, Signal

from netmon.collector import Collector


class WorkerSignals(QObject):
    """Signals for communicating between worker threads and main thread."""
    
    sample_ready = Signal(object)  # Emits Measurement object
    error = Signal(str)           # Emits error message
    finished = Signal()           # Emits when worker completes


class SampleWorker(QRunnable):
    """Worker that executes collector.generate_sample() in background thread."""
    
    def __init__(self, collector: Collector, host: str):
        super().__init__()
        self.collector = collector
        self.host = host
        self.signals = WorkerSignals()
    
    def run(self):
        """Execute the sampling task in background thread."""
        try:
            # Call the collector (this may be slow - e.g., real ping)
            measurement = self.collector.generate_sample(self.host)
            
            # Emit the result back to main thread
            self.signals.sample_ready.emit(measurement)
            
        except Exception as e:
            # Emit error message back to main thread
            self.signals.error.emit(str(e))
            
        finally:
            # Always signal completion
            self.signals.finished.emit()