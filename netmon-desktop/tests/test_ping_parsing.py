"""Unit tests for ping latency parsing (pure function tests).

Tests the parse_ping_latency_ms() pure function across various ping output
formats without requiring subprocess calls or OS-specific setup.
"""

from netmon.collector_ping import parse_ping_latency_ms


class TestParsePingLatencyLinuxMacOS:
    """Test parsing Linux and macOS ping output formats."""

    def test_linux_standard_format(self):
        """Test standard Linux ping output: time=12.3 ms"""
        output = "64 bytes from example.com: icmp_seq=1 ttl=64 time=12.3 ms"
        assert parse_ping_latency_ms(output) == 12.3

    def test_macos_standard_format(self):
        """Test standard macOS ping output."""
        output = "64 bytes from 172.217.14.206: icmp_seq=0 ttl=56 time=8.123 ms"
        assert parse_ping_latency_ms(output) == 8.123

    def test_linux_multiline_output(self):
        """Test parsing from multi-line Linux output."""
        output = """
PING google.com (142.250.185.46) 56(84) bytes of data.
64 bytes from lga25s78-in-f14.1e100.net (142.250.185.46): icmp_seq=1 ttl=117 time=12.3 ms

--- google.com ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
"""
        assert parse_ping_latency_ms(output) == 12.3

    def test_high_precision_decimal(self):
        """Test parsing high-precision decimal values."""
        output = "time=0.123 ms"
        assert parse_ping_latency_ms(output) == 0.123

    def test_low_latency(self):
        """Test parsing very low latency values."""
        output = "time=0.5 ms"
        assert parse_ping_latency_ms(output) == 0.5


class TestParsePingLatencyWindows:
    """Test parsing Windows ping output formats."""

    def test_windows_standard_format(self):
        """Test standard Windows ping output: time=12ms (no space)."""
        output = "Reply from 142.250.185.46: bytes=32 time=15ms TTL=117"
        assert parse_ping_latency_ms(output) == 15.0

    def test_windows_with_space_after_equals(self):
        """Test Windows format with space after equals: time= 12 ms"""
        output = "Reply from 192.168.1.1: bytes=32 time= 20 ms TTL=64"
        assert parse_ping_latency_ms(output) == 20.0

    def test_windows_with_space_before_equals(self):
        """Test format with space before equals: time = 12 ms (defensive parsing)."""
        output = "Reply from 192.168.1.1: bytes=32 time = 25 ms TTL=64"
        assert parse_ping_latency_ms(output) == 25.0

    def test_windows_less_than_1ms(self):
        """Test Windows time<1ms format (fast localhost response)."""
        output = "Reply from 127.0.0.1: bytes=32 time<1ms TTL=128"
        # Interpreted as midpoint: 1/2 = 0.5
        assert parse_ping_latency_ms(output) == 0.5

    def test_windows_less_than_10ms(self):
        """Test Windows time<10ms format."""
        output = "Reply from 192.168.1.1: bytes=32 time<10ms TTL=64"
        # Interpreted as midpoint: 10/2 = 5.0
        assert parse_ping_latency_ms(output) == 5.0

    def test_windows_multiline_output(self):
        """Test parsing from multi-line Windows output."""
        output = """
Pinging google.com [142.250.185.46] with 32 bytes of data:
Reply from 142.250.185.46: bytes=32 time=15ms TTL=117

Ping statistics for 142.250.185.46:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss),
"""
        assert parse_ping_latency_ms(output) == 15.0


class TestParsePingLatencyCaseInsensitive:
    """Test case-insensitive parsing."""

    def test_uppercase_time(self):
        """Test parsing with uppercase TIME."""
        output = "TIME=15.5 MS"
        assert parse_ping_latency_ms(output) == 15.5

    def test_mixed_case(self):
        """Test parsing with mixed case."""
        output = "Time=20.3 Ms"
        assert parse_ping_latency_ms(output) == 20.3

    def test_lowercase_time(self):
        """Test parsing with lowercase time."""
        output = "time=10.0 ms"
        assert parse_ping_latency_ms(output) == 10.0


class TestParsePingLatencyEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_string(self):
        """Test parsing empty string returns None."""
        assert parse_ping_latency_ms("") is None

    def test_none_input(self):
        """Test parsing None returns None."""
        assert parse_ping_latency_ms(None) is None

    def test_no_time_token(self):
        """Test output without 'time' keyword returns None."""
        output = "Request timed out."
        assert parse_ping_latency_ms(output) is None

    def test_garbage_output(self):
        """Test random garbage output returns None."""
        output = "asdfjkl;qwerty12345!@#$%"
        assert parse_ping_latency_ms(output) is None

    def test_destination_unreachable(self):
        """Test destination unreachable output returns None."""
        output = """
PING 192.168.1.254 (192.168.1.254) 56(84) bytes of data.
From 192.168.1.1 icmp_seq=1 Destination Host Unreachable

--- 192.168.1.254 ping statistics ---
1 packets transmitted, 0 received, +1 errors, 100% packet loss
"""
        assert parse_ping_latency_ms(output) is None

    def test_timeout_message(self):
        """Test timeout message returns None."""
        output = "Request timeout for icmp_seq 0"
        assert parse_ping_latency_ms(output) is None

    def test_whitespace_only(self):
        """Test whitespace-only input returns None."""
        assert parse_ping_latency_ms("   \\n\\t  ") is None

    def test_partial_match_no_ms(self):
        """Test partial match without 'ms' suffix returns None."""
        output = "time=12.3"  # Missing 'ms'
        assert parse_ping_latency_ms(output) is None

    def test_time_in_unrelated_context(self):
        """Test 'time' appearing in unrelated context."""
        output = "The time is 12:30 PM, time elapsed: 5 seconds"
        assert parse_ping_latency_ms(output) is None


class TestParsePingLatencyIntegerValues:
    """Test parsing integer latency values."""

    def test_integer_latency(self):
        """Test parsing integer latency values."""
        output = "time=100 ms"
        assert parse_ping_latency_ms(output) == 100.0

    def test_large_latency(self):
        """Test parsing large latency values (high latency network)."""
        output = "time=9999 ms"
        assert parse_ping_latency_ms(output) == 9999.0

    def test_zero_latency_edge_case(self):
        """Test parsing zero latency (unlikely but possible)."""
        output = "time=0 ms"
        assert parse_ping_latency_ms(output) == 0.0


class TestParsePingLatencyWhitespaceVariations:
    """Test parsing with various whitespace patterns."""

    def test_no_space_around_equals(self):
        """Test time=12ms (no spaces)."""
        output = "time=12ms"
        assert parse_ping_latency_ms(output) == 12.0

    def test_space_before_equals(self):
        """Test time =12 ms (space before equals) - now supported."""
        output = "time =12 ms"
        # After defensive parsing update, this now matches
        assert parse_ping_latency_ms(output) == 12.0

    def test_space_after_equals(self):
        """Test time= 12 ms (space after equals)."""
        output = "time= 12 ms"
        assert parse_ping_latency_ms(output) == 12.0

    def test_multiple_spaces(self):
        """Test time=  12  ms (multiple spaces)."""
        output = "time=  12  ms"
        assert parse_ping_latency_ms(output) == 12.0

    def test_tab_character(self):
        """Test whitespace with tab characters."""
        output = "time=\t12\tms"  # Actual tab characters
        assert parse_ping_latency_ms(output) == 12.0


class TestParsePingLatencyMultipleMatches:
    """Test behavior when multiple time values appear in output."""

    def test_first_match_wins(self):
        """Test that first match is returned when multiple exist."""
        output = "time=10 ms, time=20 ms, time=30 ms"
        # Should return the first match
        assert parse_ping_latency_ms(output) == 10.0

    def test_less_than_before_equals(self):
        """Test time<1ms appearing before time=5ms."""
        output = "time<1ms (fast), actual time=5ms"
        # Should match time<1ms first (parsed as 0.5)
        assert parse_ping_latency_ms(output) == 0.5


class TestParsePingLatencyRobustness:
    """Test function robustness against malformed input."""

    def test_special_characters_in_output(self):
        """Test output with special characters."""
        output = "!@#time=12.5 ms$%^&*()"
        assert parse_ping_latency_ms(output) == 12.5

    def test_unicode_characters(self):
        """Test output with unicode characters."""
        output = "时间time=10.5 ms延迟"
        assert parse_ping_latency_ms(output) == 10.5

    def test_malformed_number_format(self):
        """Test malformed number formats are rejected."""
        output = "time=12.3.4 ms"  # Invalid number (multiple decimals)
        # Defensive: reject malformed numbers rather than partial parse
        assert parse_ping_latency_ms(output) is None

    def test_negative_latency(self):
        """Test negative latency value (shouldn't match pattern)."""
        output = "time=-5 ms"
        # Regex doesn't match negative numbers (by design)
        assert parse_ping_latency_ms(output) is None

    def test_very_long_output(self):
        """Test function performance on very long output."""
        # Simulate verbose output with time value buried deep
        output = "x" * 10000 + "time=15.5 ms" + "y" * 10000
        assert parse_ping_latency_ms(output) == 15.5
