"""Quick manual test to verify logging system works."""

import os
import sys

# Set DEBUG level for thorough logging (can be overridden by env var)
if "NETMON_LOG_LEVEL" not in os.environ:
    os.environ["NETMON_LOG_LEVEL"] = "DEBUG"

from netmon.logging_config import configure_logging
from netmon.collector_ping import PingCollector, parse_ping_latency_ms
from netmon.workers import SampleWorker
from netmon.collector import FakeCollectorAdapter

configure_logging()

print("\n" + "=" * 80)
print("LOGGING SYSTEM VERIFICATION")
print("=" * 80)

# Test 1: Parse function (should have no logs - it's pure)
print("\n1. Testing pure parse function (should be silent at INFO):")
result = parse_ping_latency_ms("time=10.5 ms")
print(f"   Result: {result}")

# Test 2: PingCollector with invalid host (should log at DEBUG)
print("\n2. Testing PingCollector with unreachable host (check logs above):")
collector = PingCollector(timeout_ms=500)
measurement = collector.generate_sample("192.0.2.1")  # TEST-NET-1, should fail
print(f"   Measurement: loss={measurement.loss}")

# Test 3: Worker with FakeCollector
print("\n3. Testing Worker (check DEBUG logs):")
from PySide6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)

fake_collector = FakeCollectorAdapter()
worker = SampleWorker(fake_collector, "test.com", generation_id=42)

# Manually call run to see logging
worker.run()
print("   Worker executed (check logs)")

print("\n" + "=" * 80)
print("SUCCESS: Logging system integration complete")
print("=" * 80)
