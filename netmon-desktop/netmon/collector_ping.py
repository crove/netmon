"""Real ICMP ping collector for NetMon using system ping command."""

import logging
import platform
import re
import subprocess
from datetime import datetime
from math import ceil

from netmon.models import Measurement

logger = logging.getLogger(__name__)


def parse_ping_latency_ms(output: str) -> float | None:
    """Parse latency value from ping command output (pure function).

    Handles various ping output formats across platforms:
    - Linux/macOS: "time=12.3 ms"
    - Windows: "time=12ms" or "time<1ms"

    Windows "time<Nms" is interpreted as N/2 ms (midpoint estimate).
    For example, "time<1ms" => 0.5ms, "time<10ms" => 5.0ms.

    This is a pure function with no side effects, making it easily testable
    without requiring subprocess calls or OS-specific setup.

    Args:
        output: Raw ping command output (stdout or combined stdout+stderr)

    Returns:
        Latency in milliseconds (float), or None if parsing failed

    Examples:
        >>> parse_ping_latency_ms("time=12.3 ms")
        12.3
        >>> parse_ping_latency_ms("time<1ms")
        0.5
        >>> parse_ping_latency_ms("Request timed out.")
        None
    """
    if not output:
        return None

    # Compile patterns (could be cached at module level for performance)
    # Pattern 1: "time<Nms" (Windows fast response)
    less_than_pattern = re.compile(r"time<(\d+)", re.IGNORECASE)
    match = less_than_pattern.search(output)
    if match:
        # Interpret "time<N" as midpoint: N/2
        threshold = float(match.group(1))
        return threshold / 2.0

    # Pattern 2: "time=12.3 ms" or "time = 12 ms" (standard format)
    # Matches: "time [space] = [space] <number> ms"
    # Supports optional space before '=' for defensive parsing
    latency_pattern = re.compile(r"time\s*[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
    match = latency_pattern.search(output)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, IndexError):
            return None

    return None


class PingCollector:
    """Collector that uses OS ping command to measure network latency.

    Cross-platform implementation supporting Windows, Linux, and macOS.
    Uses subprocess to execute system ping with configurable timeout.

    **Localization Limitation:**
    Parsing relies on the English keyword "time" in ping output. On non-English
    Windows systems (e.g., German "Zeit", French "temps"), parsing will fail and
    samples will be reported as packet loss. This is intentional defensive behavior.

    **Workarounds for non-English systems:**
    1. Set system locale to English for ping command (via LANG environment)
    2. Use FakeCollector for testing/development
    3. Future enhancement: Add multi-language regex patterns
    """

    def __init__(self, timeout_ms: int = 1000):
        """Initialize ping collector with timeout.

        Args:
            timeout_ms: Maximum time to wait for ping response in milliseconds.
                       Default is 1000ms (1 second).
        """
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")

        self.timeout_ms = timeout_ms
        self.timeout_seconds = timeout_ms / 1000.0
        self.system = platform.system()

        logger.debug(
            "PingCollector initialized: timeout_ms=%d, system=%s",
            timeout_ms,
            self.system,
        )

    def generate_sample(self, host: str) -> Measurement:
        """Generate a single ping measurement for the given host.

        Executes system ping command and parses the output to extract latency.
        Returns loss=True if ping fails, times out, or output cannot be parsed.

        Args:
            host: Target hostname or IP address to ping

        Returns:
            Measurement object with timestamp, host, latency, and loss status
        """
        if not host or not host.strip():
            return Measurement(ts=datetime.now(), host=host, latency_ms=None, loss=True)

        timestamp = datetime.now()

        try:
            # Build platform-specific ping command
            cmd = self._build_ping_command(host)

            logger.debug("Executing ping: host=%s, timeout=%ds", host, self.timeout_seconds)

            # Execute ping with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds + 0.5,  # Add buffer to subprocess timeout
                shell=False,  # Security: never use shell=True
            )

            logger.debug("Ping completed: host=%s, returncode=%d", host, result.returncode)

            # Non-zero return code indicates ping failure
            if result.returncode != 0:
                logger.debug(
                    "Ping failed (non-zero returncode): host=%s, returncode=%d",
                    host,
                    result.returncode,
                )
                return Measurement(ts=timestamp, host=host, latency_ms=None, loss=True)

            # Parse latency from output
            latency = self._parse_latency(result.stdout)

            if latency is not None:
                logger.debug("Parsed latency: host=%s, latency=%.2fms", host, latency)
                return Measurement(ts=timestamp, host=host, latency_ms=latency, loss=False)
            else:
                # Parse failure - treat as loss
                logger.debug(
                    "Parse failed: host=%s, output_preview=%s",
                    host,
                    result.stdout[:100] if result.stdout else "(empty)",
                )
                return Measurement(ts=timestamp, host=host, latency_ms=None, loss=True)

        except subprocess.TimeoutExpired:
            # Ping timed out
            logger.debug("Ping timeout: host=%s, timeout=%ds", host, self.timeout_seconds)
            return Measurement(ts=timestamp, host=host, latency_ms=None, loss=True)
        except Exception as e:
            # Any other error (e.g., ping command not found) - treat as loss
            logger.warning("Ping error: host=%s, error=%s", host, str(e), exc_info=True)
            return Measurement(ts=timestamp, host=host, latency_ms=None, loss=True)

    def _build_ping_command(self, host: str) -> list[str]:
        """Build platform-specific ping command.

        Args:
            host: Target host to ping

        Returns:
            List of command arguments for subprocess
        """
        if self.system == "Windows":
            # Windows: ping -n count -w timeout_ms host
            return ["ping", "-n", "1", "-w", str(self.timeout_ms), host]

        elif self.system == "Linux":
            # Linux: ping -c count -W timeout_seconds host
            timeout_secs = max(1, ceil(self.timeout_seconds))
            return ["ping", "-c", "1", "-W", str(timeout_secs), host]

        else:
            # macOS/BSD: ping -c count host
            # Note: macOS -W has different semantics, so we rely on subprocess timeout
            return ["ping", "-c", "1", host]

    def _parse_latency(self, output: str) -> float | None:
        """Parse latency from ping command output.

        Delegates to pure function parse_ping_latency_ms() for testability.

        Args:
            output: Raw ping command output

        Returns:
            Latency in milliseconds, or None if parsing failed
        """
        return parse_ping_latency_ms(output)
