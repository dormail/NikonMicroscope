"""End-to-end GUI test against the simulated camera, run headless."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import tifffile
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

from nikon_microscope.camera import Camera, CameraError, SimulatedCamera
from nikon_microscope.gui.main_window import MainWindow


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    QCoreApplication.setOrganizationName("NikonMicroscopeTest")
    QCoreApplication.setApplicationName("nikon-microscope-test")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    return QApplication.instance() or QApplication([])


def _wait_until(qapp, condition, timeout_s=10.0):
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        qapp.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


def test_live_preview_and_snap(app, tmp_path):
    window = MainWindow(SimulatedCamera())
    window.show()
    try:
        _wait_until(app, lambda: window._preview._image is not None)
        assert window._live_button.isChecked()
        assert window._preview._image.width() == 1440

        window._dir_edit.setText(str(tmp_path / "shots"))
        window._prefix_edit.setText("cell")
        window._exposure.spin.setValue(4.0)
        window._snap_button.click()
        _wait_until(app, lambda: any((tmp_path / "shots").glob("cell_*.tif")))

        (saved,) = (tmp_path / "shots").glob("cell_*.tif")
        with tifffile.TiffFile(saved) as tif:
            assert tif.asarray().shape == (2048, 2880, 3)
            assert '"exposure_ms": 4.0' in tif.pages[0].description
        assert str(saved) in window._last_saved_label.text()
    finally:
        window.close()
    assert not window._thread.isRunning()


def test_slider_and_spin_box_stay_in_sync(app):
    window = MainWindow(SimulatedCamera())
    try:
        _wait_until(app, lambda: window._snap_button.isEnabled())
        control = window._exposure
        control.slider.setValue(control.slider.maximum())
        assert control.spin.value() == pytest.approx(30_000.0)
        control.spin.setValue(0.1)
        assert control.slider.value() == 0
    finally:
        window.close()


class BrokenCamera(SimulatedCamera):
    def open(self) -> None:
        raise CameraError("no device found")


def test_camera_open_failure_is_reported(app):
    camera: Camera = BrokenCamera()
    window = MainWindow(camera)
    try:
        _wait_until(app, lambda: "no device found" in window.statusBar().currentMessage())
        assert not window._snap_button.isEnabled()
    finally:
        window.close()
