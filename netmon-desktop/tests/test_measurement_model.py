"""Tests for MeasurementModel (Qt model/view pattern)."""

from datetime import datetime
from PySide6.QtCore import Qt, QModelIndex
from netmon.models import Measurement
from netmon.ui.measurement_model import MeasurementModel


class TestMeasurementModel:
    """Test MeasurementModel behavior."""

    def test_initial_state(self):
        """Test model starts empty with correct column count."""
        model = MeasurementModel(max_rows=10)
        assert model.rowCount() == 0
        assert model.columnCount() == 4

    def test_column_headers(self):
        """Test column headers are correct."""
        model = MeasurementModel()
        assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Time"
        assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Host"
        assert model.headerData(2, Qt.Horizontal, Qt.DisplayRole) == "Latency (ms)"
        assert model.headerData(3, Qt.Horizontal, Qt.DisplayRole) == "Lost"

    def test_append_single_measurement(self):
        """Test appending a single measurement."""
        model = MeasurementModel(max_rows=10)
        measurement = Measurement(ts=datetime.now(), host="test.com", latency_ms=10.5, loss=False)

        model.append_measurement(measurement)

        assert model.rowCount() == 1
        assert model.data(model.index(0, 1), Qt.DisplayRole) == "test.com"
        assert model.data(model.index(0, 2), Qt.DisplayRole) == "10.50"
        assert model.data(model.index(0, 3), Qt.DisplayRole) == "No"

    def test_append_multiple_measurements(self):
        """Test appending multiple measurements."""
        model = MeasurementModel(max_rows=10)

        for i in range(5):
            measurement = Measurement(
                ts=datetime.now(), host=f"host{i}.com", latency_ms=float(i), loss=False
            )
            model.append_measurement(measurement)

        assert model.rowCount() == 5

    def test_row_limit_enforced(self):
        """Test that row count doesn't exceed max_rows."""
        model = MeasurementModel(max_rows=3)

        # Add 5 measurements (exceeds max_rows)
        for i in range(5):
            measurement = Measurement(
                ts=datetime.now(), host=f"host{i}.com", latency_ms=float(i), loss=False
            )
            model.append_measurement(measurement)

        # Should only have 3 rows (most recent)
        assert model.rowCount() == 3

        # Verify oldest measurements were removed
        # Should have host2, host3, host4 (not host0, host1)
        assert model.data(model.index(0, 1), Qt.DisplayRole) == "host2.com"
        assert model.data(model.index(1, 1), Qt.DisplayRole) == "host3.com"
        assert model.data(model.index(2, 1), Qt.DisplayRole) == "host4.com"

    def test_clear(self):
        """Test clearing all measurements."""
        model = MeasurementModel(max_rows=10)

        # Add some measurements
        for i in range(5):
            measurement = Measurement(
                ts=datetime.now(), host=f"host{i}.com", latency_ms=float(i), loss=False
            )
            model.append_measurement(measurement)

        assert model.rowCount() == 5

        # Clear
        model.clear()
        assert model.rowCount() == 0

    def test_loss_measurement_display(self):
        """Test that loss measurements display correctly."""
        model = MeasurementModel()
        measurement = Measurement(ts=datetime.now(), host="lost.com", latency_ms=None, loss=True)

        model.append_measurement(measurement)

        assert model.data(model.index(0, 2), Qt.DisplayRole) == "--"
        assert model.data(model.index(0, 3), Qt.DisplayRole) == "Yes"

    def test_time_formatting(self):
        """Test time column displays HH:MM:SS format."""
        model = MeasurementModel()
        ts = datetime(2026, 2, 16, 14, 30, 45)
        measurement = Measurement(ts=ts, host="test.com", latency_ms=10.0, loss=False)

        model.append_measurement(measurement)

        time_str = model.data(model.index(0, 0), Qt.DisplayRole)
        assert time_str == "14:30:45"

    def test_latency_alignment(self):
        """Test that latency column is right-aligned."""
        model = MeasurementModel()
        measurement = Measurement(ts=datetime.now(), host="test.com", latency_ms=10.5, loss=False)
        model.append_measurement(measurement)

        alignment = model.data(model.index(0, 2), Qt.TextAlignmentRole)
        assert alignment == (Qt.AlignRight | Qt.AlignVCenter)

    def test_lost_alignment(self):
        """Test that lost column is centered."""
        model = MeasurementModel()
        measurement = Measurement(ts=datetime.now(), host="test.com", latency_ms=10.0, loss=False)
        model.append_measurement(measurement)

        alignment = model.data(model.index(0, 3), Qt.TextAlignmentRole)
        assert alignment == Qt.AlignCenter

    def test_get_measurements(self):
        """Test getting all measurements for export."""
        model = MeasurementModel(max_rows=10)

        measurements = []
        for i in range(3):
            m = Measurement(ts=datetime.now(), host=f"host{i}.com", latency_ms=float(i), loss=False)
            measurements.append(m)
            model.append_measurement(m)

        retrieved = model.get_measurements()
        assert len(retrieved) == 3
        assert all(isinstance(m, Measurement) for m in retrieved)

    def test_invalid_index(self):
        """Test that invalid indices return None."""
        model = MeasurementModel()
        measurement = Measurement(ts=datetime.now(), host="test.com", latency_ms=10.0, loss=False)
        model.append_measurement(measurement)

        # Out of bounds
        assert model.data(model.index(10, 0), Qt.DisplayRole) is None
        assert model.data(model.index(0, 10), Qt.DisplayRole) is None

        # Invalid index
        invalid_index = QModelIndex()
        assert model.data(invalid_index, Qt.DisplayRole) is None

    def test_flags(self):
        """Test that cells are read-only but selectable."""
        model = MeasurementModel()
        measurement = Measurement(ts=datetime.now(), host="test.com", latency_ms=10.0, loss=False)
        model.append_measurement(measurement)

        flags = model.flags(model.index(0, 0))
        assert flags & Qt.ItemIsEnabled
        assert flags & Qt.ItemIsSelectable
        assert not (flags & Qt.ItemIsEditable)
