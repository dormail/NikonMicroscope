"""Background thread that owns the camera while the GUI is running.

All camera I/O happens on this thread so the GUI never blocks on the device.
The GUI talks to it through the thread-safe ``request_*`` methods and listens
to its signals.

Live frames are handed over through a one-slot mailbox instead of being
carried by the signal: if the GUI is slower than the camera, stale frames are
dropped rather than queued up.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ..camera import Camera, CameraError, Frame


class AcquisitionThread(QThread):
    #: The camera was opened; carries its ``CameraInfo``.
    opened = Signal(object)
    #: A live frame is waiting in the mailbox; fetch it with :meth:`take_frame`.
    frame_ready = Signal()
    #: A full-resolution still was captured; carries the ``Frame``.
    still_captured = Signal(object)
    #: Live view was stopped by the thread itself (after an error).
    live_stopped = Signal()
    #: Something went wrong; carries a message for the user.
    error = Signal(str)

    def __init__(self, camera: Camera, parent=None) -> None:
        super().__init__(parent)
        self._camera = camera
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._quit = False
        self._live = False
        self._snap_requested = False
        self._pending_exposure: float | None = None
        self._pending_gain: float | None = None
        self._mailbox: Frame | None = None

    # -- called from the GUI thread ------------------------------------------

    def request_live(self, enabled: bool) -> None:
        with self._lock:
            self._live = enabled
        self._wake.set()

    def request_snap(self) -> None:
        with self._lock:
            self._snap_requested = True
        self._wake.set()

    def request_exposure_ms(self, value: float) -> None:
        with self._lock:
            self._pending_exposure = value
        self._wake.set()

    def request_gain(self, value: float) -> None:
        with self._lock:
            self._pending_gain = value
        self._wake.set()

    def take_frame(self) -> Frame | None:
        """Return the newest live frame, or None if it was already taken."""
        with self._lock:
            frame, self._mailbox = self._mailbox, None
        return frame

    def shutdown(self) -> None:
        """Stop the thread and wait until the camera has been closed."""
        with self._lock:
            self._quit = True
        self._wake.set()
        self.wait()

    # -- acquisition thread ----------------------------------------------------

    def run(self) -> None:
        try:
            self._camera.open()
        except CameraError as exc:
            self.error.emit(f"Could not open camera: {exc}")
            return
        try:
            self.opened.emit(self._camera.info)
            self._loop()
        finally:
            self._camera.close()

    def _loop(self) -> None:
        while True:
            # Clear before reading the requests: anything that arrives after
            # this point sets the event again and is picked up next iteration.
            self._wake.clear()
            with self._lock:
                if self._quit:
                    return
                live = self._live
                snap, self._snap_requested = self._snap_requested, False
                exposure, self._pending_exposure = self._pending_exposure, None
                gain, self._pending_gain = self._pending_gain, None

            try:
                if exposure is not None:
                    self._camera.set_exposure_ms(exposure)
                if gain is not None:
                    self._camera.set_gain(gain)
                if snap:
                    self.still_captured.emit(self._camera.snap())
                if live:
                    self._deliver(self._camera.read_live_frame())
            except CameraError as exc:
                with self._lock:
                    self._live = False
                self.error.emit(str(exc))
                if live:
                    self.live_stopped.emit()
                continue

            if not live:
                # Idle: sleep until the GUI asks for something.
                self._wake.wait()

    def _deliver(self, frame: Frame) -> None:
        with self._lock:
            was_empty = self._mailbox is None
            self._mailbox = frame
        if was_empty:
            self.frame_ready.emit()
