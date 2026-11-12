# NikonMicroscope

Small cross-platform tool to preview and capture images from a Nikon
microscope camera (target: **Nikon DS-Fi3**). Linux first, Windows later.

Status: the GUI, capture pipeline and a simulated camera work. The real
DS-Fi3 backend is not written yet — see [docs/HANDOFF.md](docs/HANDOFF.md).

## Run

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync                                   # create .venv and install everything
uv run nikon-microscope                   # GUI with the simulated camera
uv run nikon-microscope snap -o shot.tif  # one still, no GUI
uv run nikon-microscope cameras           # list camera backends
uv run pytest                             # tests (GUI tests run headless)
```
