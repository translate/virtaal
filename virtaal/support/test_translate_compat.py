#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import locale

from translate.storage.placeables import StringElem

from virtaal.common.platform import platform
from virtaal.support import translate_compat
from virtaal.support.translate_compat import (
    _fix_language_name,
    forceunicode,
    gettext_country,
    gettext_domain,
    gettext_lang,
    tr_lang,
)

# tr_lang() #

def test_tr_lang_formats_a_language_with_country():
    handle = tr_lang('en')

    assert handle('English (United Kingdom)') == 'English (United Kingdom)'


def test_tr_lang_leaves_a_macrolanguage_suffix_unformatted():
    # The "language (country)" reformatting is deliberately skipped for
    # this one pseudo-country value - the whole original name passes
    # through _fix_language_name() untouched instead.
    handle = tr_lang('en')

    assert handle('Chinese (macrolanguage)') == 'Chinese (macrolanguage)'


def test_tr_lang_handles_a_plain_language_name():
    handle = tr_lang('en')

    assert handle('English') == 'English'


# _fix_language_name() #

def test_fix_language_name_replaces_a_known_untranslated_name():
    assert _fix_language_name('Catalan; Valencian') == 'Catalan'


def test_fix_language_name_truncates_a_long_name_at_a_semicolon():
    assert _fix_language_name('AAAAAAAAAAAAAAAAAAAA; extra stuff') == 'AAAAAAAAAAAAAAAAAAAA'


def test_fix_language_name_leaves_a_short_name_unchanged():
    assert _fix_language_name('short') == 'short'


def test_fix_language_name_leaves_a_long_name_without_a_semicolon_unchanged():
    name = 'A very long language name with no semicolon'
    assert _fix_language_name(name) == name


# gettext_domain() #

def test_gettext_domain_uses_the_given_langcode():
    f = gettext_domain('en', 'iso_639')

    assert f('anything') == 'anything'  # fallback=True, no real .mo installed


def test_gettext_domain_falls_back_to_the_system_locale_on_windows(monkeypatch):
    monkeypatch.setattr(platform, 'is_windows', True)
    monkeypatch.setattr(locale, 'getdefaultlocale', lambda: ('en_US', 'UTF-8'))

    f = gettext_domain(None, 'iso_639')

    assert f('anything') == 'anything'


# gettext_lang() / gettext_country() #

def test_gettext_lang_uses_pycountrys_locale_dir_when_available():
    f = gettext_lang('en')

    assert f('anything') == 'anything'


def test_gettext_lang_falls_back_to_iso_639_without_pycountry(monkeypatch):
    monkeypatch.setattr(translate_compat, 'pycountry', None)

    f = gettext_lang('en')

    assert f('anything') == 'anything'


def test_gettext_country_uses_pycountrys_locale_dir_when_available():
    f = gettext_country('en')

    assert f('anything') == 'anything'


def test_tr_lang_translates_the_country_too():
    assert tr_lang('de')('Portuguese (Brazil)') == 'Portugiesisch (Brasilien)'


def test_gettext_country_falls_back_to_iso_3166_without_pycountry(monkeypatch):
    monkeypatch.setattr(translate_compat, 'pycountry', None)

    f = gettext_country('en')

    assert f('anything') == 'anything'


# Virtaal's own ISO catalogs (lite or pseudo translations) #

def _install_catalog(locale_dir, lang, domain, entries):
    from translate.tools.pocompile import convertmo
    po = 'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n'
    po += ''.join('\nmsgid "%s"\nmsgstr "%s"\n' % pair for pair in entries.items())
    po_file = locale_dir / (lang + domain + '.po')
    po_file.write_text(po, encoding='utf-8')
    mo_dir = locale_dir / lang / 'LC_MESSAGES'
    mo_dir.mkdir(parents=True, exist_ok=True)
    with open(po_file, 'rb') as infile, open(mo_dir / (domain + '.mo'), 'w') as outfile:
        convertmo(infile, outfile, None)


def test_virtaals_own_catalog_fills_what_pycountrys_lacks(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'locale_dir', str(tmp_path))
    _install_catalog(tmp_path, 'xx', 'iso639-3', {'Zulu': 'isiZulu'})

    assert gettext_lang('xx')('Zulu') == 'isiZulu'


def test_pycountrys_catalog_wins_over_virtaals_own(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'locale_dir', str(tmp_path))
    _install_catalog(tmp_path, 'de', 'iso639-3', {'German': 'Not this'})

    assert gettext_lang('de')('German') == 'Deutsch'


# forceunicode() #

def test_forceunicode_passes_through_none():
    assert forceunicode(None) is None


def test_forceunicode_passes_through_a_plain_string():
    assert forceunicode('already text') == 'already text'


def test_forceunicode_decodes_bytes():
    assert forceunicode(b'bytes here') == 'bytes here'


def test_forceunicode_decodes_bytes_using_their_own_encoding_attribute():
    class _EncodedBytes(bytes):
        encoding = 'latin-1'

    assert forceunicode(_EncodedBytes('café'.encode('latin-1'))) == 'café'


def test_forceunicode_stringifies_a_stringelem():
    assert forceunicode(StringElem('elem text')) == 'elem text'
