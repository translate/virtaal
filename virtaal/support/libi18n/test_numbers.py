#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest

from virtaal.common import pan_app
from virtaal.support.libi18n.numbers import (
    format_number,
    format_percent,
    format_size,
    localise_digits,
    ui_locale,
)


@pytest.mark.parametrize('lang, expected', [
    ('pt_BR', 'pt_BR'),
    ('zh_CN', 'zh_Hans_CN'),
    ('sr@latin', 'sr_Latn'),
    ('ca@valencia', 'ca_ES_VALENCIA'),
    # Babel doesn't know Acholi; the pseudo-translation locales aren't real.
    ('ach', 'root'),
    ('pseudo-source', 'root'),
])
def test_ui_locale(lang, expected):
    assert str(ui_locale(lang)) == expected


@pytest.mark.parametrize('lang, expected', [
    ('en', 'Page 12'),
    ('ar', 'Page 12'),
    ('ar_EG', 'Page ١٢'),
    ('fa', 'Page ۱۲'),
    ('bn_IN', 'Page ১২'),
])
def test_localise_digits_uses_the_default_numbering_system(monkeypatch, lang, expected):
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    assert localise_digits('Page 12') == expected


@pytest.mark.parametrize('lang, expected', [
    ('en', '1,234,567'),
    ('de', '1.234.567'),
    ('fa', '۱٬۲۳۴٬۵۶۷'),
    ('pseudo-source', '1,234,567'),
])
def test_format_number(monkeypatch, lang, expected):
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    assert format_number(1234567) == expected


@pytest.mark.parametrize('lang, fraction, decimals, expected', [
    ('en', 0.205, 1, '20.5%'),
    ('de', 0.205, 1, '20,5\xa0%'),
    ('tr', 0.205, 1, '%20,5'),
    ('bn_IN', 0.205, 1, '২০.৫%'),
    ('en', 1, 0, '100%'),
])
def test_format_percent(monkeypatch, lang, fraction, decimals, expected):
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    assert format_percent(fraction, decimals) == expected


@pytest.mark.parametrize('lang, size, expected', [
    ('en', 512, '512 byte'),
    ('en', 18_700, '18.7 kB'),
    ('de', 18_700, '18,7 kB'),
    ('fr', 18_700, '18,7\u202fko'),
    ('ne', 18_700, '१८.७ kB'),
    ('bn_IN', 512, '৫১২ বাইট'),
    ('en', 5_242_880, '5.2 MB'),
    ('en', 1_234_567_890_123_456, '1,234.6 TB'),
])
def test_format_size(monkeypatch, lang, size, expected):
    monkeypatch.setattr(pan_app, 'ui_language', lang)

    assert format_size(size) == expected
