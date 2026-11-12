# NikonMicroscope

Preview/capture GUI for a Nikon DS-Fi3 microscope camera. Python, PySide6, uv.

Read `docs/HANDOFF.md` first (current state, next steps, code map), and
`docs/HARDWARE.md` before touching anything camera-specific — it separates
what is verified from what is only inferred from public sources.

## Commands

```sh
uv sync
uv run pytest                              # GUI tests run headless (offscreen)
uv run ruff check . && uv run ruff format .
uv run nikon-microscope                    # GUI, simulated camera
uv run nikon-microscope snap -o out.tif    # headless still
sudo tools/probe_camera.sh                 # read-only USB probe of the real camera
```

## Conventions

- New camera hardware = one module in `src/nikon_microscope/camera/`
  implementing `Camera` (`camera/base.py`), registered in `camera/__init__.py`.
  The GUI must keep working with `--camera simulated` on a machine without
  hardware.
- All device I/O happens on `gui/acquisition.py`'s thread; the GUI thread
  never calls a camera method directly.
- `storage.py` and `camera/` must not import Qt.
- Nikon's SDK (DLLs, headers) is proprietary: never commit it.
  `probe-output/` and USB captures are git-ignored (serial numbers).
- Keep `docs/HANDOFF.md` and `docs/HARDWARE.md` current when the state or the
  hardware knowledge changes; commit and push regularly.
