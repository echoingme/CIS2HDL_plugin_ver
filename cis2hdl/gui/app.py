"""CIS2HDL Application — PySide6 entry point."""

from __future__ import annotations

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from cis2hdl import __version__
from cis2hdl.core.config import config

from .colors import Colors, Fonts, FontSize
from .main_window import MainWindow


def run_gui() -> None:
    """Launch the CIS2HDL GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("CIS2HDL")
    app.setOrganizationName("CIS2HDL")

    # Set default font — extract primary family from Fonts.UI CSS string
    _ui_font_family = Fonts.UI.split(",")[0].strip().strip('"').strip("'")
    font = QFont(_ui_font_family, FontSize.SM)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()
    window.setWindowTitle(f"CIS2HDL v{__version__} — OrCAD CIS to HDL Schematic Converter")
    window.setMinimumSize(config.gui.window_min_width, config.gui.window_min_height)
    window.show()

    logging.info("CIS2HDL GUI started")
    sys.exit(app.exec())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_gui()
