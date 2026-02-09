"""Main window for NetMon application."""

import csv
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
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer, QThreadPool
from PySide6.QtGui import QCloseEvent
from netmon.collector import Collector, FakeCollectorAdapter
from netmon.workers import SampleWorker


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, collector: Collector | None = None):
        super().__init__()
        self.setWindowTitle("NetMon")
        self.setGeometry(100, 100, 1000, 700)

        # Initialize collector
        self.collector = collector if collector is not None else FakeCollectorAdapter()

        # Initialize monitoring state
        self.is_monitoring = False

        # Timer for regular sampling
        self.timer = QTimer()
        self.timer.timeout.connect(self.collect_sample)

        # Sampling interval configuration - single source of truth
        self.INTERVAL_OPTIONS = {"200 ms": 200, "500 ms": 500, "1000 ms": 1000, "2000 ms": 2000}
        self.DEFAULT_INTERVAL_TEXT = "1000 ms"
        self.sample_interval_ms = self.INTERVAL_OPTIONS[self.DEFAULT_INTERVAL_TEXT]
        
        # Threading for non-blocking sampling
        self.thread_pool = QThreadPool.globalInstance()
        self._in_flight = False
        self._current_worker = None  # Track current worker for cleanup

        # Data storage (keep last N samples)
        self.max_table_rows = 300
        self.measurements = deque(maxlen=self.max_table_rows)

        # Statistics tracking
        self.recent_latencies = deque(maxlen=30)  # For jitter calculation
        self.recent_samples = deque(maxlen=50)  # For loss calculation

        # Table state tracking
        self._table_initialized = False

        # Cached strings to reduce allocations in hot path
        self._loss_yes = "Yes"
        self._loss_no = "No"
        self._loss_dash = "--"

        # Set up the main UI
        self.setup_ui()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle application close event - clean up resources."""
        # Stop monitoring and timer
        if self.timer.isActive():
            self.timer.stop()
        self.is_monitoring = False
        
        # Clean up any in-flight worker
        if self._current_worker is not None:
            try:
                self._current_worker.signals.sample_ready.disconnect()
                self._current_worker.signals.error.disconnect() 
                self._current_worker.signals.finished.disconnect()
            except RuntimeError:
                pass  # Already disconnected
            self._current_worker = None
        
        # Wait for thread pool to finish (with timeout)
        self.thread_pool.waitForDone(1000)  # 1 second timeout
        
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

        # Host selection
        host_group = QGroupBox("Target Host")
        host_layout = QVBoxLayout(host_group)

        self.host_combo = QComboBox()
        self.host_combo.setEditable(True)
        self.host_combo.addItems(
            ["google.com", "cloudflare.com", "8.8.8.8", "1.1.1.1", "github.com"]
        )
        self.host_combo.setCurrentText("google.com")
        host_layout.addWidget(self.host_combo)
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

        layout.addWidget(controls_group)

        # Summary statistics
        stats_group = QGroupBox("Summary Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.latency_label = QLabel("Latency: --")
        self.jitter_label = QLabel("Jitter: --")
        self.loss_label = QLabel("Loss: --")

        for label in [self.latency_label, self.jitter_label, self.loss_label]:
            label.setStyleSheet("padding: 5px; font-family: monospace;")
            stats_layout.addWidget(label)

        layout.addWidget(stats_group)

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

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Time", "Host", "Latency (ms)", "Lost"])

        # Configure table appearance
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Host
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Latency
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Lost

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Initialize with 0 rows for clean append-only behavior
        self.table.setRowCount(0)

        layout.addWidget(self.table)

        return area

    def start_monitoring(self):
        """Handle start button click."""
        self.is_monitoring = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Status: Monitoring")

        # Start the timer with current interval
        self.timer.start(self.sample_interval_ms)

    def stop_monitoring(self):
        """Handle stop button click."""
        self.is_monitoring = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Status: Stopped")

        # Stop the timer
        self.timer.stop()
        
        # Note: In-flight workers will complete but their results will be ignored
        # due to the is_monitoring check in on_sample_ready()

    def clear_data(self):
        """Clear all monitoring data and reset UI state.

        Keeps monitoring state intact - if running, continues running but with fresh data.
        """
        # Clear all data collections
        self.measurements.clear()
        self.recent_samples.clear()
        self.recent_latencies.clear()

        # Clear the table
        self.table.setRowCount(0)

        # Reset statistics labels
        self.latency_label.setText("Latency: --")
        self.jitter_label.setText("Jitter: --")
        self.loss_label.setText("Loss: --")

        # Update status - show cleared but preserve monitoring state
        if self.is_monitoring:
            self.status_label.setText("Status: Monitoring (Cleared)")
        else:
            self.status_label.setText("Status: Cleared")

    def export_csv(self):
        """Export measurements to CSV file."""
        if not self.measurements:
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
                for measurement in self.measurements:
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
            self.set_sample_interval(ms_value)

    def set_sample_interval(self, ms: int):
        """Set the sampling interval and update timer if running."""
        self.sample_interval_ms = ms

        # If timer is currently active, update its interval immediately
        if self.timer.isActive():
            self.timer.setInterval(ms)

    def collect_sample(self):
        """Collect a new measurement sample asynchronously."""
        if not self.is_monitoring:
            return

        # Get current host from combo box
        host = self.host_combo.currentText().strip()
        if not host:
            return
        
        # Skip if already sampling (bounded concurrency)
        if self._in_flight:
            return
        
        # Mark as in-flight and start worker
        self._in_flight = True
        
        # Create and configure worker
        worker = SampleWorker(self.collector, host)
        worker.signals.sample_ready.connect(self.on_sample_ready)
        worker.signals.error.connect(self.on_sample_error)
        worker.signals.finished.connect(self.on_sample_finished)
        
        # Track current worker for cleanup
        self._current_worker = worker
        
        # Execute in thread pool
        self.thread_pool.start(worker)
    
    def on_sample_ready(self, sample):
        """Handle measurement result from worker thread."""
        # Only process if still monitoring (ignore late results)
        if not self.is_monitoring:
            return
            
        # Add to our collections
        self.measurements.append(sample)
        self.recent_samples.append(sample)

        # Track latencies for jitter calculation (only non-lost samples)
        if not sample.loss and sample.latency_ms is not None:
            self.recent_latencies.append(sample.latency_ms)

        # Append only the new sample to table (O(1) operation)
        self.append_measurement_to_table(sample)

        # Update statistics
        self.update_statistics()
    
    def on_sample_error(self, error_msg):
        """Handle sampling error from worker thread."""
        # Log error and update status if still monitoring
        print(f"Error collecting sample: {error_msg}")
        if self.is_monitoring:
            self.status_label.setText(f"Status: Sampling error - {error_msg}")
    
    def on_sample_finished(self):
        """Handle worker completion - clear in-flight flag and cleanup."""
        # Disconnect signals to prevent memory leaks
        if self._current_worker is not None:
            try:
                self._current_worker.signals.sample_ready.disconnect()
                self._current_worker.signals.error.disconnect()
                self._current_worker.signals.finished.disconnect()
            except RuntimeError:
                # Signals already disconnected - ignore
                pass
            self._current_worker = None
        
        self._in_flight = False

    def append_measurement_to_table(self, measurement):
        """Append a single measurement to the table (O(1) operation).

        This avoids the O(N) cost of redrawing the entire table each tick.
        Optimized to reduce allocations and improve performance.
        """
        # Insert new row at the end first
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)

        # Time column - optimize string formatting
        time_str = measurement.ts.strftime("%H:%M:%S")
        time_item = QTableWidgetItem(time_str)
        time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.table.setItem(row_position, 0, time_item)

        # Host column
        host_item = QTableWidgetItem(measurement.host)
        host_item.setFlags(host_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.table.setItem(row_position, 1, host_item)

        # Latency column (right-aligned) - reduce string allocations
        if measurement.loss:
            latency_str = self._loss_dash  # Reuse cached string
        else:
            # More efficient than f-string for this simple case
            latency_str = f"{measurement.latency_ms:.2f}"
        latency_item = QTableWidgetItem(latency_str)
        latency_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        latency_item.setFlags(latency_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.table.setItem(row_position, 2, latency_item)

        # Lost column (centered) - use cached strings
        lost_str = self._loss_yes if measurement.loss else self._loss_no
        lost_item = QTableWidgetItem(lost_str)
        lost_item.setTextAlignment(Qt.AlignCenter)
        lost_item.setFlags(lost_item.flags() & ~Qt.ItemIsEditable)  # Read-only
        self.table.setItem(row_position, 3, lost_item)

        # Remove oldest rows if we exceed capacity (no off-by-one issues)
        while self.table.rowCount() > self.max_table_rows:
            self.table.removeRow(0)

        # Keep latest row visible
        self.table.scrollToBottom()

    def update_statistics(self):
        """Update the summary statistics labels."""
        if not self.recent_samples:
            return

        # Calculate latency (last non-lost sample)
        last_latency = None
        for sample in reversed(self.recent_samples):
            if not sample.loss and sample.latency_ms is not None:
                last_latency = sample.latency_ms
                break

        if last_latency is not None:
            self.latency_label.setText(f"Latency: {last_latency:.2f} ms")
        else:
            self.latency_label.setText("Latency: -- ms")

        # Calculate jitter (standard deviation of recent latencies)
        if len(self.recent_latencies) >= 2:
            jitter = statistics.stdev(self.recent_latencies)
            self.jitter_label.setText(f"Jitter: {jitter:.2f} ms")
        else:
            self.jitter_label.setText("Jitter: -- ms")

        # Calculate loss percentage (over recent samples)
        if len(self.recent_samples) > 0:
            lost_count = sum(1 for s in self.recent_samples if s.loss)
            loss_percent = (lost_count / len(self.recent_samples)) * 100
            self.loss_label.setText(f"Loss: {loss_percent:.1f}%")
        else:
            self.loss_label.setText("Loss: --%")
