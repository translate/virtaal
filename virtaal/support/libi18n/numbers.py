#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

"""Numbers shown in the UI language's own digits."""


def localise_digits(text):
    """text with its ASCII digits replaced by the UI language's own."""
    #l10n: The digits zero to nine of your language's number system, in
    #order, e.g. "٠١٢٣٤٥٦٧٨٩" for Arabic-Indic digits. Leave as
    #"0123456789" if your language uses these digits.
    digits = _("0123456789")
    if len(digits) != 10:
        return text
    return text.translate(str.maketrans("0123456789", digits))
