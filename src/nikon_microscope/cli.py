"""Command-line entry point.

``nikon-microscope``                 start the GUI
``nikon-microscope snap -o out.tif`` capture one still without a GUI
``nikon-microscope cameras``         list the available camera backends
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .camera import BACKENDS, DEFAULT_BACKEND, CameraError, create_camera


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nikon-microscope", description="Preview and capture images from a Nikon microscope camera."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--camera", default=DEFAULT_BACKEND, choices=sorted(BACKENDS), help="camera backend (default: %(default)s)"
    )
    commands = parser.add_subparsers(dest="command")

    commands.add_parser("gui", help="start the graphical interface (default)")
    commands.add_parser("cameras", help="list available camera backends")

    snap = commands.add_parser("snap", help="capture one full-resolution image and exit")
    snap.add_argument("-o", "--output", type=Path, required=True, help="output file (.tif, .png or .jpg)")
    snap.add_argument("--exposure-ms", type=float, help="exposure time in milliseconds")
    snap.add_argument("--gain", type=float, help="analogue gain factor")
    return parser


def _snap(args: argparse.Namespace) -> int:
    from .storage import save_frame

    with create_camera(args.camera) as camera:
        if args.exposure_ms is not None:
            camera.set_exposure_ms(args.exposure_ms)
        if args.gain is not None:
            camera.set_gain(args.gain)
        frame = camera.snap()
        path = save_frame(frame, args.output, camera.info.model)
    print(f"Saved {path} ({frame.width} x {frame.height}, {frame.exposure_ms:g} ms, gain {frame.gain:g})")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "cameras":
            for name in sorted(BACKENDS):
                print(name + ("  (default)" if name == DEFAULT_BACKEND else ""))
            return 0
        if args.command == "snap":
            return _snap(args)
        from .gui import run

        return run(create_camera(args.camera))
    except (CameraError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
