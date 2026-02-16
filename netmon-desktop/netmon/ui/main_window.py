"""Main window for NetMon application."""

import csv
import logging
import statistics
from collections import deque
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QLineEdit,
    QListWidget,
    QComboBox,
    QTableView,
    QHeaderView,
    QGroupBox,
    QFileDialog,
    QCheckBox,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QCloseEvent
from netmon.collector import Collector, FakeCollectorAdapter
from netmon.scheduler import MultiHostScheduler
from netmon.ui.measurement_model import MeasurementModel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, collector: Collector | None = None):
        super().__init__()
        self.setWindowTitle("NetMon - Multi-Host Monitor")
        self.setGeometry(100, 100, 1000, 700)

        # Initialize collector
        collector = collector if collector is not None else FakeCollectorAdapter()

        # Sampling interval configuration
        self.INTERVAL_OPTIONS = {"200 ms": 200, "500 ms": 500, "1000 ms": 1000, "2000 ms": 2000}
        self.DEFAULT_INTERVAL_TEXT = "1000 ms"
        self.sample_interval_ms = self.INTERVAL_OPTIONS[self.DEFAULT_INTERVAL_TEXT]

        # Initialize scheduler (centralized multi-host scheduler)
        self.scheduler = MultiHostScheduler(
            collector=collector,
            interval_ms=self.sample_interval_ms,
            max_concurrent=4,  # Global concurrency limit
        )
        self.scheduler.sample_ready.connect(self.on_sample_ready)
        self.scheduler.error.connect(self.on_sample_error)

        # Data storage
        self.max_table_rows = 300
        self.measurement_model = MeasurementModel(max_rows=self.max_table_rows)
        
        # Proxy model for filtering and sorting
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.measurement_model)
        self.proxy_model.setFilterKeyColumn(1)  # Filter on Host column (index 1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # Per-host statistics tracking (keyed by host)
        self.host_stats = {}  # {host: {latencies: deque, samples: deque}}
        
        # Track hosts for filter dropdown
        self.filter_hosts = set()  # Set of unique hosts
        
        # Auto-scroll control ("follow tail" behavior)
        self.follow_tail = True  # Follow new data by default
        self._user_disabled_follow_tail = False  # Track explicit user disable

        # Set up the main UI
        self.setup_ui()
        
        # Add default hosts
        for host in ["google.com", "cloudflare.com", "8.8.8.8"]:
            self.scheduler.add_host(host)
            self.host_list.addItem(host)
            self.host_stats[host] = {
                "latencies": deque(maxlen=30),
                "samples": deque(maxlen=50),
            }
            # Add to filter dropdown
            self.filter_hosts.add(host)
            self.filter_combo.addItem(host)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle application close event - clean up resources."""
        # Stop monitoring via scheduler
        self.scheduler.stop_monitoring()

        # Wait for thread pool to finish (with timeout)
        self.scheduler.thread_pool.waitForDone(1000)  # 1 second timeout

        super().closeEvent(event)

    def setup_ui(self):
        """Set up the main user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout - horizontal split
        main_layout = QHBoxLayout(central_widget)

        # Left control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel, 0)  # Fixed width

        # Right measurement area
        measurement_area = self.create_measurement_area()
        main_layout.addWidget(measurement_area, 1)  # Expandable

    def create_control_panel(self):
        """Create the left control panel."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Box)
        panel.setFixedWidth(250)

        layout = QVBoxLayout(panel)

        # Title
        title = QLabel("Control Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px;")
        layout.addWidget(title)

        # Host list management
        host_group = QGroupBox("Target Hosts")
        host_layout = QVBoxLayout(host_group)

        # Host input
        input_layout = QHBoxLayout()
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Enter host...")
        self.host_input.returnPressed.connect(self.add_host)
        input_layout.addWidget(self.host_input)
        
        self.add_host_button = QPushButton("+")
        self.add_host_button.setFixedWidth(30)
        self.add_host_button.clicked.connect(self.add_host)
        input_layout.addWidget(self.add_host_button)
        host_layout.addLayout(input_layout)

        # Host list
        self.host_list = QListWidget()
        self.host_list.setMaximumHeight(120)
        self.host_list.currentItemChanged.connect(self.on_host_selection_changed)
        host_layout.addWidget(self.host_list)
        
        # Remove host button
        self.remove_host_button = QPushButton("Remove Selected")
        self.remove_host_button.clicked.connect(self.remove_host)
        host_layout.addWidget(self.remove_host_button)
        
        layout.addWidget(host_group)

        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Start button
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.clicked.connect(self.start_monitoring)
        controls_layout.addWidget(self.start_button)

        # Stop button
        self.stop_button = QPushButton("Stop Monitoring")
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)  # Initially disabled
        controls_layout.addWidget(self.stop_button)

        # Clear Data button
        self.clear_button = QPushButton("Clear Data")
        self.clear_button.clicked.connect(self.clear_data)
        controls_layout.addWidget(self.clear_button)

        # Export CSV button
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self.export_csv)
        controls_layout.addWidget(self.export_button)

        # Sampling interval selector
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Interval:")
        interval_layout.addWidget(interval_label)

        self.interval_combo = QComboBox()
        self.interval_combo.addItems(list(self.INTERVAL_OPTIONS.keys()))
        self.interval_combo.setCurrentText(self.DEFAULT_INTERVAL_TEXT)
        self.interval_combo.currentTextChanged.connect(self.on_interval_changed)
        interval_layout.addWidget(self.interval_combo)

        controls_layout.addLayout(interval_layout)
        
        # Concurrency info
        self.concurrency_label = QLabel("Max jobs: 4")
        self.concurrency_label.setStyleSheet("font-size: 10px; color: gray;")
        controls_layout.addWidget(self.concurrency_label)

        layout.addWidget(controls_group)

        # Summary statistics (per-host)
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_host_label = QLabel("Host: (select one)")
        self.stats_host_label.setStyleSheet("font-weight: bold; font-size: 10px;")
        stats_layout.addWidget(self.stats_host_label)

        self.latency_label = QLabel("Latency: --")
        self.jitter_label = QLabel("Jitter: --")
        self.loss_label = QLabel("Loss: --")

        for label in [self.latency_label, self.jitter_label, self.loss_label]:
            label.setStyleSheet("padding: 5px; font-family: monospace;")
            stats_layout.addWidget(label)

        layout.addWidget(stats_group)
        
        # View options
        view_group = QGroupBox("View Options")
        view_layout = QVBoxLayout(view_group)
        
        self.follow_tail_checkbox = QCheckBox("Follow Tail")
        self.follow_tail_checkbox.setChecked(True)
        self.follow_tail_checkbox.setToolTip("Auto-scroll to newest data (disabled when sorting)")
        self.follow_tail_checkbox.stateChanged.connect(self.on_follow_tail_toggled)
        view_layout.addWidget(self.follow_tail_checkbox)
        
        layout.addWidget(view_group)

        # Add some spacing
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        return panel

    def create_measurement_area(self):
        """Create the right measurement area with table."""
        area = QFrame()
        area.setFrameStyle(QFrame.Box)

        layout = QVBoxLayout(area)

        # Title
        title = QLabel("Live Measurements")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin: 10px;")
        layout.addWidget(title)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter by host:")
        filter_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All")
        self.filter_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)

        # Create table view with proxy model
        self.table = QTableView()
        self.table.setModel(self.proxy_model)  # Use proxy, not source model
        self.table.setSortingEnabled(True)  # Enable sorting by clicking headers

        # Configure table appearance
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Host
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Latency
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Lost

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        
        # Connect signals for auto-scroll control
        scrollbar = self.table.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scrollbar_changed)
        header.sortIndicatorChanged.connect(self.on_sort_changed)

        layout.addWidget(self.table)

        return area

    def add_host(self):
        """Add host from input field to monitoring list."""
        host = self.host_input.text().strip()
        if not host:
            return
        
        # Check if already in list
        if host in [self.host_list.item(i).text() for i in range(self.host_list.count())]:
            self.status_label.setText(f"Status: Host '{host}' already in list")
            return
        
        # Add to scheduler and UI
        self.scheduler.add_host(host)
        self.host_list.addItem(host)
        
        # Initialize stats for this host
        self.host_stats[host] = {
            "latencies": deque(maxlen=30),
            "samples": deque(maxlen=50),
        }
        
        # Add to filter dropdown if not already present
        if host not in self.filter_hosts:
            self.filter_hosts.add(host)
            self.filter_combo.addItem(host)
        
        # Clear input
        self.host_input.clear()
        self.status_label.setText(f"Status: Added '{host}'")
    
    def remove_host(self):
        """Remove selected host from monitoring list."""
        current_item = self.host_list.currentItem()
        if not current_item:
            self.status_label.setText("Status: No host selected")
            return
        
        host = current_item.text()
        
        # Remove from scheduler
        self.scheduler.remove_host(host)
        
        # Remove from UI
        self.host_list.takeItem(self.host_list.row(current_item))
        
        # Remove stats
        self.host_stats.pop(host, None)
        
        # Remove from filter dropdown
        if host in self.filter_hosts:
            self.filter_hosts.remove(host)
            index = self.filter_combo.findText(host)
            if index >= 0:
                self.filter_combo.removeItem(index)
        
        self.status_label.setText(f"Status: Removed '{host}'")
        
        # Clear stats display if no host selected
        if self.host_list.count() == 0:
            self.stats_host_label.setText("Host: (none)")
            self.latency_label.setText("Latency: --")
            self.jitter_label.setText("Jitter: --")
            self.loss_label.setText("Loss: --")
    
    def on_host_selection_changed(self):
        """Handle host selection change in list - update statistics display."""
        current_item = self.host_list.currentItem()
        if current_item:
            host = current_item.text()
            self.stats_host_label.setText(f"Host: {host}")
            self.update_statistics_for_host(host)
        else:
            self.stats_host_label.setText("Host: (select one)")
            self.latency_label.setText("Latency: --")
            self.jitter_label.setText("Jitter: --")
            self.loss_label.setText("Loss: --")

    def start_monitoring(self):
        """Handle start button click."""
        if self.scheduler.get_hosts():
            self.scheduler.start_monitoring()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            num_hosts = len(self.scheduler.get_hosts())
            self.status_label.setText(f"Status: Monitoring {num_hosts} host(s)")
        else:
            self.status_label.setText("Status: No hosts to monitor")

    def stop_monitoring(self):
        """Handle stop button click."""
        self.scheduler.stop_monitoring()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: Stopped")

    def clear_data(self):
        """Clear all monitoring data and reset UI state.

        Keeps monitoring state intact - if running, continues running but with fresh data.
        """
        # Clear model
        self.measurement_model.clear()
        
        # Clear per-host statistics
        for host in self.host_stats:
            self.host_stats[host]["latencies"].clear()
            self.host_stats[host]["samples"].clear()
        
        # Update statistics display
        current_item = self.host_list.currentItem()
        if current_item:
            self.update_statistics_for_host(current_item.text())
        
        # Update status
        if self.scheduler.is_monitoring:
            self.status_label.setText("Status: Monitoring (Cleared)")
        else:
            self.status_label.setText("Status: Cleared")

    def export_csv(self):
        """Export measurements to CSV file."""
        measurements = self.measurement_model.get_measurements()
        if not measurements:
            self.status_label.setText("Status: No data to export")
            return

        # Open save dialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Measurements to CSV", "measurements.csv", "CSV Files (*.csv)"
        )

        # If user cancelled, do nothing
        if not filename:
            return

        # Ensure filename has .csv extension
        if not filename.lower().endswith(".csv"):
            filename += ".csv"

        try:
            # Write CSV with proper encoding and newline handling
            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(["ts_iso", "host", "latency_ms", "loss"])

                # Write measurements in chronological order
                for measurement in measurements:
                    # Format timestamp as ISO string
                    ts_iso = measurement.ts.isoformat()

                    # Format latency: empty string if lost, otherwise 2 decimal places
                    if measurement.loss:
                        latency_str = ""
                    else:
                        latency_str = f"{measurement.latency_ms:.2f}"

                    # Write row
                    writer.writerow(
                        [
                            ts_iso,
                            measurement.host,
                            latency_str,
                            measurement.loss,  # True/False
                        ]
                    )

            self.status_label.setText("Status: Exported CSV")

        except (IOError, PermissionError, OSError) as e:
            # Handle file system related errors with specific error type
            self.status_label.setText(f"Status: Export failed - {type(e).__name__}")
        except UnicodeEncodeError:
            # Handle encoding issues
            self.status_label.setText("Status: Export failed - Encoding error")
        except Exception as e:
            # Handle any other unexpected errors without crashing the UI
            # Log the actual error for debugging while showing user-friendly message
            print(f"Unexpected error during CSV export: {e}")
            self.status_label.setText("Status: Export failed - Unexpected error")

    def on_interval_changed(self, text: str):
        """Handle sampling interval change."""
        # Use robust mapping instead of string parsing
        if text in self.INTERVAL_OPTIONS:
            ms_value = self.INTERVAL_OPTIONS[text]
            self.scheduler.set_interval(ms_value)

    def on_sample_ready(self, sample, generation_id, host):
        """Handle measurement result from scheduler.

        Args:
            sample: Measurement object
            generation_id: Generation ID when worker was scheduled
            host: Host that was sampled
        """
        # Add to table model
        self.measurement_model.append_measurement(sample)
        
        # Add host to filter dropdown if new
        if host not in self.filter_hosts:
            self.filter_hosts.add(host)
            self.filter_combo.addItem(host)
        
        # Update per-host statistics
        if host in self.host_stats:
            self.host_stats[host]["samples"].append(sample)
            if not sample.loss and sample.latency_ms is not None:
                self.host_stats[host]["latencies"].append(sample.latency_ms)
        
        # Maybe auto-scroll to latest row (if following tail)
        self.maybe_autoscroll()
        
        # Update statistics display if this host is selected
        current_item = self.host_list.currentItem()
        if current_item and current_item.text() == host:
            self.update_statistics_for_host(host)

    def on_sample_error(self, host, error_msg):
        """Handle sampling error from scheduler.
        
        Args:
            host: Host that had an error
            error_msg: Error message
        """
        logger.error("Sampling error for %s: %s", host, error_msg)
        if self.scheduler.is_monitoring:
            self.status_label.setText(f"Status: Error on {host}")

    def on_filter_changed(self, text: str):
        """Handle filter dropdown selection change.
        
        Args:
            text: Selected filter text ("All" or a hostname)
        """
        if text == "All":
            # Clear filter to show all rows
            self.proxy_model.setFilterFixedString("")
        else:
            # Filter to show only rows matching the selected host
            self.proxy_model.setFilterFixedString(text)
    
    def update_statistics_for_host(self, host: str):
        """Update statistics display for a specific host.
        
        Args:
            host: Host to show statistics for
        """
        if host not in self.host_stats:
            self.latency_label.setText("Latency: --")
            self.jitter_label.setText("Jitter: --")
            self.loss_label.setText("Loss: --")
            return
        
        samples = self.host_stats[host]["samples"]
        latencies = self.host_stats[host]["latencies"]
        
        if not samples:
            self.latency_label.setText("Latency: --")
            self.jitter_label.setText("Jitter: --")
            self.loss_label.setText("Loss: --")
            return
        
        # Calculate latency (last non-lost sample)
        last_latency = None
        for sample in reversed(samples):
            if not sample.loss and sample.latency_ms is not None:
                last_latency = sample.latency_ms
                break
        
        if last_latency is not None:
            self.latency_label.setText(f"Latency: {last_latency:.2f} ms")
        else:
            self.latency_label.setText("Latency: -- ms")
        
        # Calculate jitter (standard deviation of recent latencies)
        if len(latencies) >= 2:
            jitter = statistics.stdev(latencies)
            self.jitter_label.setText(f"Jitter: {jitter:.2f} ms")
        else:
            self.jitter_label.setText("Jitter: -- ms")
        
        # Calculate loss percentage (over recent samples)
        if len(samples) > 0:
            lost_count = sum(1 for s in samples if s.loss)
            loss_percent = (lost_count / len(samples)) * 100
            self.loss_label.setText(f"Loss: {loss_percent:.1f}%")
        else:
            self.loss_label.setText("Loss: --%")
    
    def is_sorting_active(self) -> bool:
        """Check if table is currently sorted by user.
        
        Returns:
            True if sorting is enabled and a sort column is active
        """
        if not self.table.isSortingEnabled():
            return False
        
        header = self.table.horizontalHeader()
        return header.sortIndicatorSection() >= 0
    
    def is_near_bottom(self, threshold: int = 5) -> bool:
        """Check if scrollbar is near the bottom.
        
        Args:
            threshold: Number of steps from max to consider "near bottom"
        
        Returns:
            True if within threshold steps of bottom
        """
        scrollbar = self.table.verticalScrollBar()
        return (scrollbar.maximum() - scrollbar.value()) <= threshold
    
    def maybe_autoscroll(self):
        """Conditionally scroll to bottom if follow_tail is enabled and appropriate."""
        if self.follow_tail and not self.is_sorting_active():
            self.table.scrollToBottom()
    
    def on_scrollbar_changed(self, value: int):
        """Handle scrollbar value changes to detect user scrolling.
        
        Args:
            value: Current scrollbar value
        """
        # Ignore if user explicitly disabled follow tail via checkbox
        if self._user_disabled_follow_tail:
            return
        
        # If user scrolls to near bottom and sorting is inactive, re-enable follow_tail
        if self.is_near_bottom() and not self.is_sorting_active():
            if not self.follow_tail:
                self.follow_tail = True
                # Block signals to prevent on_follow_tail_toggled from overwriting _user_disabled_follow_tail
                self.follow_tail_checkbox.blockSignals(True)
                self.follow_tail_checkbox.setChecked(True)
                self.follow_tail_checkbox.blockSignals(False)
        # If user scrolls away from bottom, disable follow_tail
        elif not self.is_near_bottom():
            if self.follow_tail:
                self.follow_tail = False
                # Block signals to prevent on_follow_tail_toggled from overwriting _user_disabled_follow_tail
                self.follow_tail_checkbox.blockSignals(True)
                self.follow_tail_checkbox.setChecked(False)
                self.follow_tail_checkbox.blockSignals(False)
    
    def on_sort_changed(self, column: int, order):
        """Handle sort indicator changes - disable follow_tail when sorting.
        
        Args:
            column: Column index that was sorted
            order: Sort order (ascending/descending)
        """
        # When user activates sorting, disable follow_tail
        if self.is_sorting_active():
            self.follow_tail = False
            # Block signals to prevent on_follow_tail_toggled from overwriting _user_disabled_follow_tail
            self.follow_tail_checkbox.blockSignals(True)
            self.follow_tail_checkbox.setChecked(False)
            self.follow_tail_checkbox.blockSignals(False)
    
    def on_follow_tail_toggled(self, state: int):
        """Handle Follow Tail checkbox toggle.
        
        Args:
            state: Qt.Checked or Qt.Unchecked
        """
        checked = (state == Qt.CheckState.Checked.value)
        
        # If user is enabling follow_tail while sorting is active, prevent it
        if checked and self.is_sorting_active():
            self.follow_tail = False
            # Block signals to prevent recursion
            self.follow_tail_checkbox.blockSignals(True)
            self.follow_tail_checkbox.setChecked(False)
            self.follow_tail_checkbox.blockSignals(False)
            self.status_label.setText("Status: Follow Tail disabled while sorting")
            return
        
        # Update state
        self.follow_tail = checked
        self._user_disabled_follow_tail = not checked
        
        # If enabling, scroll to bottom immediately
        if checked:
            self.maybe_autoscroll()
