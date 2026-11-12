"""Qt user interface."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..camera import Camera
from .main_window import MainWindow


def run(camera: Camera) -> int:
    """Show the main window for ``camera`` and run the Qt event loop."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("NikonMicroscope")
    app.setApplicationName("nikon-microscope")
    window = MainWindow(camera)
    window.show()
    return app.exec()


__all__ = ["MainWindow", "run"]
