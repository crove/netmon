"""Worker classes for background sampling tasks."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from netmon.collector import Collector

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Signals for communicating between worker threads and main thread."""

    sample_ready = Signal(object, int, str)  # Emits (Measurement, generation_id, host)
    error = Signal(str)  # Emits error message
    finished = Signal()  # Emits when worker completes


class SampleWorker(QRunnable):
    """Worker that executes collector.generate_sample() in background thread."""

    def __init__(self, collector: Collector, host: str, generation_id: int):
        super().__init__()
        self.collector = collector
        self.host = host
        self.generation_id = generation_id
        self.signals = WorkerSignals()

    def run(self):
        """Execute the sampling task in background thread."""
        try:
            logger.debug(
                "Worker starting: host=%s, generation_id=%d", self.host, self.generation_id
            )

            # Call the collector (this may be slow - e.g., real ping)
            measurement = self.collector.generate_sample(self.host)

            # Emit the result back to main thread with generation_id and host
            self.signals.sample_ready.emit(measurement, self.generation_id, self.host)

            logger.debug(
                "Worker completed: host=%s, generation_id=%d, loss=%s",
                self.host,
                self.generation_id,
                measurement.loss,
            )

        except Exception as e:
            # Emit error message back to main thread
            logger.exception(
                "Worker exception: host=%s, generation_id=%d, error=%s",
                self.host,
                self.generation_id,
                str(e),
            )
            self.signals.error.emit(str(e))

        finally:
            # Always signal completion
            self.signals.finished.emit()
