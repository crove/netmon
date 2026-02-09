"""Collector abstraction for NetMon data sources."""

from typing import Protocol
from netmon.models import Measurement
from netmon.fake_collector import FakeCollector


class Collector(Protocol):
    """Protocol defining the interface for measurement collectors."""

    def generate_sample(self, host: str) -> Measurement:
        """Generate a single measurement sample for the given host."""
        ...


class FakeCollectorAdapter:
    """Adapter that implements Collector protocol using FakeCollector."""

    def __init__(self, fake_collector: FakeCollector | None = None):
        """Initialize with optional FakeCollector instance."""
        if fake_collector is None:
            fake_collector = FakeCollector()
        self._fake_collector = fake_collector

    def generate_sample(self, host: str) -> Measurement:
        """Generate a sample using the underlying FakeCollector."""
        return self._fake_collector.generate_sample(host)
