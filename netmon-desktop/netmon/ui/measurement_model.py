"""Qt model for measurement data using model/view pattern."""

from collections import deque
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from netmon.models import Measurement


class MeasurementModel(QAbstractTableModel):
    """Table model for network measurements.

    Uses Qt's model/view pattern for efficient table updates. Stores measurements
    in a deque with automatic row limit management via beginRemoveRows/endRemoveRows.
    """

    def __init__(self, max_rows: int = 300, parent=None):
        super().__init__(parent)
        self._measurements = deque()  # No maxlen - we manage manually
        self._max_rows = max_rows

        # Column definitions
        self._columns = ["Time", "Host", "Latency (ms)", "Lost"]

        # Cached strings to reduce allocations
        self._loss_yes = "Yes"
        self._loss_no = "No"
        self._loss_dash = "--"

    def rowCount(self, parent=QModelIndex()):
        """Return the number of rows (measurements)."""
        if parent.isValid():
            return 0
        return len(self._measurements)

    def columnCount(self, parent=QModelIndex()):
        """Return the number of columns."""
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        """Return data for a given cell."""
        if not index.isValid():
            return None

        if index.row() >= len(self._measurements) or index.row() < 0:
            return None

        measurement = self._measurements[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:  # Time
                return measurement.ts.strftime("%H:%M:%S")
            elif col == 1:  # Host
                return measurement.host
            elif col == 2:  # Latency
                if measurement.loss:
                    return self._loss_dash
                else:
                    return f"{measurement.latency_ms:.2f}"
            elif col == 3:  # Lost
                return self._loss_yes if measurement.loss else self._loss_no

        elif role == Qt.TextAlignmentRole:
            if col == 2:  # Latency - right aligned
                return Qt.AlignRight | Qt.AlignVCenter
            elif col == 3:  # Lost - centered
                return Qt.AlignCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return header data."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
        return None

    def flags(self, index):
        """Return item flags (read-only by default)."""
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def append_measurement(self, measurement: Measurement):
        """Append a new measurement to the model.

        If the model is at capacity, the oldest row is removed first using
        beginRemoveRows/endRemoveRows, then the new row is added using
        beginInsertRows/endInsertRows. This ensures proper view synchronization.
        """
        # Check if we need to remove the oldest row first
        at_capacity = len(self._measurements) >= self._max_rows

        if at_capacity:
            # Remove oldest row (index 0) before adding new one
            self.beginRemoveRows(QModelIndex(), 0, 0)
            self._measurements.popleft()  # Manually remove oldest
            self.endRemoveRows()

        # Add the new row at the end
        new_row = len(self._measurements)
        self.beginInsertRows(QModelIndex(), new_row, new_row)
        self._measurements.append(measurement)
        self.endInsertRows()

    def clear(self):
        """Clear all measurements from the model."""
        if len(self._measurements) == 0:
            return

        self.beginRemoveRows(QModelIndex(), 0, len(self._measurements) - 1)
        self._measurements.clear()
        self.endRemoveRows()

    def get_measurements(self):
        """Get all measurements (for export, statistics, etc.)."""
        return list(self._measurements)
