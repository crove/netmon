"""Entry point for NetMon application."""

import logging
import os
import sys
from PySide6.QtWidgets import QApplication
from netmon.collector import FakeCollectorAdapter
from netmon.logging_config import configure_logging
from netmon.ui.main_window import MainWindow

# Configure logging early
configure_logging()
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the NetMon application."""
    app = QApplication(sys.argv)

    # Collector selection with fallback
    collector = None
    user_message = None
    debug_info = None

    # Check for environment variable override
    force_fake = os.environ.get("NETMON_COLLECTOR", "").lower() == "fake"

    if not force_fake:
        # Try to use PingCollector as default - separate import from instantiation
        PingCollector = None

        # Step 1: Try importing the module
        try:
            from netmon.collector_ping import PingCollector

            logger.info("PingCollector module imported successfully")
        except ImportError as e:
            debug_info = f"Import failed: {e}"
            logger.warning("PingCollector unavailable: %s", e)
            user_message = "Using simulated data (real network monitoring unavailable)"

        # Step 2: Try instantiating if import succeeded
        if PingCollector is not None:
            try:
                collector = PingCollector(timeout_ms=1000)
                logger.info("PingCollector initialized successfully")
            except ValueError as e:
                # Invalid configuration parameter
                debug_info = f"Configuration error: {e}"
                logger.error("PingCollector configuration invalid: %s", e)
                user_message = "Using simulated data (configuration error)"
            except PermissionError as e:
                # Insufficient privileges (rare on modern systems)
                debug_info = f"Permission error: {e}"
                logger.warning("Insufficient permissions for ping: %s", e)
                user_message = "Using simulated data (permission denied)"
            except OSError as e:
                # ping command not found or not accessible
                debug_info = f"System error: {e}"
                logger.warning("Ping command unavailable: %s", e)
                user_message = "Using simulated data (ping command not available)"

    # Fall back to FakeCollectorAdapter if needed
    if collector is None:
        collector = FakeCollectorAdapter()
        logger.info("Using FakeCollectorAdapter")

        if not user_message and force_fake:
            user_message = "Using simulated data (NETMON_COLLECTOR=fake)"
            logger.info("Fake collector explicitly requested via environment variable")

    # Create main window
    window = MainWindow(collector=collector)

    # Show user-friendly message in status label if fallback occurred
    if user_message:
        window.status_label.setText(f"Status: {user_message}")
        window.status_label.setStyleSheet("font-weight: bold; color: orange;")

        # Set tooltip with debug info if available
        if debug_info:
            tooltip = f"Fallback to simulated data\n\nTechnical details: {debug_info}"
            window.status_label.setToolTip(tooltip)
            logger.debug("Debug info: %s", debug_info)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
