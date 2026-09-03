#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

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
