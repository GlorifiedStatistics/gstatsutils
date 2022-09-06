import numpy as np
from gstats_utils import get_np_abs


def test_get_np_abs():
    a = np.array([1, 2, 3, 4, -5])
    assert np.all(get_np_abs(a) >= 0)
