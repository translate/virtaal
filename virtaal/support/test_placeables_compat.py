#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import re
import time

from translate.storage.placeables import general

from virtaal.support import placeables_compat  # noqa: F401

_UPSTREAM = re.compile(r"((mailto:)|)[A-Za-z0-9]+[-a-zA-Z0-9._%]*@(([-A-Za-z0-9]+)\.)+[a-zA-Z]{2,4}")


def _spans(regex, text):
    return [m.span() for m in regex.finditer(text)]


def test_a_long_word_parses_quickly():
    # #4335: 4096 letters with no "@" took 20 s; base64 data, hashes and long URLs look like this.
    start = time.perf_counter()
    general.EmailPlaceable.parse('x' * 4096)
    general.EmailPlaceable.parse('http://' + 'a' * 4000)

    assert time.perf_counter() - start < 1


def test_matches_the_same_text_as_upstream():
    texts = [
        'Write to me@example.org.', 'mailto:a.b-c_d%e@mail.example.co.za now', '--joe@example.com',
        'a@b.comxyz@c.org', 'user@localhost', 'no address here', '1@2.ab and x.y@z.info',
        'Ann.Vertaler@translate.org.za, ben@example.org',
    ]
    for text in texts:
        assert _spans(general.EmailPlaceable.regex, text) == _spans(_UPSTREAM, text), text


def test_parse_still_finds_an_address():
    parsed = general.EmailPlaceable.parse('Write to me@example.org today')

    assert [str(elem) for elem in parsed if isinstance(elem, general.EmailPlaceable)] == ['me@example.org']
