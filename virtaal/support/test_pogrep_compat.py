#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import unicodedata

from translate.storage import po

from virtaal.support.pogrep_compat import GrepFilter


def _unit(source, target):
    u = po.pofile().addsourceunit(source)
    u.target = target
    return u


def test_getmatches_does_not_raise():
    # Real crash (Python 3.14+): upstream GrepFilter.getmatches() ORs
    # in re.LOCALE, which is invalid with a str pattern.
    units = [_unit("Don't know", "Don't know")]
    f = GrepFilter(searchstring="Don't know", searchparts=('source', 'target'),
                    ignorecase=True, useregexp=False, max_matches=200000)

    matches, indexes = f.getmatches(units)

    assert indexes == [0]
    assert [m.start for m in matches] == [0, 0]  # matched in both source and target


def test_getmatches_maps_offsets_through_nfd_decomposed_accents():
    # A search term with no accents at all must still land on the right
    # offsets when *other* text in the same string is NFD-decomposed
    # (e.g. a Java/Oracle export), since the underlying normalize()/
    # real_index() machinery matches against the NFC-composed form.
    nfd_e_acute = unicodedata.normalize('NFD', "é")
    units = [_unit("x", nfd_e_acute + " Don't know and also Don't know " + nfd_e_acute)]
    f = GrepFilter(searchstring="Don't know", searchparts=('target',),
                    ignorecase=True, useregexp=False, max_matches=200000)

    matches, _ = f.getmatches(units)

    raw = units[0].target
    assert [raw[m.start:m.end] for m in matches] == ["Don't know", "Don't know"]
