#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Numbers shown in the UI language's own digits."""

from virtaal.support.libi18n.cldr_digits import DIGITS as CLDR_DIGITS

LATIN = "0123456789"


def cldr_digits(lang):
    """CLDR's default digits for a locale code, e.g. "bn_IN" or
        "ca@valencia", trying ever less specific forms of it."""
    code = lang.split("@")[0]
    while code:
        if code in CLDR_DIGITS:
            return CLDR_DIGITS[code]
        code = code.rpartition("_")[0]
    return LATIN


def localise_digits(text):
    """text with its ASCII digits replaced by the UI language's own: its
        translators' choice, else CLDR's default."""
    from virtaal.common import pan_app
    #l10n: The digits zero to nine of your language's number system, in
    #order, e.g. "٠١٢٣٤٥٦٧٨٩" for Arabic-Indic digits. Leave untranslated
    #to use the Unicode CLDR's default digits for your language.
    digits = _("0123456789")
    if digits == LATIN:
        digits = cldr_digits(pan_app.ui_language or "")
    if len(digits) != 10:
        return text
    return text.translate(str.maketrans(LATIN, digits))
