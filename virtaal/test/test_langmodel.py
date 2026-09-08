#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

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
