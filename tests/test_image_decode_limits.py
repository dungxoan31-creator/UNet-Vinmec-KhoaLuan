"""Reject oversized decoded images before allocating full pixel arrays."""

import pydicom
from PIL import Image

from backend.services import image_service


def test_oversized_raster_is_rejected_before_opencv_decode(monkeypatch):
    class ImageHeader:
        size = (5001, 5000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(Image, "open", lambda _path: ImageHeader())
    monkeypatch.setattr(
        image_service,
        "cv2_imread_unicode",
        lambda *_args: (_ for _ in ()).throw(AssertionError("OpenCV decode must not run")),
    )

    assert image_service.decode_ultrasound_image("oversized.png") is None


def test_oversized_dicom_is_rejected_before_pixel_array_decode(monkeypatch):
    accessed = False

    class Dataset:
        Rows = 5000
        Columns = 5001
        SamplesPerPixel = 1
        Modality = "US"
        NumberOfFrames = 1

        def get(self, key, default=None):
            return getattr(self, key, default)

        @property
        def pixel_array(self):
            nonlocal accessed
            accessed = True
            return None

    monkeypatch.setattr(pydicom, "dcmread", lambda *_args, **_kwargs: Dataset())

    assert image_service.decode_ultrasound_image("oversized.dcm") is None
    assert accessed is False
