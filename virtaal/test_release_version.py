#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os

import pytest

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging")


@pytest.fixture(scope="module")
def release_version():
    spec = importlib.util.spec_from_file_location(
        "release_version", os.path.join(PACKAGING_DIR, "release_version.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("ver, expected", [
    ("1.0.0-rc3", (1, 0, 0, 63)),
    ("1.0.0", (1, 0, 0, 99)),
    ("1.0.0-beta1", (1, 0, 0, 31)),
    ("1.1.0-a2", (1, 1, 0, 2)),
    ("1.0.1-rc1", (1, 0, 1, 61)),
    ("0.2", (0, 2, 0, 99)),
    ("1.1.0.dev0", (1, 1, 0, 0)),
])
def test_file_version_encodes_the_release_stage(release_version, ver, expected):
    assert release_version.file_version(ver) == expected


def test_rc_below_its_release(release_version):
    assert release_version.file_version("1.0.0-rc3") < release_version.file_version("1.0.0")


def test_beta_below_rc(release_version):
    assert release_version.file_version("1.0.0-beta3") < release_version.file_version("1.0.0-rc1")


def test_file_version_grows_with_every_release(release_version):
    versions = ["0.7.1", "1.0.0-beta1", "1.0.0-beta3", "1.0.0-rc1", "1.0.0-rc3", "1.0.0",
                "1.0.1-rc1", "1.0.1", "1.1.0-a1", "1.1.0-b1", "1.1.0-rc1", "1.1.0", "2.0.0"]
    encoded = [release_version.file_version(v) for v in versions]
    assert all(a < b for a, b in zip(encoded, encoded[1:]))


@pytest.mark.parametrize("ver", ["1.0.0-rc30", "1.0.0-rc", "1.1.0.dev2", "1", "70000.0.0"])
def test_file_version_refuses_what_it_cannot_encode(release_version, ver):
    with pytest.raises(ValueError):
        release_version.file_version(ver)


def test_windows_spec_uses_file_version():
    with open(os.path.join(PACKAGING_DIR, "windows", "virtaal.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert "_ver_tuple = file_version(virtaal_version)" in spec
    assert "filevers=_ver_tuple" in spec and "prodvers=_ver_tuple" in spec


def test_installer_stamps_the_file_version():
    with open(os.path.join(PACKAGING_DIR, "windows", "virtaal.iss"), encoding="utf-8-sig") as f:
        iss = f.read()
    assert "\nVersionInfoVersion={#MyAppFileVersion}\n" in iss
    with open(os.path.join(PACKAGING_DIR, "windows", "build_installer.ps1"), encoding="utf-8") as f:
        script = f.read()
    assert '"/DMyAppFileVersion=$fileVersion"' in script
    assert "file_version(ver)" in script
