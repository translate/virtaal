#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from translate.storage.placeables.terminology import TerminologyPlaceable

from virtaal.plugins.terminology.termview import TerminologyCombo


def test_combo_handles_more_than_one_translation():
    # Only built when a placeable has more than one match, e.g. a
    # terminology entry with two definitions for the same source.
    elem = TerminologyPlaceable('drink')
    elem.translations = ['drank', 'dryf']

    TerminologyCombo(elem)
