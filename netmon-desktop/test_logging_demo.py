"""Demo: Structured logging at different levels."""

import os
import sys

print("=" * 80)
print("STRUCTURED LOGGING DEMO")
print("=" * 80)

# Test at INFO level (default)
print("\n1. INFO LEVEL (default - production mode)")
print("-" * 80)
os.environ["NETMON_LOG_LEVEL"] = "INFO"

from netmon.logging_config import configure_logging
from netmon.collector_ping import PingCollector

configure_logging()

collector = PingCollector(timeout_ms=500)
measurement = collector.generate_sample("192.0.2.1")  # Should fail
print(f"Measurement: loss={measurement.loss}")
print("Note: No DEBUG logs visible at INFO level")

print("\n" + "=" * 80)
print("Demo complete. Try running with:")
print("  NETMON_LOG_LEVEL=DEBUG python test_logging_demo.py")
print("=" * 80)
