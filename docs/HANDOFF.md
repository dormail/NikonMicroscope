# Handoff: where the project stands and what to do next

Last updated 2026-11-12, written on a machine **without** the microscope.

## State

Working, tested against a simulated camera only:

- GUI (`uv run nikon-microscope`): live preview, exposure and gain controls,
  Snap (button or Space) saving a full-resolution still as TIFF / PNG / JPEG
  with exposure, gain and timestamp embedded in the file.
- Headless capture: `uv run nikon-microscope snap -o shot.tif --exposure-ms 12`.
- 17 tests, including a headless end-to-end GUI test (`uv run pytest`).

Not done:

- **No real DS-Fi3 backend.** The camera has never been connected. Public
  research says there is no native Linux driver; see
  [HARDWARE.md](HARDWARE.md) for the evidence and the options.
- Stage movement (planned, nothing written). The stage / microscope model is
  not known yet.
- Windows has not been tried. Nothing in the code is Linux-specific except
  `tools/probe_camera.sh`.

## Setup on a new machine

```sh
git clone git@github.com:dormail/NikonMicroscope.git && cd NikonMicroscope
# install uv if missing: https://docs.astral.sh/uv/getting-started/installation/
uv sync
uv run pytest                 # should pass without any hardware
uv run nikon-microscope       # GUI with the simulated camera
```

If the GUI fails to start on Ubuntu with an "xcb" platform plugin error:
`sudo apt install libxcb-cursor0`.

## Next steps, in order

1. **Probe the camera.** Plug the DS-Fi3 into a USB 3 port, power it on, run
   `sudo tools/probe_camera.sh`, and read the result as described in
   [HARDWARE.md → First plug-in](HARDWARE.md#first-plug-in). Record the
   findings in HARDWARE.md.
2. **Choose the backend route** (table in HARDWARE.md). This is an open
   decision that depends on the probe result and on whether a Windows
   machine or VM next to the microscope is acceptable:
   - vendor-specific USB device, Windows acceptable → `DSCam.dll` backend,
     optionally behind a small frame server for the Linux GUI;
   - vendor-specific, Linux only → reverse-engineer the USB protocol;
   - standard class (unlikely) → V4L2 / Aravis / gphoto2 backend.

   Requesting the Nikon SDK account takes days, so start that early if the
   SDK route is on the table.
3. **Write the backend** as a new module in `src/nikon_microscope/camera/`
   implementing `Camera` from `camera/base.py`, and register it in
   `camera/__init__.py`. It then appears as `--camera <name>` in both the GUI
   and the CLI. Test it headless first with `nikon-microscope snap`.
4. **Then** stage movement, and Windows packaging.

## Code map

```
src/nikon_microscope/
  camera/base.py        Camera interface, Frame, CameraInfo, CameraError
  camera/simulated.py   Synthetic DS-Fi3 (2880x2048 stills, 1440x1024 live)
  camera/__init__.py    BACKENDS registry, create_camera()
  storage.py            save_frame(), file naming, embedded metadata (no Qt)
  cli.py                argument parsing: gui / snap / cameras
  gui/acquisition.py    QThread that owns the camera; all device I/O is here
  gui/main_window.py    Window, controls, capture flow
  gui/preview.py        Aspect-fit image widget
tools/probe_camera.sh   Collects USB facts on first plug-in (read-only)
docs/HARDWARE.md        Everything known about the DS-Fi3 and backend options
```

Design points worth knowing before changing things:

- **One thread owns the camera.** The GUI never calls the camera directly; it
  calls `AcquisitionThread.request_*()` and listens to signals. Backends
  therefore do not need to be thread-safe, and a slow device cannot freeze
  the window.
- **Live frames go through a one-slot mailbox**, not through the signal, so
  a slow GUI drops stale frames instead of queueing them.
- **`Frame.data`** is `(h, w, 3)` RGB or `(h, w)` mono, `uint8` or `uint16`,
  with `bit_depth` giving the meaningful range. TIFF keeps the full depth;
  PNG and JPEG are reduced to 8 bit.
- **Gain is a linear factor** (1× – 64× in the simulator, matching the
  camera's ISO 50 – 3200 span). The GUI's gain and exposure sliders are
  logarithmic and need a minimum above zero; map SDK units to a factor in
  the backend.
- Saved files are never overwritten; a counter is appended on a name clash.

## Ideas not started

Histogram / clipping indicator, auto exposure, white balance, 1:1 zoom and
pan in the preview, scale bar from objective calibration, time-lapse, stage
control and tiling.
