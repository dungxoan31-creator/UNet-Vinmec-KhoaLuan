"""
Unicode-safe OpenCV image utility functions and encoders.
"""

import os

import cv2
import numpy as np


def cv2_imread_unicode(file_path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
    """
    Unicode-safe image reader for Windows paths with Vietnamese characters.
    """
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


def cv2_imwrite_unicode(file_path: str, img_np: np.ndarray) -> bool:
    """
    Unicode-safe image writer for Windows paths with Vietnamese characters.
    """
    ext = os.path.splitext(file_path)[1]
    ret, buf = cv2.imencode(ext, img_np)
    if ret:
        with open(file_path, "wb") as f:
            f.write(buf)
        return True
    return False
