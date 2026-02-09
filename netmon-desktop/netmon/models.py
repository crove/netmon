"""Data models for NetMon measurements."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Measurement:
    """A single network measurement sample."""

    ts: datetime
    host: str
    latency_ms: float | None  # None indicates packet loss
    loss: bool

    def __post_init__(self):
        """Ensure consistency between latency_ms and loss fields."""
        if self.loss:
            self.latency_ms = None
        elif self.latency_ms is None:
            self.loss = True
