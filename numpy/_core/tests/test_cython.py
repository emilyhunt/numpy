from datetime import datetime
import os
import shutil
import subprocess
import sys
import time
import pytest

import numpy as np
from numpy.testing import IS_WASM

# This import is copied from random.tests.test_extending
try:
    import cython
    from Cython.Compiler.Version import version as cython_version
except ImportError:
    cython = None
else:
    from numpy._utils import _pep440

    # Cython 0.29.30 is required for Python 3.11 and there are
    # other fixes in the 0.29 series that are needed even for earlier
    # Python versions.
    # Note: keep in sync with the one in pyproject.toml
    required_version = "0.29.30"
    if _pep440.parse(cython_version) < _pep440.Version(required_version):
        # too old or wrong cython, skip the test
        cython = None

pytestmark = pytest.mark.skipif(cython is None, reason="requires cython")


@pytest.fixture
def install_temp(tmp_path):
    # Based in part on test_cython from random.tests.test_extending
    if IS_WASM:
        pytest.skip("No subprocess")

    srcdir = os.path.join(os.path.dirname(__file__), 'examples', 'cython')
    build_dir = tmp_path / "build"
    os.makedirs(build_dir, exist_ok=True)
    try:
        subprocess.check_call(["meson", "--version"])
    except FileNotFoundError:
        pytest.skip("No usable 'meson' found")
    if sys.platform == "win32":
        subprocess.check_call(["meson", "setup",
                               "--buildtype=release",
                               "--vsenv", str(srcdir)],
                              cwd=build_dir,
                              )
    else:
        subprocess.check_call(["meson", "setup", str(srcdir)],
                              cwd=build_dir
                              )
    subprocess.check_call(["meson", "compile", "-vv"], cwd=build_dir)

    sys.path.append(str(build_dir))

def test_is_timedelta64_object(install_temp):
    import checks

    assert checks.is_td64(np.timedelta64(1234))
    assert checks.is_td64(np.timedelta64(1234, "ns"))
    assert checks.is_td64(np.timedelta64("NaT", "ns"))

    assert not checks.is_td64(1)
    assert not checks.is_td64(None)
    assert not checks.is_td64("foo")
    assert not checks.is_td64(np.datetime64("now", "s"))


def test_is_datetime64_object(install_temp):
    import checks

    assert checks.is_dt64(np.datetime64(1234, "ns"))
    assert checks.is_dt64(np.datetime64("NaT", "ns"))

    assert not checks.is_dt64(1)
    assert not checks.is_dt64(None)
    assert not checks.is_dt64("foo")
    assert not checks.is_dt64(np.timedelta64(1234))


def test_get_datetime64_value(install_temp):
    import checks

    dt64 = np.datetime64("2016-01-01", "ns")

    result = checks.get_dt64_value(dt64)
    expected = dt64.view("i8")

    assert result == expected


def test_get_timedelta64_value(install_temp):
    import checks

    td64 = np.timedelta64(12345, "h")

    result = checks.get_td64_value(td64)
    expected = td64.view("i8")

    assert result == expected


def test_get_datetime64_unit(install_temp):
    import checks

    dt64 = np.datetime64("2016-01-01", "ns")
    result = checks.get_dt64_unit(dt64)
    expected = 10
    assert result == expected

    td64 = np.timedelta64(12345, "h")
    result = checks.get_dt64_unit(td64)
    expected = 5
    assert result == expected


def test_abstract_scalars(install_temp):
    import checks

    assert checks.is_integer(1)
    assert checks.is_integer(np.int8(1))
    assert checks.is_integer(np.uint64(1))

def test_default_int(install_temp):
    import checks

    assert checks.get_default_integer() is np.dtype(int)

def test_convert_datetime64_to_datetimestruct(install_temp):
    # GH#21199
    import checks

    res = checks.convert_datetime64_to_datetimestruct()

    exp = {
        "year": 2022,
        "month": 3,
        "day": 15,
        "hour": 20,
        "min": 1,
        "sec": 55,
        "us": 260292,
        "ps": 0,
        "as": 0,
    }

    assert res == exp


class TestDatetimeStrings:
    def test_make_iso_8601_datetime(self, install_temp):
        # GH#21199
        import checks
        dt = datetime(2016, 6, 2, 10, 45, 19)
        # uses NPY_FR_s
        result = checks.make_iso_8601_datetime(dt)
        assert result == b"2016-06-02T10:45:19"

    def test_get_datetime_iso_8601_strlen(self, install_temp):
        # GH#21199
        import checks
        # uses NPY_FR_ns
        res = checks.get_datetime_iso_8601_strlen()
        assert res == 48


@pytest.mark.parametrize(
    "arrays",
    [
        [np.random.rand(2)],
        [np.random.rand(2), np.random.rand(3, 1)],
        [np.random.rand(2), np.random.rand(2, 3, 2), np.random.rand(1, 3, 2)],
        [np.random.rand(2, 1)] * 4 + [np.random.rand(1, 1, 1)],
    ]
)
def test_multiiter_fields(install_temp, arrays):
    import checks
    bcast = np.broadcast(*arrays)

    assert bcast.ndim == checks.get_multiiter_number_of_dims(bcast)
    assert bcast.size == checks.get_multiiter_size(bcast)
    assert bcast.numiter == checks.get_multiiter_num_of_iterators(bcast)
    assert bcast.shape == checks.get_multiiter_shape(bcast)
    assert bcast.index == checks.get_multiiter_current_index(bcast)
    assert all(
        [
            x.base is y.base
            for x, y in zip(bcast.iters, checks.get_multiiter_iters(bcast))
        ]
    )


def test_conv_intp(install_temp):
    import checks

    class myint:
        def __int__(self):
            return 3

    # These conversion passes via `__int__`, not `__index__`:
    assert checks.conv_intp(3.) == 3
    assert checks.conv_intp(myint()) == 3
