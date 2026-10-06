#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Numbers formatted for the UI language: Babel's CLDR patterns and
symbols, with the digits of the locale's default numbering system."""

import copy

from babel import Locale, UnknownLocaleError

from virtaal.support.libi18n.cldr_numbering_systems import DIGITS

LATIN = "0123456789"

# gettext's @modifiers as CLDR subtags.
_MODIFIERS = {"latin": "_Latn", "cyrillic": "_Cyrl", "valencia": "_ES_VALENCIA"}


def ui_locale(lang=None):
    """The Babel Locale for a UI language code such as "pt_BR" or
        "sr@latin" (the current UI language by default), or CLDR's root
        locale for one Babel doesn't know."""
    if lang is None:
        from virtaal.common import pan_app
        lang = pan_app.ui_language or "en"
    code, _, modifier = lang.partition("@")
    try:
        return Locale.parse(code + _MODIFIERS.get(modifier, ""))
    except (ValueError, UnknownLocaleError):
        return Locale.parse("root")


def localise_digits(text, locale=None):
    """text with its ASCII digits replaced by those of the locale's
        default numbering system."""
    digits = DIGITS.get((locale or ui_locale()).default_numbering_system, LATIN)
    if digits == LATIN:
        return text
    return text.translate(str.maketrans(LATIN, digits))


def format_number(number):
    """An integer in the UI language's digits and grouping."""
    locale = ui_locale()
    return localise_digits(locale.decimal_formats[None].apply(number, locale, numbering_system="default"), locale)


def format_percent(fraction, decimals=1):
    """fraction (0.25 for 25%) as a percentage in the UI language's
        own pattern, with exactly decimals decimal places."""
    locale = ui_locale()
    pattern = copy.copy(locale.percent_formats[None])
    pattern.frac_prec = (decimals, decimals)
    return localise_digits(pattern.apply(fraction, locale, numbering_system="default"), locale)
