"""Tests for netmon.models.Measurement invariants."""

from datetime import datetime
from netmon.models import Measurement


class TestMeasurement:
    """Test Measurement dataclass behavior and invariants."""

    def test_measurement_valid_success(self):
        """Test valid successful measurement."""
        ts = datetime.now()
        measurement = Measurement(ts=ts, host="example.com", latency_ms=25.5, loss=False)

        assert measurement.ts == ts
        assert measurement.host == "example.com"
        assert measurement.latency_ms == 25.5
        assert measurement.loss is False

    def test_measurement_valid_loss(self):
        """Test valid lost measurement."""
        ts = datetime.now()
        measurement = Measurement(ts=ts, host="example.com", latency_ms=None, loss=True)

        assert measurement.ts == ts
        assert measurement.host == "example.com"
        assert measurement.latency_ms is None
        assert measurement.loss is True

    def test_post_init_enforces_loss_true_implies_no_latency(self):
        """Test __post_init__ invariant: loss=True forces latency_ms=None.

        When loss=True is specified, any provided latency_ms value should be
        overridden to None to maintain data consistency.
        """
        ts = datetime.now()
        measurement = Measurement(
            ts=ts,
            host="example.com",
            latency_ms=25.5,  # This should be overridden to None
            loss=True,
        )

        # __post_init__ should have enforced the invariant
        assert measurement.latency_ms is None, (
            "When loss=True, latency_ms must be None regardless of input"
        )
        assert measurement.loss is True

    def test_post_init_enforces_no_latency_implies_loss_true(self):
        """Test __post_init__ invariant: latency_ms=None forces loss=True.

        When latency_ms=None is specified, any provided loss value should be
        overridden to True to maintain data consistency.
        """
        ts = datetime.now()
        measurement = Measurement(
            ts=ts,
            host="example.com",
            latency_ms=None,
            loss=False,  # This should be overridden to True
        )

        # __post_init__ should have enforced the invariant
        assert measurement.latency_ms is None
        assert measurement.loss is True, (
            "When latency_ms=None, loss must be True regardless of input"
        )

    def test_measurement_types(self):
        """Test that measurement fields have correct types."""
        ts = datetime.now()
        measurement = Measurement(ts=ts, host="test.host", latency_ms=42.0, loss=False)

        assert isinstance(measurement.ts, datetime)
        assert isinstance(measurement.host, str)
        assert isinstance(measurement.latency_ms, float)
        assert isinstance(measurement.loss, bool)

    def test_measurement_zero_latency(self):
        """Test measurement with zero latency (edge case)."""
        ts = datetime.now()
        measurement = Measurement(ts=ts, host="fast.host", latency_ms=0.0, loss=False)

        assert measurement.latency_ms == 0.0
        assert measurement.loss is False
