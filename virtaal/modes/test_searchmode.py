#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from translate.storage import xliff

from virtaal.modes.searchmode import SearchMode
from virtaal.support.pogrep_compat import GrepFilter


class _FakeUnit:
    def __init__(self, strings):
        self.target = SimpleNamespace(strings=list(strings))

    def hasplural(self):
        return True


class _FakeMatch:
    def __init__(self, unit, part_n, start, end):
        self.unit = unit
        self.part = 'target'
        self.part_n = part_n
        self.start = start
        self.end = end


def test_replace_match_updates_plural_target_string():
    """replace_match()'s plural branch read an undefined `strings` name
    instead of match.unit.target.strings - raised NameError on every
    replace of a plural target when no unit_controller is wired in
    (the "replace all" style call path)."""
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(
        main_controller=SimpleNamespace(unit_controller=None))

    unit = _FakeUnit(['cat', 'cats'])
    match = _FakeMatch(unit, part_n=1, start=0, end=4)

    mode.replace_match(match, 'dogs')

    assert unit.target == ['cat', 'dogs']


def _xliff_unit(source, target):
    u = xliff.xlifffile().addsourceunit(source)
    u.target = target
    return u


def test_replace_all_on_xliff_units():
    """_get_unit_matches_dict() keyed matches by the unit object itself
    - translate-toolkit's lxml-based units (XLIFF, TMX, TS) define
    __eq__ without __hash__, making them unhashable, so clicking
    "Replace All" on any such file crashed with TypeError before a
    single replacement happened (#3258)."""
    units = [
        _xliff_unit("Don't know", "Don't know"),
        _xliff_unit("x", "Don't know and also Don't know"),
    ]
    f = GrepFilter(searchstring="Don't know", searchparts=('target',),
                    ignorecase=True, useregexp=False, max_matches=200000)
    matches, _ = f.getmatches(units)

    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(
        main_controller=SimpleNamespace(
            unit_controller=None,
            undo_controller=SimpleNamespace(record_start=lambda: None, record_stop=lambda: None),
        ))
    mode.matches = matches
    mode.ent_replace = SimpleNamespace(get_text=lambda: 'REPLACED')
    mode._search_timeout = 0  # _cancel_search_timeout() then no-ops
    mode.update_search = lambda: None  # not under test here

    mode._replace_all()  # must not raise

    assert units[0].target == 'REPLACED'
    assert units[1].target == 'REPLACED and also REPLACED'
