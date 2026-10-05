#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins

import pytest

from virtaal.common import pan_app
from virtaal.support.libi18n.numbers import cldr_digits, localise_digits

ARABIC_INDIC = '٠١٢٣٤٥٦٧٨٩'
BENGALI = '০১২৩৪৫৬৭৮৯'


def _translate_digits(monkeypatch, translation):
    monkeypatch.setattr(builtins, '_', lambda s: translation if s == '0123456789' else s)


@pytest.mark.parametrize('translation, expected', [
    (ARABIC_INDIC, 'Page ١٢'),
    # A translation that isn't exactly ten digits is ignored.
    ('0-9', 'Page 12'),
])
def test_localise_digits_uses_the_translated_digits(monkeypatch, translation, expected):
    _translate_digits(monkeypatch, translation)
    monkeypatch.setattr(pan_app, 'ui_language', 'bn')

    assert localise_digits('Page 12') == expected


@pytest.mark.parametrize('lang, expected', [
    ('en', 'Page 12'),
    ('bn_IN', 'Page ১২'),
    ('pseudo-source', 'Page 12'),
])
def test_localise_digits_falls_back_to_cldr_when_untranslated(monkeypatch, lang, expected):
    _translate_digits(monkeypatch, '0123456789')
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    assert localise_digits('Page 12') == expected


@pytest.mark.parametrize('lang, expected', [
    ('bn', BENGALI),
    # CLDR's default for Arabic is 0-9, but Egyptian Arabic's isn't.
    ('ar', '0123456789'),
    ('ar_EG', ARABIC_INDIC),
    ('ar_EG@foo', ARABIC_INDIC),
    # Devanagari-script Kashmiri uses 0-9, unlike Kashmiri.
    ('ks_Deva_IN', '0123456789'),
    ('', '0123456789'),
])
def test_cldr_digits(lang, expected):
    assert cldr_digits(lang) == expected
