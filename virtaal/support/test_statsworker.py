#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
import os
import runpy
import sys
import time

import pytest
from gi.repository import GLib
from translate.storage import factory

from virtaal.support import statsdb, statsworker

# conftest.py replaces it for every other test.
fill_in_background = statsworker.fill_in_background

PO = (
    'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
    'msgid "Hello"\nmsgstr "Hallo"\n\n'
    '#, fuzzy\nmsgid "World"\nmsgstr "Wêreld"\n\n'
    'msgid "Open"\nmsgstr ""\n'
)

XLIFF = '''<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
<file original="doc" source-language="en" target-language="af" datatype="plaintext"><body>
<trans-unit id="1" approved="yes"><source>One</source><target state="final">Een</target></trans-unit>
<trans-unit id="2"><source>Two</source><target state="needs-review-translation">Twee</target></trans-unit>
<trans-unit id="3"><source>Three</source></trans-unit>
<trans-unit id="4" translate="no"><source>Four</source></trans-unit>
<trans-unit id="5"><source>Five</source><target state="translated">Vyf</target></trans-unit>
</body></file></xliff>
'''


def _po(tmp_path, name='af.po'):
    path = tmp_path / name
    path.write_text(PO, encoding="utf-8")
    return str(path)


def _is_cached(path):
    cache = statsdb.StatsCache()
    cache.cur.execute("SELECT path FROM files WHERE path=?", (os.path.realpath(path),))
    return cache.cur.fetchone() is not None


# state_lists() #

def test_state_lists_match_the_stats_cache_for_po(tmp_path):
    path = _po(tmp_path)
    store = factory.getobject(path)

    expected = statsdb.StatsCache(str(tmp_path / 'stats.db')).filestatestats(path, store, extended=True)

    assert statsworker.state_lists(store) == expected


def test_state_lists_match_the_stats_cache_for_xliff_states(tmp_path):
    # XLIFF has more workflow states than PO, and untranslatable units.
    path = tmp_path / 'af.xlf'
    path.write_text(XLIFF, encoding="utf-8")
    store = factory.getobject(str(path))

    expected = statsdb.StatsCache(str(tmp_path / 'stats.db')).filestatestats(str(path), store, extended=True)

    assert statsworker.state_lists(store) == expected
    assert len(expected['extended']) > 2


# fill_in_background() / wait() #

def test_fill_in_background_caches_the_file_on_disk(tmp_path):
    path = _po(tmp_path)

    fill_in_background(path)
    statsworker.wait()

    assert _is_cached(path)


def test_fills_run_one_after_the_other(tmp_path):
    first, second = _po(tmp_path, 'one.po'), _po(tmp_path, 'two.po')

    fill_in_background(first)
    fill_in_background(second)

    assert statsworker._queued == [second]
    statsworker.wait()
    assert _is_cached(first) and _is_cached(second)


def test_the_main_loop_starts_the_next_fill(tmp_path):
    first, second = _po(tmp_path, 'one.po'), _po(tmp_path, 'two.po')

    fill_in_background(first)
    fill_in_background(second)
    deadline = time.monotonic() + 30
    while statsworker._running is not None and time.monotonic() < deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(0.01)

    assert statsworker._running is None
    assert _is_cached(first) and _is_cached(second)


def test_a_failed_fill_is_logged_and_the_next_one_still_runs(tmp_path, caplog):
    path = _po(tmp_path)

    with caplog.at_level(logging.DEBUG):
        fill_in_background(str(tmp_path / 'missing.po'))
        fill_in_background(path)
        statsworker.wait()

    assert 'missing.po' in caplog.text
    assert _is_cached(path)


def test_wait_returns_at_once_with_nothing_queued():
    statsworker.wait()


def test_poll_keeps_polling_while_the_fill_runs(monkeypatch):
    proc = type('Proc', (), {'poll': lambda self: None})()
    monkeypatch.setattr(statsworker, '_running', proc)

    assert statsworker._poll(proc) is True


def test_poll_stops_for_a_fill_that_is_no_longer_running(monkeypatch):
    monkeypatch.setattr(statsworker, '_running', None)

    assert statsworker._poll(object()) is False


def _run_child(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['statsworker', *args])
    monkeypatch.delitem(sys.modules, 'virtaal.support.statsworker')
    runpy.run_module('virtaal.support.statsworker', run_name='__main__')


def test_the_child_process_caches_the_file_in_the_given_database(tmp_path, monkeypatch):
    path = _po(tmp_path)
    statsfile = tmp_path / 'child.db'

    _run_child(monkeypatch, str(statsfile), path)

    cache = statsdb.StatsCache(str(statsfile))
    cache.cur.execute("SELECT count(*) FROM files")
    assert cache.cur.fetchone()[0] == 1


def test_the_child_process_exits_with_an_error_for_a_missing_file(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as exit_info:
        _run_child(monkeypatch, str(tmp_path / 'child.db'), str(tmp_path / 'missing.po'))

    assert exit_info.value.code == 1
