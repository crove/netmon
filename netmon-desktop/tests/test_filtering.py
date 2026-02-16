"""Tests for filtering and sorting functionality."""

import pytest
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from netmon.ui.main_window import MainWindow
from netmon.collector import FakeCollectorAdapter
from netmon.models import Measurement


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    """Create MainWindow instance for each test."""
    collector = FakeCollectorAdapter()
    win = MainWindow(collector)
    yield win
    # Cleanup
    win.scheduler.stop_monitoring()
    win.scheduler.thread_pool.waitForDone(100)
    win.close()
    win.deleteLater()


class TestFilteringAndSorting:
    """Test suite for proxy model filtering and sorting."""

    def test_initial_filter_state(self, window):
        """Verify filter dropdown starts with 'All' and default hosts."""
        # Should have "All" plus 3 default hosts
        assert window.filter_combo.count() == 4
        assert window.filter_combo.itemText(0) == "All"
        assert "google.com" in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]
        assert "cloudflare.com" in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]
        assert "8.8.8.8" in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]
    
    def test_filter_shows_all_by_default(self, window):
        """Verify 'All' filter shows all measurements."""
        # Add measurements for different hosts
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        m2 = Measurement(ts=datetime.now(), host="cloudflare.com", latency_ms=15.0, loss=False)
        m3 = Measurement(ts=datetime.now(), host="8.8.8.8", latency_ms=20.0, loss=False)
        
        window.measurement_model.append_measurement(m1)
        window.measurement_model.append_measurement(m2)
        window.measurement_model.append_measurement(m3)
        
        # With "All" filter, proxy should show all 3 rows
        assert window.proxy_model.rowCount() == 3
    
    def test_filter_by_specific_host(self, window):
        """Verify filtering by specific host shows only that host's measurements."""
        # Add measurements for different hosts
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        m2 = Measurement(ts=datetime.now(), host="cloudflare.com", latency_ms=15.0, loss=False)
        m3 = Measurement(ts=datetime.now(), host="google.com", latency_ms=12.0, loss=False)
        
        window.measurement_model.append_measurement(m1)
        window.measurement_model.append_measurement(m2)
        window.measurement_model.append_measurement(m3)
        
        # Filter to google.com
        window.filter_combo.setCurrentText("google.com")
        
        # Should show only 2 google.com measurements
        assert window.proxy_model.rowCount() == 2
        
        # Verify the visible rows are correct
        for row in range(window.proxy_model.rowCount()):
            index = window.proxy_model.index(row, 1)  # Host column
            host = window.proxy_model.data(index, Qt.DisplayRole)
            assert host == "google.com"
    
    def test_filter_switch_between_hosts(self, window):
        """Verify switching filters works correctly."""
        # Add measurements
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        m2 = Measurement(ts=datetime.now(), host="cloudflare.com", latency_ms=15.0, loss=False)
        m3 = Measurement(ts=datetime.now(), host="8.8.8.8", latency_ms=20.0, loss=False)
        
        window.measurement_model.append_measurement(m1)
        window.measurement_model.append_measurement(m2)
        window.measurement_model.append_measurement(m3)
        
        # Filter to cloudflare.com
        window.filter_combo.setCurrentText("cloudflare.com")
        assert window.proxy_model.rowCount() == 1
        
        # Switch to 8.8.8.8
        window.filter_combo.setCurrentText("8.8.8.8")
        assert window.proxy_model.rowCount() == 1
        
        # Switch back to All
        window.filter_combo.setCurrentText("All")
        assert window.proxy_model.rowCount() == 3
    
    def test_sorting_enabled(self, window):
        """Verify table sorting is enabled."""
        # Check that sorting is enabled on the table
        assert window.table.isSortingEnabled()
    
    def test_proxy_model_configuration(self, window):
        """Verify proxy model is configured correctly."""
        # Verify proxy model settings
        assert window.proxy_model.sourceModel() == window.measurement_model
        assert window.proxy_model.filterKeyColumn() == 1  # Host column
        assert window.proxy_model.filterCaseSensitivity() == Qt.CaseInsensitive
    
    def test_new_host_added_to_filter(self, window):
        """Verify new hosts are added to filter dropdown."""
        initial_count = window.filter_combo.count()
        
        # Simulate receiving a measurement from a new host
        m = Measurement(ts=datetime.now(), host="example.com", latency_ms=25.0, loss=False)
        window.on_sample_ready(m, 0, "example.com")
        
        # Filter dropdown should have one more item
        assert window.filter_combo.count() == initial_count + 1
        assert "example.com" in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]
    
    def test_duplicate_hosts_not_added_to_filter(self, window):
        """Verify duplicate hosts don't create multiple filter entries."""
        initial_count = window.filter_combo.count()
        
        # Add multiple measurements from the same host
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        m2 = Measurement(ts=datetime.now(), host="google.com", latency_ms=12.0, loss=False)
        
        window.on_sample_ready(m1, 0, "google.com")
        window.on_sample_ready(m2, 0, "google.com")
        
        # Filter dropdown count should not change (google.com already exists)
        assert window.filter_combo.count() == initial_count
    
    def test_filter_empty_results(self, window):
        """Verify filtering with no matching results shows empty table."""
        # Add measurements for one host
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        window.measurement_model.append_measurement(m1)
        
        # Filter to a different host (that has no measurements)
        window.filter_combo.setCurrentText("cloudflare.com")
        
        # Should show 0 rows
        assert window.proxy_model.rowCount() == 0
    
    def test_source_model_unchanged_by_filter(self, window):
        """Verify filtering doesn't modify the source model."""
        # Add measurements
        m1 = Measurement(ts=datetime.now(), host="google.com", latency_ms=10.0, loss=False)
        m2 = Measurement(ts=datetime.now(), host="cloudflare.com", latency_ms=15.0, loss=False)
        
        window.measurement_model.append_measurement(m1)
        window.measurement_model.append_measurement(m2)
        
        # Source model should have 2 rows
        source_count = window.measurement_model.rowCount()
        assert source_count == 2
        
        # Filter to one host
        window.filter_combo.setCurrentText("google.com")
        
        # Source model should still have 2 rows (unchanged)
        assert window.measurement_model.rowCount() == source_count
        
        # But proxy should show only 1
        assert window.proxy_model.rowCount() == 1
    
    def test_add_host_updates_filter_dropdown(self, window):
        """Verify manually adding a host updates the filter dropdown."""
        initial_count = window.filter_combo.count()
        
        # Add a new host via the UI
        window.host_input.setText("new-host.com")
        window.add_host()
        
        # Filter dropdown should have the new host
        assert window.filter_combo.count() == initial_count + 1
        assert "new-host.com" in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]
    
    def test_remove_host_updates_filter_dropdown(self, window):
        """Verify removing a host updates the filter dropdown."""
        # Select first host in list
        window.host_list.setCurrentRow(0)
        first_host = window.host_list.currentItem().text()
        
        initial_count = window.filter_combo.count()
        
        # Remove the host
        window.remove_host()
        
        # Filter dropdown should have one less item
        assert window.filter_combo.count() == initial_count - 1
        assert first_host not in [window.filter_combo.itemText(i) for i in range(window.filter_combo.count())]

