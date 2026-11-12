"""Synthetic camera for developing and testing without hardware.

Renders a bright-field-like scene (stained "cells" on a light background) and
reacts to exposure and gain the way a real sensor would: brightness scales
with ``exposure * gain``, highlights clip, and the frame rate drops once the
exposure time exceeds the frame period. The scene drifts slowly so that the
live preview is visibly live.

The geometry mimics the DS-Fi3: 2880 x 2048 stills, 1440 x 1024 live frames.
"""

from __future__ import annotations

import math
import time

import numpy as np

from .base import Camera, CameraError, CameraInfo, Frame, Range

SENSOR_SIZE = (2880, 2048)
LIVE_SIZE = (1440, 1024)
MAX_LIVE_FPS = 30.0
#: Exposure at which the scene background sits just below saturation at gain 1.
REFERENCE_EXPOSURE_MS = 20.0


class SimulatedCamera(Camera):
    backend_name = "simulated"

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed
        self._open = False
        self._exposure_ms = 10.0
        self._gain = 1.0
        self._frame_index = 0
        self._last_frame_time = 0.0
        self._t0 = 0.0
        self._scene_full: np.ndarray | None = None
        self._scene_live: np.ndarray | None = None
        self._noise: np.ndarray | None = None
        self._rng = np.random.default_rng(seed)
        self._info = CameraInfo(
            model="Simulated DS-Fi3",
            serial="SIM-0001",
            sensor_size=SENSOR_SIZE,
            live_size=LIVE_SIZE,
            bit_depth=8,
            exposure_ms=Range(0.1, 30_000.0),
            gain=Range(1.0, 64.0),
        )

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> None:
        if self._open:
            return
        self._scene_full = _render_scene(SENSOR_SIZE, self._seed)
        self._scene_live = self._scene_full[::2, ::2].copy()
        # A small bank of noise tiles, reused with random offsets per frame.
        self._noise = self._rng.normal(0.0, 1.0, size=(256, 256, 3)).astype(np.float32)
        self._t0 = time.monotonic()
        self._last_frame_time = 0.0
        self._open = True

    def close(self) -> None:
        self._open = False
        self._scene_full = None
        self._scene_live = None
        self._noise = None

    @property
    def info(self) -> CameraInfo:
        return self._info

    # -- acquisition -------------------------------------------------------

    def read_live_frame(self, timeout_s: float = 2.0) -> Frame:
        self._require_open()
        period = max(1.0 / MAX_LIVE_FPS, self._exposure_ms / 1000.0)
        wait = self._last_frame_time + period - time.monotonic()
        if wait > timeout_s:
            time.sleep(timeout_s)
            raise CameraError("Timed out waiting for a live frame")
        if wait > 0:
            time.sleep(wait)
        self._last_frame_time = time.monotonic()
        return self._expose(self._scene_live, drift_scale=1)

    def snap(self) -> Frame:
        self._require_open()
        time.sleep(min(self._exposure_ms / 1000.0, 2.0))
        return self._expose(self._scene_full, drift_scale=2)

    # -- settings ----------------------------------------------------------

    def get_exposure_ms(self) -> float:
        return self._exposure_ms

    def set_exposure_ms(self, value: float) -> None:
        self._exposure_ms = self._info.exposure_ms.clamp(float(value))

    def get_gain(self) -> float:
        return self._gain

    def set_gain(self, value: float) -> None:
        self._gain = self._info.gain.clamp(float(value))

    # -- internals ---------------------------------------------------------

    def _require_open(self) -> None:
        if not self._open:
            raise CameraError("Camera is not open")

    def _expose(self, scene: np.ndarray, drift_scale: int) -> Frame:
        """Turn the radiance map ``scene`` (float32, 0..1) into an 8-bit frame."""
        t = time.monotonic() - self._t0
        # Slow circular stage drift, in live-frame pixels.
        dx = round(12 * math.sin(t * 0.35)) * drift_scale
        dy = round(8 * math.cos(t * 0.27)) * drift_scale
        img = np.roll(scene, (dy, dx), axis=(0, 1))

        signal = self._exposure_ms / REFERENCE_EXPOSURE_MS * self._gain
        img = img * np.float32(signal * 235.0)

        # Read noise grows with gain; tile the noise bank at a random offset.
        h, w = img.shape[:2]
        oy, ox = self._rng.integers(0, 256, size=2)
        noise = np.roll(self._noise, (int(oy), int(ox)), axis=(0, 1))
        reps = (-(-h // 256), -(-w // 256), 1)
        img += np.tile(noise, reps)[:h, :w] * np.float32(1.5 * np.sqrt(self._gain))

        data = np.clip(img, 0, 255).astype(np.uint8)
        self._frame_index += 1
        return Frame(
            data=data,
            bit_depth=8,
            exposure_ms=self._exposure_ms,
            gain=self._gain,
            index=self._frame_index,
        )


def _render_scene(size: tuple[int, int], seed: int) -> np.ndarray:
    """Render a float32 ``(h, w, 3)`` transmission map of H&E-like cells."""
    width, height = size
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    # Uneven illumination: brightest in the centre, like a real condenser.
    r2 = ((xx - width / 2) / width) ** 2 + ((yy - height / 2) / height) ** 2
    scene = np.repeat((1.0 - 0.35 * r2)[:, :, None], 3, axis=2).astype(np.float32)

    cytoplasm = np.array([0.10, 0.45, 0.25], dtype=np.float32)  # absorbs green -> pink
    nucleus = np.array([0.75, 0.80, 0.30], dtype=np.float32)  # absorbs red/green -> purple

    for _ in range(140):
        cx, cy = rng.uniform(0, width), rng.uniform(0, height)
        radius = rng.uniform(40, 110)
        x0, x1 = int(max(cx - radius, 0)), int(min(cx + radius + 1, width))
        y0, y1 = int(max(cy - radius, 0)), int(min(cy + radius + 1, height))
        if x0 >= x1 or y0 >= y1:
            continue
        sub_x, sub_y = xx[y0:y1, x0:x1] - cx, yy[y0:y1, x0:x1] - cy
        angle = rng.uniform(0, np.pi)
        stretch = rng.uniform(0.6, 1.0)
        u = sub_x * np.cos(angle) + sub_y * np.sin(angle)
        v = (-sub_x * np.sin(angle) + sub_y * np.cos(angle)) / stretch
        dist = np.sqrt(u * u + v * v) / radius
        body = np.clip((1.0 - dist) * 6.0, 0.0, 1.0)[:, :, None]
        core = np.clip((0.35 - dist) * 12.0, 0.0, 1.0)[:, :, None]
        patch = scene[y0:y1, x0:x1]
        patch *= 1.0 - body * cytoplasm * rng.uniform(0.5, 1.0)
        patch *= 1.0 - core * nucleus

    return scene
