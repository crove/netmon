"""Test logging configuration edge cases."""

import os
import sys
import logging

print("=" * 80)
print("LOGGING CONFIGURATION EDGE CASES")
print("=" * 80)

# Test 1: Invalid log level (should default to INFO)
print("\n1. Invalid log level (should default to INFO)")
os.environ["NETMON_LOG_LEVEL"] = "INVALID"
from netmon.logging_config import configure_logging

configure_logging()
logger = logging.getLogger("test")
logger.info("This INFO message should appear")
logger.debug("This DEBUG message should NOT appear")

# Test 2: Case sensitivity
print("\n2. Log level is case-insensitive")
os.environ["NETMON_LOG_LEVEL"] = "debug"
# Need to reimport to reset
import importlib
import netmon.logging_config

importlib.reload(netmon.logging_config)
netmon.logging_config.configure_logging()
logger2 = logging.getLogger("test2")
logger2.debug("This DEBUG message should appear")

print("\n" + "=" * 80)
print("Edge case tests complete")
print("=" * 80)
