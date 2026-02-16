"""Multi-host sampling scheduler with bounded concurrency."""

import logging
from PySide6.QtCore import QObject, QTimer, QThreadPool, Signal
from netmon.collector import Collector
from netmon.workers import SampleWorker

logger = logging.getLogger(__name__)


class MultiHostScheduler(QObject):
    """Schedules ping sampling for multiple hosts with bounded concurrency.
    
    Key features:
    - Maintains list of target hosts
    - Bounded global concurrency (max N workers at once)
    - Per-host in-flight tracking (prevents duplicate pings to same host)
    - Timer-driven scheduling with skipped ticks if over capacity
    
    Thread-safe: All state access on Qt main thread via signals/slots.
    """

    # Signals
    sample_ready = Signal(object, int, str)  # (Measurement, generation_id, host)
    error = Signal(str, str)  # (host, error_msg)

    def __init__(
        self,
        collector: Collector,
        interval_ms: int = 1000,
        max_concurrent: int = 4,
        parent=None,
    ):
        """Initialize multi-host scheduler.
        
        Args:
            collector: Collector instance for generating samples
            interval_ms: Sampling interval in milliseconds
            max_concurrent: Maximum number of concurrent workers globally
            parent: Qt parent object
        """
        super().__init__(parent)
        
        self.collector = collector
        self.interval_ms = interval_ms
        self.max_concurrent = max_concurrent
        
        # Host management
        self._hosts = []  # List of target hosts
        self._host_in_flight = {}  # {host: bool} - per-host in-flight flags
        
        # Global concurrency tracking
        self._global_in_flight = 0  # Count of active workers
        
        # Generation ID for invalidating stale results
        self._generation_id = 0
        
        # Threading
        self.thread_pool = QThreadPool.globalInstance()
        
        # Timer for periodic sampling
        self.timer = QTimer()
        self.timer.timeout.connect(self._schedule_tick)
        
        # Monitoring state
        self.is_monitoring = False

    def add_host(self, host: str):
        """Add a host to the monitoring list.
        
        Args:
            host: Host to add (duplicates are ignored)
        """
        host = host.strip()
        if not host:
            return
        
        if host not in self._hosts:
            self._hosts.append(host)
            self._host_in_flight[host] = False
            logger.debug("Host added: %s (total: %d)", host, len(self._hosts))

    def remove_host(self, host: str):
        """Remove a host from the monitoring list.
        
        Args:
            host: Host to remove
        """
        if host in self._hosts:
            self._hosts.remove(host)
            self._host_in_flight.pop(host, None)
            logger.debug("Host removed: %s (remaining: %d)", host, len(self._hosts))

    def get_hosts(self):
        """Get list of all monitored hosts.
        
        Returns:
            List of host strings
        """
        return list(self._hosts)

    def clear_hosts(self):
        """Clear all hosts from the monitoring list."""
        self._hosts.clear()
        self._host_in_flight.clear()
        logger.debug("All hosts cleared")

    def start_monitoring(self):
        """Start monitoring all hosts."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.timer.start(self.interval_ms)
        logger.info("Monitoring started: %d hosts, interval=%dms", len(self._hosts), self.interval_ms)

    def stop_monitoring(self):
        """Stop monitoring all hosts and invalidate in-flight results."""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.timer.stop()
        self._generation_id += 1  # Invalidate in-flight workers
        logger.info("Monitoring stopped (generation_id=%d)", self._generation_id)

    def set_interval(self, interval_ms: int):
        """Update sampling interval.
        
        Args:
            interval_ms: New interval in milliseconds
        """
        self.interval_ms = interval_ms
        if self.timer.isActive():
            self.timer.setInterval(interval_ms)
        logger.debug("Interval updated: %dms", interval_ms)

    def _schedule_tick(self):
        """Handle timer tick - attempt to schedule samples for ready hosts.
        
        Scheduling rules:
        1. Skip if not monitoring
        2. Skip if global concurrency limit reached
        3. For each host: schedule if not already in-flight
        4. Fair scheduling: iterate through all hosts each tick
        """
        if not self.is_monitoring:
            return
        
        if len(self._hosts) == 0:
            return
        
        # Check global concurrency limit
        if self._global_in_flight >= self.max_concurrent:
            logger.debug(
                "Tick skipped: at global concurrency limit (%d/%d)",
                self._global_in_flight,
                self.max_concurrent,
            )
            return
        
        # Try to schedule samples for hosts that aren't in-flight
        scheduled_count = 0
        for host in self._hosts:
            # Check global limit again (may have scheduled some already)
            if self._global_in_flight >= self.max_concurrent:
                break
            
            # Skip if this host already has a worker in-flight
            if self._host_in_flight.get(host, False):
                continue
            
            # Schedule sample for this host
            self._schedule_sample(host)
            scheduled_count += 1
        
        if scheduled_count > 0:
            logger.debug(
                "Scheduled %d samples (in-flight: %d/%d)",
                scheduled_count,
                self._global_in_flight,
                self.max_concurrent,
            )

    def _schedule_sample(self, host: str):
        """Schedule a sample collection for a specific host.
        
        Args:
            host: Target host
        """
        # Mark as in-flight
        self._host_in_flight[host] = True
        self._global_in_flight += 1
        
        # Capture current generation_id
        generation_id = self._generation_id
        
        # Create worker
        worker = SampleWorker(self.collector, host, generation_id)
        worker.signals.sample_ready.connect(self._on_sample_ready)
        worker.signals.error.connect(self._on_sample_error)
        worker.signals.finished.connect(lambda: self._on_sample_finished(host))
        
        # Execute in thread pool
        self.thread_pool.start(worker)

    def _on_sample_ready(self, sample, generation_id, host):
        """Handle sample ready from worker.
        
        Args:
            sample: Measurement object
            generation_id: Generation ID when worker was scheduled
            host: Host that was sampled
        """
        # Check if stale (generation mismatch)
        if generation_id != self._generation_id:
            logger.debug(
                "Ignoring stale result: host=%s, generation_id=%d (current=%d)",
                host,
                generation_id,
                self._generation_id,
            )
            return
        
        # Only process if still monitoring
        if not self.is_monitoring:
            return
        
        # Forward to main window
        self.sample_ready.emit(sample, generation_id, host)

    def _on_sample_error(self, error_msg):
        """Handle sample error from worker.
        
        Args:
            error_msg: Error message
        """
        # Note: We don't have host context here from the worker error signal
        # This is a limitation of the current worker design
        logger.error("Sampling error: %s", error_msg)
        self.error.emit("unknown", error_msg)

    def _on_sample_finished(self, host: str):
        """Handle worker completion - clear in-flight flags.
        
        Args:
            host: Host that finished sampling
        """
        # Clear per-host flag
        self._host_in_flight[host] = False
        
        # Decrement global counter
        self._global_in_flight = max(0, self._global_in_flight - 1)
        
        logger.debug(
            "Worker finished: host=%s (in-flight: %d/%d)",
            host,
            self._global_in_flight,
            self.max_concurrent,
        )

    def get_stats(self):
        """Get scheduler statistics.
        
        Returns:
            Dict with scheduler state info
        """
        return {
            "hosts": len(self._hosts),
            "in_flight": self._global_in_flight,
            "max_concurrent": self.max_concurrent,
            "monitoring": self.is_monitoring,
            "generation_id": self._generation_id,
        }
