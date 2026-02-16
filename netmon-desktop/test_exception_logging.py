"""Test that exception logging includes tracebacks."""

import os

os.environ["NETMON_LOG_LEVEL"] = "DEBUG"

from netmon.logging_config import configure_logging

configure_logging()

print("=" * 80)
print("EXCEPTION LOGGING TEST")
print("=" * 80)

# Test 1: Worker exception with traceback
print("\n1. Testing Worker exception logging (should include traceback):")
from netmon.workers import SampleWorker
from netmon.collector import Collector


class BrokenCollector(Collector):
    """Collector that always raises an exception."""

    def generate_sample(self, host: str):
        # Create a nested exception for more interesting traceback
        def inner():
            raise ValueError("Simulated collector failure")

        inner()


worker = SampleWorker(BrokenCollector(), "test.com", generation_id=1)
worker.run()  # This will catch and log the exception

# Test 2: PingCollector exception (if possible)
print("\n2. Testing PingCollector exception logging:")
from netmon.collector_ping import PingCollector
import subprocess

# Mock subprocess to raise exception
original_run = subprocess.run


def broken_run(*args, **kwargs):
    raise RuntimeError("Simulated subprocess error")


subprocess.run = broken_run
try:
    collector = PingCollector()
    measurement = collector.generate_sample("test.com")
    print(f"   Measurement: loss={measurement.loss}")
finally:
    subprocess.run = original_run

print("\n" + "=" * 80)
print("Check logs above - should see full tracebacks with:")
print("  - Worker: ValueError with nested call stack")
print("  - PingCollector: RuntimeError with subprocess context")
print("=" * 80)
