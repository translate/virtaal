#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Finding libgettextpo, and the frozen-build self-check without it.
Runs with or without the library installed."""

import ctypes.util
import gc
import logging
import sys

import pytest

from virtaal.common import pan_app
from virtaal.common.platform import Platform
from virtaal.support import gettextpo


@pytest.fixture(autouse=True)
def _unloaded(monkeypatch):
    # The loaded library is cached for the process; start each test without it.
    monkeypatch.setattr(gettextpo, '_lib', None)
    monkeypatch.setattr(gettextpo, '_load_attempted', False)


@pytest.fixture
def ui_languages(monkeypatch):
    # Not the real one: it would switch the whole test process's UI language.
    languages = []
    monkeypatch.setattr(pan_app, 'set_ui_language', languages.append)
    return languages


def _candidates(monkeypatch, *names):
    monkeypatch.setattr(gettextpo, '_library_candidates', lambda: iter(names))


def test_without_find_library_the_plain_names_are_tried(monkeypatch):
    monkeypatch.setattr(ctypes.util, 'find_library', lambda name: None)

    assert list(gettextpo._library_candidates()) == list(gettextpo._LIBRARY_NAMES)


def test_a_library_that_does_not_load_is_skipped(monkeypatch, caplog):
    _candidates(monkeypatch, '/nonexistent/libgettextpo.so.0')

    with caplog.at_level(logging.DEBUG):
        assert not gettextpo.available()

    assert 'Could not load /nonexistent/libgettextpo.so.0' in caplog.text
    assert 'msgfmt checks disabled' in caplog.text


def test_a_bundled_library_that_does_not_load_is_a_warning(monkeypatch, caplog, tmp_path):
    # A frozen build's own copy failing to load is a packaging bug.
    monkeypatch.setattr(gettextpo, 'platform',
                        Platform(sys_platform='linux', frozen=True, executable=str(tmp_path / 'virtaal')))
    _candidates(monkeypatch, '/nonexistent/libgettextpo.so.0')

    gettextpo.available()

    assert [r.levelno for r in caplog.records if 'Could not load' in r.getMessage()] == [logging.WARNING]


@pytest.mark.skipif(not ctypes.util.find_library('c'), reason="no C library to load by name")
def test_a_library_without_the_checking_api_is_skipped(monkeypatch, caplog):
    libc = ctypes.util.find_library('c')
    _candidates(monkeypatch, libc)

    with caplog.at_level(logging.DEBUG):
        assert not gettextpo.available()

    assert '%s lacks' % libc in caplog.text


def test_the_checker_needs_the_library(monkeypatch):
    unraisable = []
    monkeypatch.setattr(sys, 'unraisablehook', unraisable.append)
    _candidates(monkeypatch)

    with pytest.raises(RuntimeError, match='libgettextpo is not available'):
        gettextpo.MsgfmtChecker()
    gc.collect()

    # Its __del__ ran on the half-built checker without failing.
    assert unraisable == []


def test_self_check_without_the_library(monkeypatch, ui_languages):
    _candidates(monkeypatch)

    assert gettextpo.self_check('de') == (None, None)
    assert ui_languages == ['de']


def test_self_check_without_a_ui_catalog(monkeypatch):
    # A Flatpak without its locale extension: msgfmt's message stays English.
    def missing_catalog(lang):
        raise FileNotFoundError(lang)
    monkeypatch.setattr(pan_app, 'set_ui_language', missing_catalog)
    _candidates(monkeypatch)

    assert gettextpo.self_check('de') == (None, None)
