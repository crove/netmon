"""Tests for netmon.collector.FakeCollectorAdapter behavior."""

from datetime import datetime
import pytest
from netmon.collector import FakeCollectorAdapter
from netmon.fake_collector import FakeCollector
from netmon.models import Measurement


class TestFakeCollectorAdapter:
    """Test FakeCollectorAdapter behavior and contracts."""

    def test_adapter_default_constructor(self):
        """Test adapter creates with default FakeCollector."""
        adapter = FakeCollectorAdapter()

        # Should be able to generate samples
        sample = adapter.generate_sample("test.host")

        assert isinstance(sample, Measurement)
        assert sample.host == "test.host"
        assert isinstance(sample.ts, datetime)

    def test_adapter_with_injected_collector(self):
        """Test adapter works with injected FakeCollector."""
        fake_collector = FakeCollector(seed=123)
        adapter = FakeCollectorAdapter(fake_collector)

        sample = adapter.generate_sample("injected.host")

        assert isinstance(sample, Measurement)
        assert sample.host == "injected.host"
        assert isinstance(sample.ts, datetime)

    def test_adapter_deterministic_with_seed(self):
        """Test adapter produces deterministic results with seeded collector."""
        # Create two adapters with same seed
        adapter1 = FakeCollectorAdapter(FakeCollector(seed=42))
        adapter2 = FakeCollectorAdapter(FakeCollector(seed=42))

        # Generate samples
        sample1 = adapter1.generate_sample("deterministic.test")
        sample2 = adapter2.generate_sample("deterministic.test")

        # Should have same latency and loss values
        assert sample1.latency_ms == sample2.latency_ms
        assert sample1.loss == sample2.loss
        assert sample1.host == sample2.host

    def test_adapter_enforces_measurement_loss_latency_invariants(self):
        """Test adapter always returns Measurements that satisfy loss ↔ latency invariants.

        Validates that:
        - If loss=True, then latency_ms=None
        - If loss=False, then latency_ms is a positive float
        This ensures the adapter respects the Measurement contract.
        """
        adapter = FakeCollectorAdapter(FakeCollector(seed=100))

        # Generate several samples to test invariants across different scenarios
        for i in range(10):
            sample = adapter.generate_sample(f"invariant-test-{i}")

            # Validate basic structure
            assert isinstance(sample, Measurement), "Should return Measurement instance"
            assert isinstance(sample.ts, datetime), "Timestamp should be datetime"
            assert isinstance(sample.host, str), "Host should be string"
            assert isinstance(sample.loss, bool), "Loss should be boolean"

            # Validate core business invariant: loss ↔ latency relationship
            if sample.loss:
                assert sample.latency_ms is None, (
                    f"Lost sample must have latency_ms=None, got {sample.latency_ms}"
                )
            else:
                assert sample.latency_ms is not None, "Successful sample must have latency_ms"
                assert isinstance(sample.latency_ms, float), "Latency must be float"
                assert sample.latency_ms > 0, f"Latency must be positive, got {sample.latency_ms}"

    def test_adapter_preserves_exact_host_strings(self):
        """Test adapter preserves host strings exactly as provided.

        This validates that various host formats (domains, IPs, complex names)
        are preserved without modification through the collection process.
        """
        adapter = FakeCollectorAdapter(FakeCollector(seed=200))

        test_hosts = [
            "google.com",  # Simple domain
            "192.168.1.1",  # IPv4 address
            "long-hostname-with-dashes.example.org",  # Complex domain
            "short.co",  # Short domain
        ]

        for expected_host in test_hosts:
            sample = adapter.generate_sample(expected_host)
            assert sample.host == expected_host, (
                f"Host should be preserved exactly: expected '{expected_host}', got '{sample.host}'"
            )

    def test_adapter_generates_recent_timestamps(self):
        """Test adapter generates timestamps close to current time (within 1 second).

        This validates that timestamps are fresh without brittle exact time assertions.
        """
        adapter = FakeCollectorAdapter()

        sample = adapter.generate_sample("timestamp.test")
        now = datetime.now()

        # Timestamp should be recent (within last second) to avoid brittle time assertions
        time_diff = abs((now - sample.ts).total_seconds())
        assert time_diff < 1.0, f"Timestamp too old: {time_diff}s difference"

    def test_adapter_error_propagation(self):
        """Test adapter propagates collector errors."""
        adapter = FakeCollectorAdapter(FakeCollector())

        # Test invalid host (should raise ValueError from FakeCollector)
        with pytest.raises(ValueError, match="Host cannot be empty"):
            adapter.generate_sample("")

        with pytest.raises(ValueError, match="Host cannot be empty"):
            adapter.generate_sample("   ")
