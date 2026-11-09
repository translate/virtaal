#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import hashlib
import importlib.util
import os

import pytest

PACKAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "devsupport", "packaging")


def _fetch_dictionaries():
    spec = importlib.util.spec_from_file_location(
        "fetch_dictionaries", os.path.join(PACKAGING_DIR, "fetch_dictionaries.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned(module, name, content=b"x"):
    """Repins name's files to content, as if that were what's upstream."""
    digest = hashlib.sha256(content).hexdigest()
    module.DICTIONARIES[name] = {source: digest for source in module.DICTIONARIES[name]}


def test_fetches_the_pinned_files(tmp_path):
    module = _fetch_dictionaries()
    _pinned(module, "en_GB")
    urls = []

    paths = module.fetch(str(tmp_path), ["en_GB"], get=lambda url: urls.append(url) or b"x")

    assert sorted(os.path.basename(p) for p in paths) == ["README_en_GB.txt", "en_GB.aff", "en_GB.dic"]
    assert all(url.startswith(module.RAW) for url in urls) and len(urls) == 3
    assert (tmp_path / "en_GB.dic").read_bytes() == b"x"


def test_keeps_files_already_fetched(tmp_path):
    module = _fetch_dictionaries()
    _pinned(module, "en_US")
    module.fetch(str(tmp_path), ["en_US"], get=lambda url: b"x")

    def offline(url):
        raise AssertionError("fetched %s again" % url)
    module.fetch(str(tmp_path), ["en_US"], get=offline)


def test_refuses_a_changed_file(tmp_path):
    module = _fetch_dictionaries()
    _pinned(module, "en_US")

    with pytest.raises(SystemExit):
        module.fetch(str(tmp_path), ["en_US"], get=lambda url: b"changed")


def test_pins_a_commit_not_a_branch():
    module = _fetch_dictionaries()
    assert len(module.COMMIT) == 40 and module.COMMIT in module.RAW
