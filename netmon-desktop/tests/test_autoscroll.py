"""Tests for auto-scroll (\"follow tail\") functionality."""

import pytest
from datetime import datetime
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QApplication
from netmon.ui.main_window import MainWindow
from netmon.collector import FakeCollectorAdapter
from netmon.models import Measurement


def process_events():
    """Process pending Qt events to ensure UI updates complete."""
    QCoreApplication.processEvents()


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
    # Show window and ensure it's rendered
    win.show()
    process_events()
    # Clear any default sort indicator
    header = win.table.horizontalHeader()
    header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
    process_events()
    yield win
    # Cleanup
    win.scheduler.stop_monitoring()
    win.scheduler.thread_pool.waitForDone(100)
    win.close()
    win.deleteLater()
    process_events()


class TestAutoScroll:
    """Test suite for auto-scroll (follow tail) behavior."""

    def test_initial_follow_tail_state(self, window):
        """Verify follow_tail is enabled by default."""
        assert window.follow_tail is True
        assert window.follow_tail_checkbox.isChecked()
        assert window._user_disabled_follow_tail is False
    
    def test_is_sorting_active_initially_false(self, window):
        """Verify sorting is not active initially."""
        assert window.is_sorting_active() is False
    
    def test_is_sorting_active_after_click(self, window):
        """Verify is_sorting_active detects when user sorts."""
        # Simulate clicking header to sort
        header = window.table.horizontalHeader()
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        
        assert window.is_sorting_active() is True
    
    def test_is_near_bottom_empty_table(self, window):
        """Verify is_near_bottom returns True for empty table."""
        # Empty table scrollbar should be at max
        assert window.is_near_bottom() is True
    
    def test_is_near_bottom_with_data(self, window):
        """Verify is_near_bottom detects position correctly."""
        # Add enough data to create scrollbar (50 rows should be plenty)
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Scroll to bottom
        window.table.scrollToBottom()
        process_events()
        assert window.is_near_bottom() is True
        
        # Scroll to top
        window.table.scrollToTop()
        process_events()
        # Give it a moment to complete scroll
        assert window.is_near_bottom() is False
    
    def test_maybe_autoscroll_when_enabled(self, window):
        """Verify maybe_autoscroll scrolls when follow_tail is True."""
        # Add enough data to create scrollbar
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Scroll to top
        window.table.scrollToTop()
        process_events()
        assert not window.is_near_bottom()
        
        # Call maybe_autoscroll with follow_tail enabled
        window.follow_tail = True
        window.maybe_autoscroll()
        process_events()
        
        # Should now be at bottom
        assert window.is_near_bottom()
    
    def test_maybe_autoscroll_when_disabled(self, window):
        """Verify maybe_autoscroll does nothing when follow_tail is False."""
        # Add enough data
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Scroll to top and disable follow_tail
        window.table.scrollToTop()
        process_events()
        window.follow_tail = False
        
        # Call maybe_autoscroll
        window.maybe_autoscroll()
        process_events()
        
        # Should still be at top
        assert not window.is_near_bottom()
    
    def test_maybe_autoscroll_when_sorting(self, window):
        """Verify maybe_autoscroll does nothing when sorting is active."""
        # Add enough data
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Enable sorting and scroll to top
        header = window.table.horizontalHeader()
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        process_events()
        window.table.scrollToTop()
        process_events()
        
        # Call maybe_autoscroll with follow_tail enabled
        window.follow_tail = True
        window.maybe_autoscroll()
        process_events()
        
        # Should NOT scroll (sorting is active)
        assert not window.is_near_bottom()
    
    def test_on_sort_changed_disables_follow_tail(self, window):
        """Verify sorting a column disables follow_tail."""
        assert window.follow_tail is True
        
        # Simulate sort indicator change
        header = window.table.horizontalHeader()
        header.setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        
        # Manually trigger handler (signal may not fire in test)
        window.on_sort_changed(1, Qt.SortOrder.AscendingOrder)
        
        assert window.follow_tail is False
        assert window.follow_tail_checkbox.isChecked() is False
    
    def test_checkbox_toggle_enables_follow_tail(self, window):
        """Verify checking the checkbox enables follow_tail."""
        # Disable first
        window.follow_tail = False
        window.follow_tail_checkbox.setChecked(False)
        process_events()
        
        # Ensure no sorting is active
        assert not window.is_sorting_active()
        
        # Enable via checkbox
        window.follow_tail_checkbox.setChecked(True)
        process_events()
        
        assert window.follow_tail is True
        assert window._user_disabled_follow_tail is False
    
    def test_checkbox_toggle_disables_follow_tail(self, window):
        """Verify unchecking the checkbox disables follow_tail."""
        assert window.follow_tail is True
        
        # Disable via checkbox
        window.follow_tail_checkbox.setChecked(False)
        
        assert window.follow_tail is False
        assert window._user_disabled_follow_tail is True
    
    def test_checkbox_blocked_when_sorting(self, window):
        """Verify checkbox cannot enable follow_tail while sorting is active."""
        # Enable sorting
        header = window.table.horizontalHeader()
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        window.follow_tail = False
        
        # Try to enable via checkbox
        window.follow_tail_checkbox.setChecked(True)
        
        # Should remain disabled
        assert window.follow_tail is False
        assert window.follow_tail_checkbox.isChecked() is False
    
    def test_on_sample_ready_respects_follow_tail(self, window):
        """Verify on_sample_ready uses maybe_autoscroll instead of direct scrollToBottom."""
        # Add enough data to create scrollbar
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="google.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Scroll to top and disable follow_tail
        window.table.scrollToTop()
        process_events()
        window.follow_tail = False
        
        # Add new sample via on_sample_ready
        m = Measurement(ts=datetime.now(), host="google.com", latency_ms=99.0, loss=False)
        window.on_sample_ready(m, 0, "google.com")
        process_events()
        
        # Should NOT have auto-scrolled
        assert not window.is_near_bottom()
    
    def test_scrollbar_reactivates_follow_tail_at_bottom(self, window):
        """Verify scrolling back to bottom re-enables follow_tail."""
        # Add data and disable follow_tail
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        window.table.scrollToTop()
        process_events()
        window.follow_tail = False
        window._user_disabled_follow_tail = False  # Not explicitly disabled by user
        
        # Manually scroll to bottom
        window.table.scrollToBottom()
        process_events()
        
        # Simulate scrollbar change event
        scrollbar = window.table.verticalScrollBar()
        window.on_scrollbar_changed(scrollbar.value())
        process_events()
        
        # Should re-enable follow_tail
        assert window.follow_tail is True
        assert window.follow_tail_checkbox.isChecked() is True
    
    def test_scrollbar_respects_user_explicit_disable(self, window):
        """Verify scrolling to bottom doesn't re-enable if user explicitly disabled."""
        # Add data
        for i in range(30):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        # User explicitly disables via checkbox
        window.follow_tail_checkbox.setChecked(False)
        assert window._user_disabled_follow_tail is True
        
        # Scroll to bottom
        window.table.scrollToBottom()
        scrollbar = window.table.verticalScrollBar()
        window.on_scrollbar_changed(scrollbar.value())
        
        # Should NOT re-enable follow_tail
        assert window.follow_tail is False
    
    def test_scrollbar_disables_follow_tail_when_scrolling_up(self, window):
        """Verify scrolling away from bottom disables follow_tail."""
        # Add data
        for i in range(30):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        # Start at bottom with follow_tail enabled
        window.table.scrollToBottom()
        window.follow_tail = True
        
        # Scroll up
        window.table.scrollToTop()
        scrollbar = window.table.verticalScrollBar()
        window.on_scrollbar_changed(scrollbar.value())
        
        # Should disable follow_tail
        assert window.follow_tail is False
        assert window.follow_tail_checkbox.isChecked() is False
    
    def test_scroll_away_then_back_reenables_follow_tail(self, window):
        """Verify scrolling away then back to bottom re-enables follow_tail (regression test for signal blocking bug)."""
        # Add data
        for i in range(50):
            m = Measurement(ts=datetime.now(), host="test.com", latency_ms=float(i), loss=False)
            window.measurement_model.append_measurement(m)
        
        process_events()
        
        # Start at bottom with follow_tail enabled
        window.table.scrollToBottom()
        process_events()
        window.follow_tail = True
        window._user_disabled_follow_tail = False
        assert window.follow_tail_checkbox.isChecked() is True
        
        # Scroll away from bottom
        window.table.scrollToTop()
        process_events()
        scrollbar = window.table.verticalScrollBar()
        window.on_scrollbar_changed(scrollbar.value())
        process_events()
        
        # Should disable follow_tail, but NOT set _user_disabled_follow_tail
        assert window.follow_tail is False
        assert window.follow_tail_checkbox.isChecked() is False
        assert window._user_disabled_follow_tail is False, "_user_disabled_follow_tail should remain False (scroll-induced disable, not user click)"
        
        # Scroll back to bottom
        window.table.scrollToBottom()
        process_events()
        window.on_scrollbar_changed(scrollbar.value())
        process_events()
        
        # Should RE-ENABLE follow_tail automatically (this is the bug we're testing)
        assert window.follow_tail is True, "follow_tail should re-enable when scrolling back to bottom"
        assert window.follow_tail_checkbox.isChecked() is True
