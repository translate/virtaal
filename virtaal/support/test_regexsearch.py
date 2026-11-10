#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Risky regular expressions run in a child process with a time limit (#4692)."""

import re
import sys
import time

import pytest

from virtaal.support import regexsearch


@pytest.mark.parametrize('pattern', [
    r'(a+)+b',
    r'(a+)+$',
    r'(\w+\s?)+$',
    r'(a*)*',
    r'(?:a|aa)+$',
    r'(x+x+)+y',
    r'((ab)*c)+',
    r'(?=(a+)+)b',
])
def test_nested_repetition_is_risky(pattern):
    assert regexsearch.is_risky(pattern)


@pytest.mark.parametrize('pattern', [
    'file',
    r'fi(le)',
    r'\w+\s?',
    r'a+b+c*',
    r'(ab)+',
    r'[ab]+',
    r'(a|b)+',  # a character set, not an alternation, once parsed
    r'cat|dog',
    r'(a+)?b',
    re.escape('(a+)+b'),
    '(',  # invalid: re.compile() reports it
])
def test_a_plain_expression_is_not_risky(pattern):
    assert not regexsearch.is_risky(pattern)


def test_find_spans_finds_what_re_finds():
    strings = ['xaab', 'b', 'nothing', 'aab aab']

    spans = regexsearch.find_spans(r'(a+)+b', re.IGNORECASE, strings)

    assert spans == [[m.span() for m in re.finditer(r'(a+)+b', s, re.IGNORECASE)] for s in strings]


def test_find_spans_stops_a_search_that_takes_too_long(caplog):
    start = time.monotonic()

    with pytest.raises(regexsearch.SearchTimeout):
        regexsearch.find_spans(r'(a+)+$', 0, ['a' * 255 + '!'], timeout=1)

    assert time.monotonic() - start < 10
    assert 'stopped after 1 seconds' in caplog.text


def _slow_start(monkeypatch, delay):
    """Start the child only after delay seconds, like a frozen build
    unpacking itself."""
    from virtaal.support import helperprocess

    code = ('import runpy, time; time.sleep(%s); '
            'runpy.run_module("virtaal.support.regexsearch", run_name="__main__")' % delay)
    monkeypatch.setattr(helperprocess, 'command', lambda module: [sys.executable, '-c', code])


def test_a_slow_start_does_not_count_against_the_time_limit(monkeypatch):
    _slow_start(monkeypatch, 3)

    spans = regexsearch.find_spans(r'(a+)+b', 0, ['xaab'], timeout=1)

    assert spans == [[(1, 4)]]


def test_a_child_that_never_starts_is_stopped(monkeypatch, caplog):
    monkeypatch.setattr(regexsearch, 'STARTUP_LIMIT', 1)
    _slow_start(monkeypatch, 30)
    start = time.monotonic()

    with pytest.raises(regexsearch.SearchTimeout):
        regexsearch.find_spans(r'(a+)+b', 0, ['xaab'], timeout=1)

    assert time.monotonic() - start < 10
    assert 'took over 1 seconds to start' in caplog.text
