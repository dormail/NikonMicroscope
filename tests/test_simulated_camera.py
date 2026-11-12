import numpy as np
import pytest

from nikon_microscope.camera import CameraError, SimulatedCamera, create_camera


@pytest.fixture
def camera():
    with SimulatedCamera() as cam:
        yield cam


def test_registry_creates_simulated_backend():
    assert isinstance(create_camera("simulated"), SimulatedCamera)
    with pytest.raises(CameraError, match="Unknown camera backend"):
        create_camera("does-not-exist")


def test_frame_geometry(camera):
    live = camera.read_live_frame()
    still = camera.snap()
    assert (live.width, live.height) == camera.info.live_size == (1440, 1024)
    assert (still.width, still.height) == camera.info.sensor_size == (2880, 2048)
    assert still.data.dtype == np.uint8 and still.is_color
    assert still.index == live.index + 1


def test_longer_exposure_and_gain_brighten_the_image(camera):
    camera.set_exposure_ms(2.0)
    dark = camera.read_live_frame().data.mean()
    camera.set_exposure_ms(8.0)
    brighter = camera.read_live_frame().data.mean()
    camera.set_gain(2.0)
    brightest = camera.read_live_frame().data.mean()
    assert dark < brighter < brightest


def test_overexposure_saturates(camera):
    camera.set_exposure_ms(500.0)
    frame = camera.snap()
    assert frame.data.max() == 255
    assert (frame.data == 255).mean() > 0.5


def test_settings_are_clamped_and_recorded_in_frames(camera):
    camera.set_exposure_ms(1e9)
    assert camera.get_exposure_ms() == camera.info.exposure_ms.maximum
    camera.set_exposure_ms(5.0)
    camera.set_gain(0.0)
    assert camera.get_gain() == camera.info.gain.minimum
    frame = camera.read_live_frame()
    assert (frame.exposure_ms, frame.gain) == (5.0, 1.0)


def test_closed_camera_refuses_to_acquire():
    camera = SimulatedCamera()
    with pytest.raises(CameraError):
        camera.snap()
