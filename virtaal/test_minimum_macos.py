#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import plistlib

import pytest

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging", "macos")


@pytest.fixture
def minimum_macos():
    spec = importlib.util.spec_from_file_location("minimum_macos", os.path.join(PACKAGING_DIR, "minimum_macos.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD_VERSION = """Load command 9
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos %s
      sdk 26.0
"""
VERSION_MIN = """Load command 8
      cmd LC_VERSION_MIN_MACOSX
  cmdsize 16
  version %s
      sdk 10.15
"""


def test_reads_the_minimum_from_either_load_command(minimum_macos):
    assert minimum_macos.minimum_from_load_commands(BUILD_VERSION % "14.0") == "14.0"
    assert minimum_macos.minimum_from_load_commands(VERSION_MIN % "10.13") == "10.13"
    assert minimum_macos.minimum_from_load_commands("Load command 0\n cmd LC_SEGMENT_64\n") is None


def test_a_universal_binary_needs_its_highest_slice(minimum_macos):
    assert minimum_macos.minimum_from_load_commands(BUILD_VERSION % "11.0" + BUILD_VERSION % "10.13") == "11.0"


def test_versions_compare_numerically_not_as_text(minimum_macos, tmp_path, monkeypatch):
    files = []
    for name, version in (("a", "9.0"), ("b", "26.0"), ("c", "14.4")):
        path = tmp_path / name
        path.write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 8)
        files.append(path)
    versions = dict(zip(files, ("9.0", "26.0", "14.4")))
    monkeypatch.setattr(minimum_macos, "binary_minimum", versions.get)
    (tmp_path / "notes.txt").write_text("not a binary")

    assert minimum_macos.minimum_macos(files + [tmp_path / "notes.txt"]) == "26.0"


def test_check_fails_when_the_app_declares_an_older_macos(minimum_macos, tmp_path, monkeypatch):
    contents = tmp_path / "Virtaal.app" / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "MacOS" / "virtaal").write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 8)
    monkeypatch.setattr(minimum_macos, "binary_minimum", lambda path: "14.0")
    for declared, result in (("10.15", 1), ("14.0", 0), ("15.0", 0)):
        with open(contents / "Info.plist", "wb") as f:
            plistlib.dump({"LSMinimumSystemVersion": declared}, f)
        assert minimum_macos.check(tmp_path / "Virtaal.app") == result
