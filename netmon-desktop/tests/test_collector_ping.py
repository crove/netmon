"""Unit tests for PingCollector."""

import pytest
from datetime import datetime
from netmon.collector_ping import PingCollector
from netmon.models import Measurement


class TestPingCollectorParsing:
    """Test ping output parsing across different platforms and formats."""

    def test_parse_latency_linux_standard(self):
        """Test parsing standard Linux ping output."""
        collector = PingCollector()
        output = """
PING google.com (142.250.185.46) 56(84) bytes of data.
64 bytes from lga25s78-in-f14.1e100.net (142.250.185.46): icmp_seq=1 ttl=117 time=12.3 ms

--- google.com ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 12.345/12.345/12.345/0.000 ms
"""
        latency = collector._parse_latency(output)
        assert latency == 12.3

    def test_parse_latency_macos_standard(self):
        """Test parsing standard macOS ping output."""
        collector = PingCollector()
        output = """
PING google.com (172.217.14.206): 56 data bytes
64 bytes from 172.217.14.206: icmp_seq=0 ttl=56 time=8.123 ms

--- google.com ping statistics ---
1 packets transmitted, 1 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 8.123/8.123/8.123/0.000 ms
"""
        latency = collector._parse_latency(output)
        assert latency == 8.123

    def test_parse_latency_windows_standard(self):
        """Test parsing standard Windows ping output."""
        collector = PingCollector()
        output = """
Pinging google.com [142.250.185.46] with 32 bytes of data:
Reply from 142.250.185.46: bytes=32 time=15ms TTL=117

Ping statistics for 142.250.185.46:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 15ms, Maximum = 15ms, Average = 15ms
"""
        latency = collector._parse_latency(output)
        assert latency == 15.0

    def test_parse_latency_windows_less_than_1ms(self):
        """Test parsing Windows 'time<1ms' output."""
        collector = PingCollector()
        output = """
Pinging 127.0.0.1 with 32 bytes of data:
Reply from 127.0.0.1: bytes=32 time<1ms TTL=128

Ping statistics for 127.0.0.1:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
"""
        latency = collector._parse_latency(output)
        # "time<1ms" interpreted as 0.5ms
        assert latency == 0.5

    def test_parse_latency_windows_less_than_10ms(self):
        """Test parsing Windows 'time<10ms' output."""
        collector = PingCollector()
        output = "Reply from 192.168.1.1: bytes=32 time<10ms TTL=64"
        latency = collector._parse_latency(output)
        # "time<10ms" interpreted as 5.0ms
        assert latency == 5.0

    def test_parse_latency_with_spaces(self):
        """Test parsing output with varying whitespace."""
        collector = PingCollector()
        output = "64 bytes from example.com: time = 25.7 ms"
        latency = collector._parse_latency(output)
        assert latency == 25.7

    def test_parse_latency_decimal_precision(self):
        """Test parsing latency with high decimal precision."""
        collector = PingCollector()
        output = "time=0.123 ms"
        latency = collector._parse_latency(output)
        assert latency == 0.123

    def test_parse_latency_integer(self):
        """Test parsing integer latency values."""
        collector = PingCollector()
        output = "time=100 ms"
        latency = collector._parse_latency(output)
        assert latency == 100.0

    def test_parse_latency_case_insensitive(self):
        """Test parsing with different case variations."""
        collector = PingCollector()

        # Uppercase
        output1 = "TIME=15.5 MS"
        assert collector._parse_latency(output1) == 15.5

        # Mixed case
        output2 = "Time=20.3 Ms"
        assert collector._parse_latency(output2) == 20.3

    def test_parse_latency_empty_output(self):
        """Test parsing empty output returns None."""
        collector = PingCollector()
        assert collector._parse_latency("") is None
        assert collector._parse_latency(None) is None

    def test_parse_latency_no_match(self):
        """Test parsing output with no latency information."""
        collector = PingCollector()
        output = "Request timed out."
        assert collector._parse_latency(output) is None

    def test_parse_latency_malformed_output(self):
        """Test parsing malformed ping output."""
        collector = PingCollector()
        output = "Some random text without time information"
        assert collector._parse_latency(output) is None

    def test_parse_latency_unreachable(self):
        """Test parsing destination unreachable output."""
        collector = PingCollector()
        output = """
PING 192.168.1.254 (192.168.1.254) 56(84) bytes of data.
From 192.168.1.1 icmp_seq=1 Destination Host Unreachable

--- 192.168.1.254 ping statistics ---
1 packets transmitted, 0 received, +1 errors, 100% packet loss, time 0ms
"""
        assert collector._parse_latency(output) is None


class TestPingCollectorBuildCommand:
    """Test platform-specific command building."""

    def test_build_command_windows(self):
        """Test Windows ping command construction."""
        collector = PingCollector(timeout_ms=1000)
        collector.system = "Windows"

        cmd = collector._build_ping_command("google.com")
        assert cmd == ["ping", "-n", "1", "-w", "1000", "google.com"]

    def test_build_command_linux(self):
        """Test Linux ping command construction."""
        collector = PingCollector(timeout_ms=1000)
        collector.system = "Linux"

        cmd = collector._build_ping_command("google.com")
        assert cmd == ["ping", "-c", "1", "-W", "1", "google.com"]

    def test_build_command_linux_fractional_timeout(self):
        """Test Linux command with fractional timeout (rounds up)."""
        collector = PingCollector(timeout_ms=1500)
        collector.system = "Linux"

        cmd = collector._build_ping_command("google.com")
        assert cmd == ["ping", "-c", "1", "-W", "2", "google.com"]

    def test_build_command_macos(self):
        """Test macOS ping command construction."""
        collector = PingCollector(timeout_ms=1000)
        collector.system = "Darwin"

        cmd = collector._build_ping_command("google.com")
        assert cmd == ["ping", "-c", "1", "google.com"]

    def test_build_command_custom_timeout(self):
        """Test command with custom timeout."""
        collector = PingCollector(timeout_ms=2500)
        collector.system = "Windows"

        cmd = collector._build_ping_command("8.8.8.8")
        assert cmd == ["ping", "-n", "1", "-w", "2500", "8.8.8.8"]


class TestPingCollectorInitialization:
    """Test PingCollector initialization and configuration."""

    def test_init_default_timeout(self):
        """Test initialization with default timeout."""
        collector = PingCollector()
        assert collector.timeout_ms == 1000
        assert collector.timeout_seconds == 1.0

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        collector = PingCollector(timeout_ms=2000)
        assert collector.timeout_ms == 2000
        assert collector.timeout_seconds == 2.0

    def test_init_invalid_timeout_zero(self):
        """Test initialization fails with zero timeout."""
        with pytest.raises(ValueError, match="timeout_ms must be positive"):
            PingCollector(timeout_ms=0)

    def test_init_invalid_timeout_negative(self):
        """Test initialization fails with negative timeout."""
        with pytest.raises(ValueError, match="timeout_ms must be positive"):
            PingCollector(timeout_ms=-100)


class TestPingCollectorGenerateSample:
    """Test end-to-end sample generation."""

    def test_generate_sample_empty_host(self):
        """Test that empty host returns loss."""
        collector = PingCollector()

        measurement = collector.generate_sample("")
        assert measurement.loss is True
        assert measurement.latency_ms is None
        assert measurement.host == ""
        assert isinstance(measurement.ts, datetime)

    def test_generate_sample_whitespace_host(self):
        """Test that whitespace-only host returns loss."""
        collector = PingCollector()

        measurement = collector.generate_sample("   ")
        assert measurement.loss is True
        assert measurement.latency_ms is None

    def test_generate_sample_returns_measurement(self):
        """Test that generate_sample returns Measurement object."""
        collector = PingCollector()

        # Use localhost for reliable test (should work even offline)
        measurement = collector.generate_sample("127.0.0.1")

        assert isinstance(measurement, Measurement)
        assert measurement.host == "127.0.0.1"
        assert isinstance(measurement.ts, datetime)
        assert isinstance(measurement.loss, bool)

        # localhost should succeed
        if not measurement.loss:
            assert measurement.latency_ms is not None
            assert measurement.latency_ms >= 0

    def test_generate_sample_unreachable_host(self):
        """Test that unreachable host returns loss."""
        collector = PingCollector(timeout_ms=500)

        # Use invalid IP that should timeout quickly
        measurement = collector.generate_sample("192.0.2.1")  # TEST-NET-1 (reserved)

        assert isinstance(measurement, Measurement)
        assert measurement.host == "192.0.2.1"
        # Should be loss (either timeout or unreachable)
        assert measurement.loss is True
        assert measurement.latency_ms is None


class TestPingCollectorLocalizationRobustness:
    """Test robustness against locale/language variations.

    Windows ping output may differ by system language. These tests
    verify that parsing relies on the 'time' keyword which is more
    universal than other text. Non-English output is treated as loss.
    """

    def test_parse_german_windows_output(self):
        """Test parsing German Windows ping output."""
        collector = PingCollector()
        # German Windows: "Zeit" instead of "time" - should fail gracefully
        output = "Antwort von 8.8.8.8: Bytes=32 Zeit=15ms TTL=117"
        # Will fail to parse but should return None, not crash
        latency = collector._parse_latency(output)
        # Note: This will fail since we look for "time" keyword
        # This is intentional - we treat unparseable output as loss
        # If needed in future, can add multi-language support
        assert latency is None  # Non-English output returns None (treated as loss)

    def test_parse_french_windows_output(self):
        """Test parsing French Windows ping output."""
        collector = PingCollector()
        # French Windows: "temps" instead of "time"
        output = "Réponse de 8.8.8.8 : octets=32 temps=20ms TTL=117"
        latency = collector._parse_latency(output)
        assert latency is None  # Returns None, treated as loss

    def test_parse_spanish_windows_output(self):
        """Test parsing Spanish Windows ping output."""
        collector = PingCollector()
        # Spanish Windows: "tiempo" instead of "time"
        output = "Respuesta desde 8.8.8.8: bytes=32 tiempo=25ms TTL=117"
        latency = collector._parse_latency(output)
        assert latency is None  # Returns None, treated as loss

    def test_parse_time_keyword_required(self):
        """Test that 'time' keyword is required for successful parsing."""
        collector = PingCollector()
        # Without "time" keyword, should return None
        output = "latency=15ms duration=20ms"
        assert collector._parse_latency(output) is None

    def test_english_variations_still_work(self):
        """Test that English variations with 'time' keyword work."""
        collector = PingCollector()

        # Case variations
        assert collector._parse_latency("TIME=10ms") == 10.0
        assert collector._parse_latency("Time=11ms") == 11.0
        assert collector._parse_latency("time=12ms") == 12.0

        # Different spacing
        assert collector._parse_latency("time = 13 ms") == 13.0
        assert collector._parse_latency("time=14 ms") == 14.0
