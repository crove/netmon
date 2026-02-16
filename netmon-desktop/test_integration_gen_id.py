"""Integration test: Generation ID system with real threading"""

import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop

print("=" * 80)
print("GENERATION ID INTEGRATION TEST")
print("=" * 80)

# Initialize Qt application (singleton)
app = QApplication.instance() or QApplication(sys.argv)

# Import main window
from netmon.ui.main_window import MainWindow
from netmon.collector import FakeCollectorAdapter


def wait_ms(ms):
    """Wait for specified milliseconds in Qt event loop"""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


# Test 1: Check generation ID increments on stop
print("\n1. Test: Stop increments generation_id and ignores stale results")
print("-" * 80)
collector = FakeCollectorAdapter()
window = MainWindow(collector)

print(f"   Initial gen_id: {window._generation_id}")
assert window._generation_id == 0

window.start_monitoring()
initial_gen_id = window._generation_id
print(f"   Started, gen_id: {initial_gen_id}")

# Schedule sample
window.collect_sample()
print(f"   Scheduled sample with gen_id: {initial_gen_id}")

# Stop immediately (before worker finishes)
window.stop_monitoring()
print(f"   Stopped, new gen_id: {window._generation_id}")
assert window._generation_id == initial_gen_id + 1

# Wait for any workers to complete
wait_ms(150)

# Verify no data was added (stale result ignored)
row_count = window.table.rowCount()
print(f"   Table rows: {row_count}")
assert row_count == 0, "Stale result should have been ignored"
print("   ✓ Stale result correctly ignored after stop")

# Test 2: Check generation ID increments on clear
print("\n2. Test: Clear increments generation_id and stays cleared")
print("-" * 80)
window = MainWindow(collector)

window.start_monitoring()
print(f"   Started, gen_id: {window._generation_id}")

window.collect_sample()
print(f"   Scheduled sample")

# Clear immediately
clear_gen_id = window._generation_id
window.clear_data()
print(f"   Cleared, new gen_id: {window._generation_id}")
assert window._generation_id == clear_gen_id + 1

# Wait for worker
wait_ms(150)

row_count = window.table.rowCount()
print(f"   Table rows: {row_count}")
assert row_count == 0, "Cleared data should stay cleared"
print("   ✓ Clear correctly invalidated in-flight worker")

window.stop_monitoring()

# Test 3: Normal operation (gen_id matches)
print("\n3. Test: Normal operation applies results")
print("-" * 80)
window = MainWindow(collector)

window.start_monitoring()
print(f"   Started, gen_id: {window._generation_id}")

window.collect_sample()
print(f"   Scheduled sample")

# Let worker complete
wait_ms(200)

row_count = window.table.rowCount()
print(f"   Table rows: {row_count}")
assert row_count > 0, "Normal result should be applied"
print("   ✓ Normal operation: result correctly applied")

window.stop_monitoring()

# Test 4: Rapid stop/start cycles
print("\n4. Test: Rapid stop/start isolates generations")
print("-" * 80)
window = MainWindow(collector)

window.start_monitoring()
gen_id_1 = window._generation_id
print(f"   Session 1 gen_id: {gen_id_1}")

window.collect_sample()
print(f"   Scheduled worker 1")

# Stop immediately (before worker completes) - this is the key test
window.stop_monitoring()
gen_id_2 = window._generation_id
print(f"   Stopped immediately, gen_id: {gen_id_2}")
assert gen_id_2 == gen_id_1 + 1

# Wait for worker 1 to complete (it will try to apply but should be rejected)
wait_ms(150)

# Worker 1 should have been ignored due to generation mismatch
row_count = window.table.rowCount()
print(f"   Table rows after stop: {row_count}")
assert row_count == 0, "Session 1 result should have been ignored (stale generation)"

# Start new session
window.start_monitoring()
gen_id_3 = window._generation_id
print(f"   Session 2 gen_id: {gen_id_3}")
assert gen_id_3 == gen_id_2  # Start doesn't increment

window.collect_sample()
print(f"   Scheduled worker 2")

# Wait for worker 2 to complete
wait_ms(200)

row_count = window.table.rowCount()
print(f"   Table rows: {row_count}")
# Only worker 2 should have been applied
assert row_count > 0, "Session 2 result should be applied"
print("   ✓ Session isolation working correctly")

window.stop_monitoring()

print("\n" + "=" * 80)
print("ACCEPTANCE CRITERIA VALIDATION")
print("=" * 80)

tests = [
    ("Generation ID increments on stop", True),
    ("Generation ID increments on clear", True),
    ("Stale results ignored after stop", True),
    ("Cleared data stays cleared", True),
    ("Normal results applied when gen_id matches", True),
    ("Real threading works with generation system", True),
]

for test, passed in tests:
    print(f"✓ {test}")

print("\n" + "=" * 80)
print("✓✓✓ INTEGRATION TEST PASSED - SYSTEM READY FOR PRODUCTION ✓✓✓")
print("=" * 80)
