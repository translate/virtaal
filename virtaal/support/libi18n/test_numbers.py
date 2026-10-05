#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins

import pytest

from virtaal.support.libi18n.numbers import localise_digits


@pytest.mark.parametrize('translation, expected', [
    ('0123456789', 'Page 12'),
    ('٠١٢٣٤٥٦٧٨٩', 'Page ١٢'),
    # A translation that isn't exactly ten digits is ignored.
    ('0-9', 'Page 12'),
])
def test_localise_digits(monkeypatch, translation, expected):
    monkeypatch.setattr(builtins, '_', lambda s: translation if s == '0123456789' else s)

    assert localise_digits('Page 12') == expected
