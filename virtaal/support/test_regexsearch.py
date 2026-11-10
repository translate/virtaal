#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Risky regular expressions run in a child process with a time limit (#4692)."""

import re
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
