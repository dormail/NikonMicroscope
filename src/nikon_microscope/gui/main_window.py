"""Main application window: live preview on the left, controls on the right."""

from __future__ import annotations

import math
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..camera import Camera, CameraInfo, Frame, Range
from ..storage import FORMATS, next_free_path, save_frame
from .acquisition import AcquisitionThread
from .preview import PreviewWidget

SLIDER_STEPS = 1000


class LogSliderSpin(QWidget):
    """A spin box plus a logarithmic slider editing the same value."""

    def __init__(self, suffix: str, decimals: int, on_change, parent=None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        self._range = Range(1.0, 10.0)
        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setSuffix(suffix)
        self.spin.setKeyboardTracking(False)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.spin)
        layout.addWidget(self.slider)
        self.spin.valueChanged.connect(self._spin_changed)
        self.slider.valueChanged.connect(self._slider_changed)

    def configure(self, limits: Range, value: float) -> None:
        self._range = limits
        self.spin.blockSignals(True)
        self.spin.setRange(limits.minimum, limits.maximum)
        self.spin.setValue(value)
        self.spin.blockSignals(False)
        self._sync_slider(value)

    def value(self) -> float:
        return self.spin.value()

    def _span(self) -> float:
        return math.log(self._range.maximum / self._range.minimum)

    def _sync_slider(self, value: float) -> None:
        position = math.log(value / self._range.minimum) / self._span() * SLIDER_STEPS
        self.slider.blockSignals(True)
        self.slider.setValue(round(position))
        self.slider.blockSignals(False)

    def _spin_changed(self, value: float) -> None:
        self._sync_slider(value)
        self._on_change(value)

    def _slider_changed(self, position: int) -> None:
        value = self._range.minimum * math.exp(position / SLIDER_STEPS * self._span())
        self.spin.blockSignals(True)
        self.spin.setValue(value)
        self.spin.blockSignals(False)
        self._on_change(self.spin.value())


class MainWindow(QMainWindow):
    def __init__(self, camera: Camera) -> None:
        super().__init__()
        self.setWindowTitle("Nikon Microscope")
        self._settings = QSettings()
        self._info: CameraInfo | None = None
        self._frame_times: deque[float] = deque(maxlen=30)

        self._preview = PreviewWidget()
        self._build_controls()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self._preview, stretch=1)
        layout.addWidget(self._controls)
        self.setCentralWidget(central)

        self._fps_label = QLabel()
        self.statusBar().addPermanentWidget(self._fps_label)
        self._set_controls_enabled(False)
        self.statusBar().showMessage("Opening camera…")

        self._thread = AcquisitionThread(camera, self)
        self._thread.opened.connect(self._on_opened)
        self._thread.frame_ready.connect(self._on_frame_ready)
        self._thread.still_captured.connect(self._on_still)
        self._thread.live_stopped.connect(lambda: self._live_button.setChecked(False))
        self._thread.error.connect(self._on_error)
        self._thread.start()

    # -- construction ------------------------------------------------------

    def _build_controls(self) -> None:
        self._controls = QWidget()
        self._controls.setFixedWidth(300)
        column = QVBoxLayout(self._controls)
        column.setContentsMargins(0, 0, 0, 0)

        camera_box = QGroupBox("Camera")
        camera_form = QFormLayout(camera_box)
        self._model_label = QLabel("–")
        self._model_label.setWordWrap(True)
        self._live_button = QPushButton("Live")
        self._live_button.setCheckable(True)
        self._live_button.toggled.connect(self._on_live_toggled)
        self._exposure = LogSliderSpin(" ms", 2, lambda v: self._thread.request_exposure_ms(v))
        self._gain = LogSliderSpin("×", 2, lambda v: self._thread.request_gain(v))
        camera_form.addRow(self._model_label)
        camera_form.addRow(self._live_button)
        camera_form.addRow("Exposure", self._exposure)
        camera_form.addRow("Gain", self._gain)
        column.addWidget(camera_box)

        capture_box = QGroupBox("Capture")
        capture_form = QFormLayout(capture_box)
        pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        default_dir = str(Path(pictures or Path.home()) / "NikonMicroscope")
        self._dir_edit = QLineEdit(self._settings.value("capture/directory", default_dir))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._dir_edit)
        dir_row.addWidget(browse)
        self._prefix_edit = QLineEdit(self._settings.value("capture/prefix", "image"))
        self._format_combo = QComboBox()
        for extension, description in FORMATS.items():
            self._format_combo.addItem(description, extension)
        saved_format = self._format_combo.findData(self._settings.value("capture/format", ".tif"))
        self._format_combo.setCurrentIndex(max(saved_format, 0))
        self._snap_button = QPushButton("Snap  (Space)")
        self._snap_button.setMinimumHeight(40)
        self._snap_button.clicked.connect(self._snap)
        capture_form.addRow("Folder", dir_row)
        capture_form.addRow("Prefix", self._prefix_edit)
        capture_form.addRow("Format", self._format_combo)
        capture_form.addRow(self._snap_button)
        column.addWidget(capture_box)

        self._last_saved_label = QLabel()
        self._last_saved_label.setWordWrap(True)
        self._last_saved_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        column.addWidget(self._last_saved_label)
        column.addStretch(1)

        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        shortcut.activated.connect(self._snap_button.click)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self._live_button, self._exposure, self._gain, self._snap_button):
            widget.setEnabled(enabled)

    # -- camera events -----------------------------------------------------

    def _on_opened(self, info: CameraInfo) -> None:
        self._info = info
        width, height = info.sensor_size
        self._model_label.setText(f"{info.model}\nS/N {info.serial} · {width} × {height}")
        self._exposure.configure(info.exposure_ms, info.exposure_ms.clamp(10.0))
        self._gain.configure(info.gain, info.gain.minimum)
        self._thread.request_exposure_ms(self._exposure.value())
        self._thread.request_gain(self._gain.value())
        self._set_controls_enabled(True)
        self.statusBar().showMessage("Camera ready", 3000)
        self._snap_button.setFocus()
        self._live_button.setChecked(True)

    def _on_live_toggled(self, enabled: bool) -> None:
        self._live_button.setText("Stop live" if enabled else "Live")
        self._frame_times.clear()
        if not enabled:
            self._fps_label.clear()
        self._thread.request_live(enabled)

    def _on_frame_ready(self) -> None:
        frame = self._thread.take_frame()
        if frame is None or not self._live_button.isChecked():
            return
        self._preview.set_rgb8(frame.to_rgb8())
        self._frame_times.append(time.monotonic())
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            fps = (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0
            self._fps_label.setText(f"{frame.width} × {frame.height}   {fps:.1f} fps")

    def _on_error(self, message: str) -> None:
        self._snap_button.setEnabled(self._info is not None)
        self.statusBar().showMessage(message)

    # -- capture -----------------------------------------------------------

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose capture folder", self._dir_edit.text())
        if chosen:
            self._dir_edit.setText(chosen)

    def _snap(self) -> None:
        self._snap_button.setEnabled(False)
        self.statusBar().showMessage("Capturing…")
        self._thread.request_snap()

    def _on_still(self, frame: Frame) -> None:
        self._snap_button.setEnabled(True)
        directory = Path(self._dir_edit.text()).expanduser()
        extension = self._format_combo.currentData()
        try:
            path = next_free_path(directory, self._prefix_edit.text().strip(), extension)
            save_frame(frame, path, self._info.model if self._info else "")
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Could not save image: {exc}")
            return
        self._last_saved_label.setText(f"Last saved:\n{path}")
        self.statusBar().showMessage(f"Saved {path.name} ({frame.width} × {frame.height})", 5000)
        if not self._live_button.isChecked():
            self._preview.set_rgb8(frame.to_rgb8())

    # -- shutdown ----------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._settings.setValue("capture/directory", self._dir_edit.text())
        self._settings.setValue("capture/prefix", self._prefix_edit.text())
        self._settings.setValue("capture/format", self._format_combo.currentData())
        self._thread.shutdown()
        super().closeEvent(event)
