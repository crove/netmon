"""Logging configuration for NetMon application."""

import logging
import os
import sys


def configure_logging() -> None:
    """Configure application-wide logging.

    Respects NETMON_LOG_LEVEL environment variable (default: INFO).
    Logs to stderr with timestamp, level, module name, and message.

    Environment Variables:
        NETMON_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                         Default is INFO.

    Examples:
        # Default INFO level
        $ python -m netmon

        # Debug level for troubleshooting
        $ NETMON_LOG_LEVEL=DEBUG python -m netmon

        # Quiet mode
        $ NETMON_LOG_LEVEL=WARNING python -m netmon
    """
    # Get log level from environment, default to INFO
    log_level_str = os.environ.get("NETMON_LOG_LEVEL", "INFO").upper()

    # Map string to logging constant
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    log_level = log_level_map.get(log_level_str, logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=True,  # Override any existing configuration
    )

    # Log the configuration for visibility
    logger = logging.getLogger(__name__)
    logger.info("Logging configured: level=%s", logging.getLevelName(log_level))
