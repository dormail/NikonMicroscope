import json
from datetime import datetime

import numpy as np
import pytest
import tifffile
from PIL import Image

from nikon_microscope.camera import Frame
from nikon_microscope.storage import next_free_path, save_frame


def _frame(dtype=np.uint8, bit_depth=8):
    rng = np.random.default_rng(1)
    top = 2**bit_depth
    data = rng.integers(0, top, size=(48, 64, 3)).astype(dtype)
    return Frame(data=data, bit_depth=bit_depth, exposure_ms=12.5, gain=2.0)


def test_tiff_roundtrip_is_lossless_and_carries_metadata(tmp_path):
    frame = _frame()
    path = save_frame(frame, tmp_path / "a.tif", camera_model="Test Cam")
    with tifffile.TiffFile(path) as tif:
        np.testing.assert_array_equal(tif.asarray(), frame.data)
        metadata = json.loads(tif.pages[0].description)
    assert metadata["exposure_ms"] == 12.5
    assert metadata["gain"] == 2.0
    assert metadata["camera"] == "Test Cam"


def test_tiff_keeps_16_bit_data(tmp_path):
    frame = _frame(np.uint16, bit_depth=12)
    path = save_frame(frame, tmp_path / "deep.tiff")
    loaded = tifffile.imread(path)
    assert loaded.dtype == np.uint16
    np.testing.assert_array_equal(loaded, frame.data)


def test_png_is_lossless_8_bit(tmp_path):
    frame = _frame()
    path = save_frame(frame, tmp_path / "a.png")
    with Image.open(path) as image:
        np.testing.assert_array_equal(np.asarray(image), frame.data)
        assert image.text["exposure_ms"] == "12.5"


def test_16_bit_frame_is_reduced_to_8_bit_for_png(tmp_path):
    frame = _frame(np.uint16, bit_depth=12)
    path = save_frame(frame, tmp_path / "a.png")
    with Image.open(path) as image:
        np.testing.assert_array_equal(np.asarray(image), (frame.data >> 4).astype(np.uint8))


def test_jpeg_is_written(tmp_path):
    path = save_frame(_frame(), tmp_path / "a.jpg")
    with Image.open(path) as image:
        assert image.size == (64, 48)


def test_never_overwrites(tmp_path):
    save_frame(_frame(), tmp_path / "a.tif")
    with pytest.raises(FileExistsError):
        save_frame(_frame(), tmp_path / "a.tif")


def test_unknown_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported image format"):
        save_frame(_frame(), tmp_path / "a.bmp")


def test_next_free_path_skips_existing_files(tmp_path):
    when = datetime(2026, 1, 2, 3, 4, 5)
    first = next_free_path(tmp_path, "img", ".tif", when)
    assert first.name == "img_20260102_030405.tif"
    first.touch()
    second = next_free_path(tmp_path, "img", ".tif", when)
    assert second.name == "img_20260102_030405_1.tif"
    assert next_free_path(tmp_path, "", ".png", when).name == "20260102_030405.png"
