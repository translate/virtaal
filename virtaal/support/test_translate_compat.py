#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import locale
import os

import pytest
from translate.storage.placeables import StringElem

from virtaal.common.platform import platform
from virtaal.support import translate_compat
from virtaal.support.translate_compat import (
    _first_alternative,
    _fix_language_name,
    forceunicode,
    gettext_country,
    gettext_domain,
    gettext_lang,
    gettext_script,
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


def test_tr_lang_translates_a_semicolon_joined_name_by_its_cleaned_up_form():
    assert tr_lang('de')('Spanish; Castilian').startswith('Spanisch')


def test_tr_lang_translates_the_country_too():
    assert tr_lang('de')('Portuguese (Brazil)') == 'Portugiesisch (Brasilien)'


def test_tr_lang_translates_a_script_qualifier():
    # "Latin" is no country: the script names catalog translates it (#4681).
    assert tr_lang('de')('Serbian (Latin)', 'sr@latin') == 'Serbisch (Lateinisch)'
    assert tr_lang('sr@latin')('Serbian (Latin)', 'sr@latin') == 'srpski (latinski)'
    assert tr_lang('be')('Uzbek (Cyrillic)', 'uz@cyrillic').endswith('(кірыліца)')


def test_tr_lang_keeps_a_qualifier_neither_catalog_has():
    assert tr_lang('de')('Catalan; Valencian (Valencia)', 'ca@valencia').endswith('(Valencia)')


def test_gettext_script_uses_pycountrys_locale_dir_when_available():
    assert gettext_script('de')('Cyrillic') == 'Kyrillisch'


def test_gettext_script_falls_back_to_iso_15924_without_pycountry(monkeypatch):
    monkeypatch.setattr(translate_compat, 'pycountry', None)

    assert gettext_script('en')('Latin') == 'Latin'


def test_tr_lang_names_a_language_family_by_its_code():
    # Songhai is an ISO 639-5 family, with no ISO 639-3 entry.
    assert tr_lang('de')('Songhai languages', 'son') == 'Songhai-Sprachen'


def test_tr_lang_keeps_an_untranslated_family_in_english():
    assert tr_lang('xx')('Songhai languages', 'son') == 'Songhay'


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


def test_virtaals_own_catalog_names_a_language_family(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, 'locale_dir', str(tmp_path))
    _install_catalog(tmp_path, 'xx', 'iso639-5', {'Songhai languages': 'Songhai'})

    assert tr_lang('xx')('Songhai languages', 'son') == 'Songhai'


def test_shipped_language_name_lite_catalogs_are_read(tmp_path, monkeypatch):
    # setup.py compiles each po/LINGUAS-lite entry to <domain>.mo, read
    # in its own domain: iso639-3 for languages, iso639-5 for families.
    import pycountry

    from virtaal.support.libi18n import lite
    po_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'po')
    monkeypatch.setattr(platform, 'locale_dir', str(tmp_path))
    entries = [line.split('/') for line in lite.read_linguas(os.path.join(po_dir, 'LINGUAS-lite'))]
    names = [(domain, lang) for domain, lang in entries if domain not in lite.LIBRARY_DOMAINS]
    assert names
    for domain, lang in names:
        po_file = os.path.join(po_dir, 'lite', domain, lang + '.po')
        lite.merge(None, po_file, str(tmp_path / lang / 'LC_MESSAGES' / (domain + '.mo')))
        messages = lite.read_lite_po(po_file)
        read = gettext_domain(lang, domain, pycountry.LOCALES_DIR)
        assert any(read(name) == messages[name] != name for name in messages if name)


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


def test_tr_lang_looks_a_language_up_by_its_code_first():
    # translate-toolkit's "Nepali" and "Panjabi; Punjabi" aren't the
    # catalog's names; "Nepali (macrolanguage)" and "Panjabi" are.
    f = tr_lang('fr')

    assert f('Nepali', 'ne') == 'Népalais'
    assert f('Panjabi; Punjabi', 'pa') == 'Pendjabi'


def test_tr_lang_counts_a_translation_spelled_like_its_name():
    assert tr_lang('de')('Pedi; Sepedi; Northern Sotho', 'nso') == 'Pedi'


def test_tr_lang_falls_back_to_the_name_when_the_code_isnt_translated():
    assert tr_lang('af')('Pedi; Sepedi; Northern Sotho', 'nso') == 'Northern Sotho'


def test_tr_lang_by_code_finds_a_catalogs_inverted_name():
    # Galician only translates "Frisian, Western", not "Western Frisian".
    assert tr_lang('gl')('Frisian', 'fy') == 'Frisón do oeste'


def test_tr_lang_by_code_keeps_an_inverted_names_alternatives():
    # The semicolon stands for "Gaelic, Scottish"'s comma.
    assert tr_lang('lt')('Gaelic; Scottish Gaelic', 'gd') == 'Gėlų; škotų'


def test_tr_lang_by_code_skips_an_inverted_name_copied_unchanged():
    # Asturian's catalog has "Sami, Northern" as its own translation.
    assert tr_lang('ast')('Northern Sami', 'se') == 'Northern Sami'


def test_tr_lang_by_code_keeps_a_dialects_country():
    assert tr_lang('de')('Portuguese (Brazil)', 'pt_BR') == 'Portugiesisch (Brasilien)'


@pytest.mark.parametrize('english,name,expected', [
    ('Chinese', '中文; 汉语; 华语', '中文'),
    ('Irish', 'irsk; gælisk (irsk)', 'irsk'),
    # A semicolon standing in for the English name's own comma.
    ('Gaelic, Scottish', 'Gėlų; škotų', 'Gėlų; škotų'),
    # Inside a qualifier.
    ('Bislama', 'Bislama (Vanuatu; Kuzey Pasifik)', 'Bislama (Vanuatu; Kuzey Pasifik)'),
    ('German', 'Deutsch', 'Deutsch'),
])
def test_first_alternative(english, name, expected):
    assert _first_alternative(english, name) == expected


def test_tr_lang_by_code_names_only_the_first_of_a_catalogs_alternatives():
    # #4461: zh_CN's catalog names Chinese "中文; 汉语; 华语".
    assert tr_lang('zh_CN')('Chinese (China)', 'zh_CN') == '中文 (中国)'
