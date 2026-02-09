"""Fake data collector for NetMon testing and simulation."""

import random
from datetime import datetime
from netmon.models import Measurement


class FakeCollector:
    """Generates fake network measurement samples for testing."""

    def __init__(self, seed: int | None = None):
        """Initialize with optional random seed for deterministic behavior."""
        # Create isolated random instance for thread safety
        self._random = random.Random(seed)

        # Simulation parameters
        self.base_latency = 25.0  # Base latency in ms
        self.latency_variance = 5.0  # Normal variance
        self.spike_probability = 0.05  # 5% chance of latency spike
        self.spike_multiplier = 3.0  # Spike makes latency 3x higher
        self.loss_probability = 0.02  # 2% chance of packet loss

    def generate_sample(self, host: str) -> Measurement:
        """Generate a single measurement sample for the given host."""
        if not host or not host.strip():
            raise ValueError("Host cannot be empty")

        timestamp = datetime.now()

        # Determine if this sample is lost
        is_lost = self._random.random() < self.loss_probability

        if is_lost:
            return Measurement(ts=timestamp, host=host, latency_ms=None, loss=True)

        # Generate latency with occasional spikes
        if self._random.random() < self.spike_probability:
            # Latency spike
            latency = self.base_latency * self.spike_multiplier + self._random.gauss(
                0, self.latency_variance
            )
        else:
            # Normal latency
            latency = self.base_latency + self._random.gauss(0, self.latency_variance)

        # Ensure latency is positive
        latency = max(0.1, latency)

        return Measurement(ts=timestamp, host=host, latency_ms=round(latency, 2), loss=False)


# Global instance for easy access
_default_collector = FakeCollector()


def generate_sample(host: str) -> Measurement:
    """Generate a sample using the default collector instance."""
    return _default_collector.generate_sample(host)
