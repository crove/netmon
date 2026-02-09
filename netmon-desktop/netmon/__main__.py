"""Entry point for NetMon application."""

import sys
from PySide6.QtWidgets import QApplication
from netmon.collector import FakeCollectorAdapter
from netmon.ui.main_window import MainWindow


def main():
    """Main entry point for the NetMon application."""
    app = QApplication(sys.argv)

    # Create collector and main window
    collector = FakeCollectorAdapter()
    window = MainWindow(collector=collector)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
