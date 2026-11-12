"""Camera backends and the registry used to look them up by name."""

from __future__ import annotations

from collections.abc import Callable

from .base import Camera, CameraError, CameraInfo, Frame, Range
from .simulated import SimulatedCamera

#: Backend name -> factory. Register real hardware backends here.
BACKENDS: dict[str, Callable[[], Camera]] = {
    SimulatedCamera.backend_name: SimulatedCamera,
}

DEFAULT_BACKEND = SimulatedCamera.backend_name


def create_camera(backend: str = DEFAULT_BACKEND) -> Camera:
    """Instantiate (but do not open) the camera backend called ``backend``."""
    try:
        factory = BACKENDS[backend]
    except KeyError:
        known = ", ".join(sorted(BACKENDS))
        raise CameraError(f"Unknown camera backend {backend!r} (available: {known})") from None
    return factory()


__all__ = [
    "BACKENDS",
    "DEFAULT_BACKEND",
    "Camera",
    "CameraError",
    "CameraInfo",
    "Frame",
    "Range",
    "SimulatedCamera",
    "create_camera",
]
