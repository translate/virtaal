#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import re
from types import SimpleNamespace

import pytest
from gi.repository import Gtk
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


def test_set_search_bg_accepts_a_colour():
    # A malformed generated CSS string raises Gtk.CssProvider's own
    # GLib.GError - this is really a check that the string built here
    # is valid CSS, not just that the call completes.
    mode = SearchMode.__new__(SearchMode)
    mode.ent_search = Gtk.Entry()
    mode._search_bg_provider = None

    mode._set_search_bg('#f66')


def test_set_search_bg_removes_its_previous_provider_on_a_later_call(monkeypatch):
    """Each call used to only ever add a new provider - toggling
        between the warning colour and the default on every keystroke
        would accumulate one per keystroke, never freed."""
    mode = SearchMode.__new__(SearchMode)
    mode.ent_search = Gtk.Entry()
    mode._search_bg_provider = None

    removed = []
    style = mode.ent_search.get_style_context()
    monkeypatch.setattr(style, 'remove_provider', lambda provider: removed.append(provider))

    mode._set_search_bg('#f66')
    first_provider = mode._search_bg_provider
    mode._set_search_bg('#fff')

    assert removed == [first_provider]


# _get_matches_for_unit() #

def test_get_matches_for_unit_filters_by_unit_identity():
    mode = SearchMode.__new__(SearchMode)
    unit_a, unit_b = object(), object()
    match_a = _FakeMatch(unit_a, part_n=0, start=0, end=0)
    match_b = _FakeMatch(unit_b, part_n=0, start=0, end=0)
    mode.matches = [match_a, match_b]

    assert mode._get_matches_for_unit(unit_a) == [match_a]


# _move_match() #

def test_move_match_ignores_a_call_when_not_the_current_mode():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=SimpleNamespace(name='OtherMode'))

    mode._move_match(1)  # must not raise


def test_move_match_researches_with_no_matchcursor_yet_then_selects():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=mode)
    calls = []
    match_obj = object()

    def fake_update_search():
        calls.append('update')
        mode.matches = [match_obj]
        mode.matchcursor = SimpleNamespace(index=0, move=lambda offset: calls.append(('move', offset)))

    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = fake_update_search
    mode.select_match = lambda m: calls.append(('select', m))

    mode._move_match(1)

    assert calls == ['cancel', 'update', ('move', 1), ('select', match_obj)]


def test_move_match_researches_instead_of_moving_a_stale_cursor():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=mode)
    mode.matches = []  # no matches -> stale
    mode.matchcursor = SimpleNamespace(index=0)
    calls = []
    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = lambda: calls.append('update')

    mode._move_match(1)

    assert calls == ['cancel', 'update']


def test_move_match_moves_and_selects_when_matches_are_fresh():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=mode)
    match_obj = object()
    mode.matches = [match_obj]
    moved = []
    mode.matchcursor = SimpleNamespace(index=0, move=lambda offset: moved.append(offset))
    selected = []
    mode.select_match = lambda m: selected.append(m)

    mode._move_match(1)

    assert moved == [1]
    assert selected == [match_obj]


# _cancel_search_timeout() #

def test_cancel_search_timeout_removes_a_pending_timeout(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    mode._search_timeout = 123
    removed = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.source_remove', removed.append)

    mode._cancel_search_timeout()

    assert removed == [123]
    assert mode._search_timeout == 0


def test_cancel_search_timeout_is_a_noop_without_a_pending_timeout(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    mode._search_timeout = 0
    removed = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.source_remove', removed.append)

    mode._cancel_search_timeout()

    assert removed == []


# _on_unit_modified() / _sync_matches_for_key() (#1789) #

def test_on_unit_modified_shifts_a_target_match_past_an_edit_before_it():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=0, end=3,
                             get_getter=lambda: (lambda: 'xcat'))
    mode.matches = [match]
    mode._match_text_cache = {(id(unit), 'target', 0): 'cat'}

    mode._on_unit_modified(None, unit)

    assert (match.start, match.end) == (1, 4)
    assert mode.matches == [match]


def test_on_unit_modified_keeps_a_target_match_unaffected_by_a_later_edit():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=0, end=3,
                             get_getter=lambda: (lambda: 'catx'))
    mode.matches = [match]
    mode._match_text_cache = {(id(unit), 'target', 0): 'cat'}

    mode._on_unit_modified(None, unit)

    assert (match.start, match.end) == (0, 3)
    assert mode.matches == [match]


def test_on_unit_modified_drops_a_target_match_the_edit_overlapped():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=0, end=3,
                             get_getter=lambda: (lambda: 'dog'))
    mode.matches = [match]
    mode._match_text_cache = {(id(unit), 'target', 0): 'cat'}

    mode._on_unit_modified(None, unit)

    assert mode.matches == []


def test_on_unit_modified_ignores_a_source_match():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='source', start=0, end=3, get_getter=lambda: (lambda: 'xyz'))
    mode.matches = [match]

    mode._on_unit_modified(None, unit)

    assert mode.matches == [match]


# _sync_matches_for_key() directly - the #1789 undo path goes through
# this without 'unit-modified' ever firing (see _on_textbox_refreshed) #

def test_sync_matches_for_key_seeds_the_cache_without_shifting_on_first_sight():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=2, end=5,
                             get_getter=lambda: (lambda: 'Virtaal'))
    mode.matches = [match]
    mode._match_text_cache = {}

    mode._sync_matches_for_key((id(unit), 'target', 0))

    assert (match.start, match.end) == (2, 5)
    assert mode._match_text_cache[(id(unit), 'target', 0)] == 'Virtaal'


def test_sync_matches_for_key_round_trips_an_insert_then_its_undo():
    """Scenario A from #1789: insert "taal" in front of "Virtaal", then
        undo it - the highlight on "rta" should end up back where it
        started, not stuck at the offset it had mid-edit."""
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    text = ['Virtaal']
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=2, end=5,
                             get_getter=lambda: (lambda: text[0]))
    mode.matches = [match]
    key = (id(unit), 'target', 0)
    mode._match_text_cache = {key: 'Virtaal'}

    text[0] = 'taalVirtaal'
    mode._sync_matches_for_key(key)
    assert (match.start, match.end) == (6, 9)
    assert text[0][match.start:match.end] == 'rta'

    text[0] = 'Virtaal'  # undo
    mode._sync_matches_for_key(key)
    assert (match.start, match.end) == (2, 5)
    assert text[0][match.start:match.end] == 'rta'


def test_sync_matches_for_key_drops_the_stale_cache_entry_once_unmatched():
    mode = SearchMode.__new__(SearchMode)
    key = (1, 'target', 0)
    mode.matches = []
    mode._match_text_cache = {key: 'old text'}

    mode._sync_matches_for_key(key)

    assert key not in mode._match_text_cache


# search/replace event handler guards #

def test_on_search_next_ignores_a_call_with_no_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=None)))
    mode._move_match = lambda offset: pytest.fail('must not move without an open store')

    mode._on_search_next()


def test_on_search_next_moves_forward_with_a_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=object())))
    moved = []
    mode._move_match = moved.append

    mode._on_search_next()

    assert moved == [1]


def test_on_search_prev_moves_backward_with_a_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=object())))
    moved = []
    mode._move_match = moved.append

    mode._on_search_prev()

    assert moved == [-1]


def test_on_start_search_ignores_a_call_with_no_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=None)))
    mode.controller.select_mode = lambda m: pytest.fail('must not switch mode without an open store')

    mode._on_start_search(None, None, None, None)


def test_on_start_search_switches_to_search_mode_with_a_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=object())))
    selected = []
    mode.controller.select_mode = selected.append

    mode._on_start_search(None, None, None, None)

    assert selected == [mode]


def test_on_close_search_ignores_a_call_when_not_the_current_mode():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=object())
    mode.controller.select_default_mode = lambda: pytest.fail('must not switch away from another mode')

    assert mode._on_close_search() is False


def test_on_close_search_returns_to_the_default_mode():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(current_mode=mode)
    calls = []
    mode.controller.select_default_mode = lambda: calls.append(True)

    assert mode._on_close_search() is True
    assert calls == [True]


# _on_replace_clicked() #

def _replace_clicked_mode(**overrides):
    mode = SearchMode.__new__(SearchMode)
    mode.storecursor = SimpleNamespace(deref=lambda: None, move=lambda offset: None)
    mode.ent_search = SimpleNamespace(get_text=lambda: 'search')
    mode.ent_replace = SimpleNamespace(get_text=lambda: 'replacement')
    mode.chk_replace_all = SimpleNamespace(get_active=lambda: False)
    mode.matches = []
    mode.filter = SimpleNamespace(re_search=None)
    mode._cancel_search_timeout = lambda: None
    mode.update_search = lambda: None
    for name, value in overrides.items():
        setattr(mode, name, value)
    return mode


def test_on_replace_clicked_ignores_a_call_with_no_open_store():
    mode = _replace_clicked_mode(storecursor=None)
    mode._replace_all = lambda: pytest.fail('must not act without an open store')

    mode._on_replace_clicked(None)


def test_on_replace_clicked_ignores_a_call_with_no_search_text():
    mode = _replace_clicked_mode(ent_search=SimpleNamespace(get_text=lambda: ''))
    mode._replace_all = lambda: pytest.fail('must not act without search text')

    mode._on_replace_clicked(None)


def test_on_replace_clicked_ignores_a_call_with_no_replacement_text():
    mode = _replace_clicked_mode(ent_replace=SimpleNamespace(get_text=lambda: ''))
    mode._replace_all = lambda: pytest.fail('must not act without replacement text')

    mode._on_replace_clicked(None)


def test_on_replace_clicked_delegates_to_replace_all_when_checked():
    mode = _replace_clicked_mode(chk_replace_all=SimpleNamespace(get_active=lambda: True))
    calls = []
    mode._replace_all = lambda: calls.append(True)

    mode._on_replace_clicked(None)

    assert calls == [True]


def test_on_replace_clicked_replaces_the_current_unit_match_and_drops_it():
    current_unit = object()
    other_match = SimpleNamespace(unit=object(), part='target')
    current_match = SimpleNamespace(unit=current_unit, part='target')
    mode = _replace_clicked_mode(
        storecursor=SimpleNamespace(deref=lambda: current_unit),
        matches=[other_match, current_match],
    )
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(
        undo_controller=SimpleNamespace(record_start=lambda: None, record_stop=lambda: None)
    ))
    replaced = []
    mode.replace_match = lambda match, repl: replaced.append((match, repl))

    mode._on_replace_clicked(None)

    assert replaced == [(current_match, 'replacement')]
    assert mode.matches == [other_match]


def test_on_replace_clicked_advances_the_cursor_when_the_current_unit_has_no_match():
    mode = _replace_clicked_mode(filter=SimpleNamespace(re_search=re.compile('search')))
    moved = []
    mode.storecursor.move = moved.append

    mode._on_replace_clicked(None)

    assert moved == [1]


# trivial delegators #

def test_on_entry_activate_searches_and_selects_the_current_match():
    mode = SearchMode.__new__(SearchMode)
    mode.ent_search = SimpleNamespace(get_text=lambda: 'text')
    calls = []
    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = lambda: calls.append('update')
    mode._move_match = lambda offset: calls.append(('move', offset))

    mode._on_entry_activate(mode.ent_search)

    assert calls == ['cancel', 'update', ('move', 0)]


def test_on_search_clicked_moves_to_the_next_match():
    mode = SearchMode.__new__(SearchMode)
    moved = []
    mode._move_match = moved.append

    mode._on_search_clicked(None)

    assert moved == [1]


def test_on_cursor_changed_asserts_it_is_the_store_cursor_and_rehighlights():
    mode = SearchMode.__new__(SearchMode)
    cursor = object()
    mode.storecursor = cursor
    calls = []
    mode._highlight_matches = lambda: calls.append(True)

    mode._on_cursor_changed(cursor)

    assert calls == [True]


def test_refresh_proxy_researches():
    mode = SearchMode.__new__(SearchMode)
    calls = []
    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = lambda: calls.append('update')

    mode._refresh_proxy()

    assert calls == ['cancel', 'update']
