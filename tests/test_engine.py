import numpy as np

from app.iris_engine import IrisEngine, match
from tools.synth_iris import capture

E = IrisEngine()


def test_same_eye_matches_despite_rotation():
    a = E.extract(capture(1, 0, rotation_deg=0))
    b = E.extract(capture(1, 1, rotation_deg=9))
    hd, shift = match(a, b)
    assert hd < 0.34
    assert shift != 0  # la rotation a bien été compensée


def test_different_eyes_do_not_match():
    a, b = E.extract(capture(2, 0)), E.extract(capture(3, 0))
    assert match(a, b)[0] > 0.40


def test_template_shape_and_quality():
    t = E.extract(capture(4, 0))
    assert t.code.shape == (20, 240, 2) and t.code.dtype == bool
    assert t.usable_ratio > 0.8


def test_blank_image_rejected():
    import pytest
    from app.iris_engine import SegmentationError
    with pytest.raises(SegmentationError):
        E.extract(np.full((280, 320), 128, np.uint8))
