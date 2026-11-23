#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import importlib.util
import os
import re

import pytest

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging", "macos")

# Apple: up to three period-separated integers, nothing else.
BUNDLE_VERSION = re.compile(r"^\d+(\.\d+){0,2}$")


@pytest.fixture(scope="module")
def generate_info_plist():
    spec = importlib.util.spec_from_file_location(
        "generate_info_plist", os.path.join(PACKAGING_DIR, "generate_info_plist.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("ver, expected", [
    ("1.0.0-rc3", "1.0.63"),
    ("1.0.0", "1.0.99"),
    ("1.0.1-rc1", "1.0.161"),
    ("1.0.1", "1.0.199"),
    ("1.1.0-b2", "1.1.32"),
    ("1.0.0-beta1", "1.0.31"),
    ("1.1.0-alpha2", "1.1.2"),
    ("0.7.1", "0.7.199"),
    ("0.2", "0.2.99"),
    ("1.1.0.dev0", "1.1.0"),
    ("1.0.0+local", "1.0.99"),
])
def test_bundle_version_encodes_the_release_stage(generate_info_plist, ver, expected):
    assert generate_info_plist.bundle_version(ver) == expected


def test_bundle_version_grows_with_every_release(generate_info_plist):
    versions = ["0.7.1", "1.0.0-beta1", "1.0.0-beta3", "1.0.0-rc1", "1.0.0-rc2", "1.0.0-rc3",
                "1.0.0", "1.0.1-rc1", "1.0.1", "1.1.0-a1", "1.1.0-b1", "1.1.0-rc1", "1.1.0"]
    encoded = [generate_info_plist.bundle_version(v) for v in versions]

    for bundle in encoded:
        assert BUNDLE_VERSION.match(bundle) and len(bundle) <= 18
    as_tuples = [tuple(int(n) for n in bundle.split(".")) for bundle in encoded]
    assert all(a < b for a, b in zip(as_tuples, as_tuples[1:]))


@pytest.mark.parametrize("ver", ["1.0.0-rc30", "1.0.0-rc0", "1.0.0-rc", "1.1.0.dev2", "1", "1.0.0-preview1"])
def test_bundle_version_refuses_what_it_cannot_encode(generate_info_plist, ver):
    with pytest.raises(ValueError):
        generate_info_plist.bundle_version(ver)


def test_plist_bundle_version_is_integers_only(generate_info_plist, monkeypatch):
    monkeypatch.setattr(generate_info_plist, "virtaal_version", "1.0.0-rc3")
    plist = generate_info_plist.build_plist()
    assert BUNDLE_VERSION.match(plist["CFBundleVersion"])
    assert plist["CFBundleShortVersionString"] == "1.0.0-rc3"


def test_spec_uses_the_same_bundle_version():
    with open(os.path.join(PACKAGING_DIR, "virtaal.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert '"CFBundleVersion": bundle_version(virtaal_version)' in spec
