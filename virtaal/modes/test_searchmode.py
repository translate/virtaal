#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.modes.searchmode import SearchMode


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
