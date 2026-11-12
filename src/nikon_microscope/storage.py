"""Writing captured frames to disk. Deliberately free of any Qt dependency."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from . import __version__
from .camera import Frame

#: File extension -> human-readable name, in the order shown in the GUI.
FORMATS: dict[str, str] = {
    ".tif": "TIFF (lossless, keeps full bit depth)",
    ".png": "PNG (lossless, 8-bit)",
    ".jpg": "JPEG (lossy, 8-bit)",
}


def frame_metadata(frame: Frame, camera_model: str = "") -> dict:
    """Acquisition settings that get embedded in saved files."""
    return {
        "software": f"nikon-microscope {__version__}",
        "camera": camera_model,
        "acquired": datetime.fromtimestamp(frame.timestamp).isoformat(timespec="milliseconds"),
        "exposure_ms": frame.exposure_ms,
        "gain": frame.gain,
        "bit_depth": frame.bit_depth,
    }


def next_free_path(directory: Path, prefix: str, extension: str, when: datetime | None = None) -> Path:
    """Return ``directory/prefix_YYYYmmdd_HHMMSS.ext``, never an existing file."""
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    stem = f"{prefix}_{stamp}" if prefix else stamp
    candidate = directory / f"{stem}{extension}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{extension}"
        counter += 1
    return candidate


def save_frame(frame: Frame, path: Path, camera_model: str = "") -> Path:
    """Write ``frame`` to ``path``; the format is chosen by the file extension.

    Refuses to overwrite an existing file. Returns the path written.
    """
    path = Path(path)
    extension = path.suffix.lower()
    if extension == ".tiff":
        extension = ".tif"
    elif extension == ".jpeg":
        extension = ".jpg"
    if extension not in FORMATS:
        raise ValueError(f"Unsupported image format {path.suffix!r} (use one of {', '.join(FORMATS)})")
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata = frame_metadata(frame, camera_model)
    if extension == ".tif":
        tifffile.imwrite(
            path,
            np.ascontiguousarray(frame.data),
            photometric="rgb" if frame.is_color else "minisblack",
            description=json.dumps(metadata),
            software=metadata["software"],
            metadata=None,
        )
    else:
        image = Image.fromarray(frame.to_rgb8() if frame.is_color else frame.to_rgb8()[:, :, 0])
        if extension == ".png":
            info = PngInfo()
            for key, value in metadata.items():
                info.add_text(key, str(value))
            image.save(path, pnginfo=info)
        else:
            image.save(path, quality=95)
    return path
