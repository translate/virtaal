#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import shutil

import pytest

from virtaal.common import pan_app

TESTENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "devsupport", "screenshots", "testenv.py")


@pytest.fixture
def testenv():
    spec = importlib.util.spec_from_file_location("testenv", TESTENV)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated(testenv, monkeypatch, tmp_path):
    real = tmp_path / "real"
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.setenv(name, str(real))
    testenv.isolate_home()
    fake = os.environ["HOME"]
    yield real, fake
    shutil.rmtree(fake, ignore_errors=True)


@pytest.mark.parametrize("is_windows, is_mac", [(True, False), (False, True), (False, False)])
def test_isolate_home_moves_the_config_dir_off_the_real_one(isolated, monkeypatch, is_windows, is_mac):
    # Windows reads %APPDATA%, not $HOME (#4917).
    real, fake = isolated
    monkeypatch.setattr(pan_app.platform, "is_windows", is_windows)
    monkeypatch.setattr(pan_app.platform, "is_mac", is_mac)
    monkeypatch.setattr(pan_app.platform, "is_flatpak", False)
    # expanduser() reads USERPROFILE, not HOME, when the suite runs on Windows.
    monkeypatch.setenv("USERPROFILE", fake)
    confdir = pan_app.get_config_dir()
    assert os.path.commonpath([confdir, fake]) == fake
    assert not real.exists()


def test_isolate_home_moves_local_appdata(isolated):
    _real, fake = isolated
    assert os.path.commonpath([os.environ["LOCALAPPDATA"], fake]) == fake
