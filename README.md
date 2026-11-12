# NikonMicroscope

Small cross-platform tool to preview and capture images from a Nikon
microscope camera (target: **Nikon DS-Fi3**). Linux first, Windows later.

**Status:** the GUI, capture pipeline and a simulated camera work. There is
no backend for the real DS-Fi3 yet: the camera has no known native Linux
driver, and which route to take is still open. See
[docs/HANDOFF.md](docs/HANDOFF.md) for the state and next steps and
[docs/HARDWARE.md](docs/HARDWARE.md) for what is known about the camera.

## Run

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                   # create .venv and install everything
uv run nikon-microscope                   # GUI with the simulated camera
uv run nikon-microscope snap -o shot.tif  # one still, no GUI
uv run nikon-microscope cameras           # list camera backends
uv run pytest                             # tests (GUI tests run headless)
```

## With the camera connected

```sh
sudo tools/probe_camera.sh   # read-only; writes probe-output/<timestamp>/
```

Then follow "First plug-in" in [docs/HARDWARE.md](docs/HARDWARE.md).
