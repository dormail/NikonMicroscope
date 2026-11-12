"""Backend-independent camera interface.

Every camera backend (simulator, real DS-Fi3 driver, ...) implements
:class:`Camera`. The GUI and the CLI only ever talk to this interface, so
adding hardware support means adding one module under ``camera/`` and
registering it in ``camera/__init__.py``.

Threading contract: a camera instance is driven by a single thread at a time
(the acquisition thread while the GUI is running). Backends do not need to be
thread-safe.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Self

import numpy as np


class CameraError(RuntimeError):
    """Raised for any camera failure the user should be told about."""


@dataclass(frozen=True)
class Range:
    """Inclusive limits of a numeric camera setting."""

    minimum: float
    maximum: float

    def clamp(self, value: float) -> float:
        return min(max(value, self.minimum), self.maximum)


@dataclass(frozen=True)
class CameraInfo:
    """Static description of an opened camera."""

    model: str
    serial: str
    #: (width, height) of a full-resolution still.
    sensor_size: tuple[int, int]
    #: (width, height) of live-preview frames.
    live_size: tuple[int, int]
    #: Bits per channel of the data in :attr:`Frame.data`.
    bit_depth: int
    exposure_ms: Range
    gain: Range


@dataclass
class Frame:
    """One image from the camera.

    ``data`` is ``(height, width, 3)`` RGB or ``(height, width)`` mono, dtype
    ``uint8`` or ``uint16``. For ``uint16`` the meaningful range is
    ``0 .. 2**bit_depth - 1``.
    """

    data: np.ndarray
    bit_depth: int = 8
    exposure_ms: float = 0.0
    gain: float = 1.0
    timestamp: float = field(default_factory=time.time)
    #: Running frame number since the camera was opened.
    index: int = 0

    @property
    def width(self) -> int:
        return self.data.shape[1]

    @property
    def height(self) -> int:
        return self.data.shape[0]

    @property
    def is_color(self) -> bool:
        return self.data.ndim == 3

    def to_rgb8(self) -> np.ndarray:
        """Return a C-contiguous ``(h, w, 3) uint8`` copy-or-view for display."""
        data = self.data
        if data.dtype != np.uint8:
            shift = max(self.bit_depth - 8, 0)
            data = (data >> shift).astype(np.uint8)
        if data.ndim == 2:
            data = np.repeat(data[:, :, None], 3, axis=2)
        return np.ascontiguousarray(data)


class Camera(ABC):
    """Abstract camera. Use as a context manager or call open()/close()."""

    #: Short identifier used on the command line and in the GUI.
    backend_name: str = ""

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @abstractmethod
    def open(self) -> None:
        """Connect to the camera. Raises :class:`CameraError` on failure."""

    @abstractmethod
    def close(self) -> None:
        """Release the camera. Must be safe to call more than once."""

    @property
    @abstractmethod
    def info(self) -> CameraInfo:
        """Static camera description. Only valid while the camera is open."""

    @abstractmethod
    def read_live_frame(self, timeout_s: float = 2.0) -> Frame:
        """Block until the next live-preview frame is available and return it."""

    @abstractmethod
    def snap(self) -> Frame:
        """Capture and return one full-resolution still with current settings."""

    @abstractmethod
    def get_exposure_ms(self) -> float: ...

    @abstractmethod
    def set_exposure_ms(self, value: float) -> None: ...

    @abstractmethod
    def get_gain(self) -> float: ...

    @abstractmethod
    def set_gain(self, value: float) -> None: ...
