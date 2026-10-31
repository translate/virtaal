#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest

from virtaal.models.langmodel import LanguageModel


def test_hyphenated_langcode():
    """A code not stored exactly as given (e.g. XLIFF's hyphenated
    "en-GB" vs. the underlying language table's "en_GB") should resolve
    via _match_normalized_langcode(), not raise."""
    model = LanguageModel("en-GB")
    assert model.code == "en_GB"
    assert model.nplurals == 2


def test_underscored_langcode():
    model = LanguageModel("en_GB")
    assert model.code == "en_GB"


def test_unknown_langcode_falls_back():
    model = LanguageModel("not-a-real-language")
    assert model.nplurals == 0


@pytest.mark.parametrize('code, expected, name', [
    ('sr@latin', 'sr@latin', 'Serbian (Latin)'),
    ('sr_Latn', 'sr@latin', 'Serbian (Latin)'),
    ('sr-Latn-RS', 'sr@latin', 'Serbian (Latin)'),
    ('uz@cyrillic', 'uz@cyrillic', 'Uzbek (Cyrillic)'),
    ('be@latin', 'be@latin', 'Belarusian (Latin)'),
    # A language's default script stays the plain language.
    ('sr_Cyrl', 'sr', 'Serbian'),
    ('uz_Latn', 'uz', 'Uzbek'),
])
def test_script_variants_keep_their_script(code, expected, name):
    # sr@latin used to become plain sr, Cyrillic Serbian (#4681).
    model = LanguageModel(code)
    assert (model.code, model.name) == (expected, name)


def test_script_variant_has_its_languages_plural_forms():
    serbian, latin = LanguageModel('sr'), LanguageModel('sr@latin')
    assert (latin.nplurals, latin.plural) == (serbian.nplurals, serbian.plural)
