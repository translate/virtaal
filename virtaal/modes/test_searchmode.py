#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import re
from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk
from translate.storage import xliff

from virtaal.modes.searchmode import SearchMode
from virtaal.support.pogrep_compat import GrepFilter
from virtaal.views.theme import rgba_to_str


class _Fake:
    """A plain, hashable stand-in for a widget - unlike SimpleNamespace,
    whose own __eq__ makes it unusable as a dict key."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeTextbox(_Fake):
    """A stand-in for TextBox with a real Gtk.TextBuffer - enough for
    the highlighting/selection code, which only ever touches .buffer,
    .get_text(), .elem, .role, .props.visible and .grab_focus()."""
    def __init__(self, role, text=''):
        self.role = role
        self.buffer = Gtk.TextBuffer()
        self.buffer.set_text(text)
        self.elem = object()  # no gui_info - takes the plain-offset path
        self.props = SimpleNamespace(visible=True)

    def get_text(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)

    def grab_focus(self):
        pass


class _FakeStoreModel:
    def __init__(self, units):
        self.units = units
        self.stats = {'total': list(range(len(units)))}

    def get_units(self):
        return self.units

    def __getitem__(self, index):
        return self.units[index]


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


def test_on_search_prev_ignores_a_call_with_no_store_open():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(store_controller=SimpleNamespace(store=None)))
    mode._move_match = lambda offset: pytest.fail('must not move without an open store')

    mode._on_search_prev()


def test_replace_match_ignores_a_source_match():
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(unit_controller=None))
    match = SimpleNamespace(unit=object(), part='source')

    mode.replace_match(match, 'x')  # must not raise - must not touch match.unit


def test_replace_match_uses_the_unit_controller_when_one_is_wired_in():
    """The other branch of replace_match() (no unit_controller wired
    in) is covered by test_replace_match_updates_plural_target_string
    and test_replace_all_on_xliff_units - this is the normal,
    interactive "Replace" click path."""
    mode = SearchMode.__new__(SearchMode)
    selected = []
    set_calls = []
    unit_controller = SimpleNamespace(
        get_unit_target=lambda part_n: 'a cat sat',
        set_unit_target=lambda part_n, text: set_calls.append((part_n, text)),
    )
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(
        select_unit=selected.append, unit_controller=unit_controller))
    match = SimpleNamespace(unit=object(), part='target', part_n=0, start=2, end=5)

    mode.replace_match(match, 'dog')

    assert selected == [match.unit]
    assert set_calls == [(0, 'a dog sat')]


def test_sync_matches_for_key_updates_matchcursor_indices_when_a_match_is_dropped():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    match = SimpleNamespace(unit=unit, part='target', part_n=0, start=0, end=3,
                             get_getter=lambda: (lambda: 'dog'))
    mode.matches = [match]
    mode._match_text_cache = {(id(unit), 'target', 0): 'cat'}
    mode.matchcursor = SimpleNamespace(indices=None)

    mode._sync_matches_for_key((id(unit), 'target', 0))

    assert mode.matches == []
    assert list(mode.matchcursor.indices) == []


# selected() / unselected() #

def _selected_mode(cursor):
    mode = SearchMode.__new__(SearchMode)
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(
        store_controller=SimpleNamespace(cursor=cursor),
        unit_controller=SimpleNamespace(connect=lambda *a: 'new-sig-id', disconnect=lambda *a: None),
    ))
    mode._add_widgets = lambda: None
    mode._connect_highlighting = lambda: None
    mode._connect_textboxes = lambda: None
    mode.ent_search = Gtk.Entry()
    mode._unit_modified_id = 0
    mode._cancel_search_timeout = lambda: None
    mode.update_search = lambda: None
    return mode


def test_selected_does_nothing_without_a_store_cursor(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda *a: pytest.fail('must not touch the UI without a cursor'))
    mode = _selected_mode(cursor=None)

    mode.selected()  # must not raise


def test_selected_does_nothing_without_a_cursor_model(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda *a: pytest.fail('must not touch the UI without a cursor model'))
    mode = _selected_mode(cursor=SimpleNamespace(model=None))

    mode.selected()  # must not raise


def test_selected_shows_every_unit_when_the_search_box_is_empty(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda delay, cb: 0)
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': [0, 1, 2]}), indices=None)
    mode = _selected_mode(cursor=cursor)

    mode.selected()

    assert mode.storecursor is cursor
    assert cursor.indices == [0, 1, 2]


def test_selected_researches_when_the_search_box_already_has_text(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda delay, cb: 0)
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': []}), indices=None)
    mode = _selected_mode(cursor=cursor)
    mode.ent_search.set_text('cat')
    calls = []
    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = lambda: calls.append('update')

    mode.selected()

    assert calls == ['cancel', 'update']
    assert cursor.indices is None  # update_search() is stubbed, so it never actually ran


def test_selected_disconnects_a_previous_unit_modified_subscription(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda delay, cb: 0)
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': []}), indices=None)
    mode = _selected_mode(cursor=cursor)
    disconnected = []
    mode.controller.main_controller.unit_controller.disconnect = disconnected.append
    mode._unit_modified_id = 'old-sig-id'

    mode.selected()

    assert disconnected == ['old-sig-id']
    assert mode._unit_modified_id == 'new-sig-id'


def test_selected_schedules_a_grab_focus_that_restores_the_cursor_position(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda delay, cb: scheduled.append((delay, cb)))
    cursor = SimpleNamespace(model=SimpleNamespace(stats={'total': []}), indices=None)
    mode = _selected_mode(cursor=cursor)
    mode.ent_search.set_text('hello')
    mode.ent_search.set_position(2)

    mode.selected()

    assert len(scheduled) == 1
    delay, grab_focus = scheduled[0]
    assert delay == 100

    assert grab_focus() is False  # runs the deferred callback for real
    assert mode.ent_search.props.cursor_position == 2


def _unselected_mode():
    mode = SearchMode.__new__(SearchMode)
    mode.matches = [object()]
    mode._match_text_cache = {'k': 'v'}
    mode._unit_modified_id = 0
    return mode


def test_unselected_is_a_noop_when_nothing_was_ever_connected():
    mode = _unselected_mode()

    mode.unselected()  # must not raise

    assert mode.matches == []
    assert mode._match_text_cache == {}


def test_unselected_disconnects_the_cursor_textbox_and_unit_signals():
    mode = _unselected_mode()
    disconnected = []
    mode.storecursor = SimpleNamespace(disconnect=lambda sid: disconnected.append(('cursor', sid)))
    mode._signalid_cursor_changed = 42
    tb1 = _Fake(disconnect=lambda sid: disconnected.append(('tb1', sid)))
    tb2 = _Fake(disconnect=lambda sid: disconnected.append(('tb2', sid)))
    mode._textbox_signals = {tb1: 1, tb2: 2}
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(
        unit_controller=SimpleNamespace(disconnect=lambda sid: disconnected.append(('unit', sid)))))
    mode._unit_modified_id = 99

    mode.unselected()

    assert ('cursor', 42) in disconnected
    assert ('tb1', 1) in disconnected
    assert ('tb2', 2) in disconnected
    assert ('unit', 99) in disconnected
    assert mode._unit_modified_id == 0
    assert mode.matches == []
    assert mode._match_text_cache == {}


# select_match() #

def _select_match_mode(part, part_n, textbox):
    mode = SearchMode.__new__(SearchMode)
    selected = []
    view = SimpleNamespace(sources=[None, None], targets=[None, None])
    if part == 'target':
        view.targets[part_n] = textbox
    else:
        view.sources[part_n] = textbox
    mode.controller = SimpleNamespace(main_controller=SimpleNamespace(
        select_unit=selected.append, unit_controller=SimpleNamespace(view=view)))
    match = SimpleNamespace(unit=object(), part=part, part_n=part_n, start=2, end=5)
    return mode, match, selected


def test_select_match_returns_false_when_the_matched_textbox_is_missing(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', idle_calls.append)
    mode, match, selected = _select_match_mode('target', 0, None)

    assert mode.select_match(match) is False
    assert selected == [match.unit]
    assert idle_calls == []


def test_select_match_selects_the_matched_range_in_a_target_box(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', idle_calls.append)
    textbox = _FakeTextbox('target', 'a cat sat')
    mode, match, selected = _select_match_mode('target', 0, textbox)

    mode.select_match(match)

    assert selected == [match.unit]
    assert len(idle_calls) == 1
    idle_calls[0]()  # run the deferred selection for real

    start, end = textbox.buffer.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (2, 5)


def test_select_match_selects_the_matched_range_in_a_source_box(monkeypatch):
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', idle_calls.append)
    textbox = _FakeTextbox('source', 'a cat sat')
    mode, match, selected = _select_match_mode('source', 1, textbox)

    mode.select_match(match)
    idle_calls[0]()

    start, end = textbox.buffer.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (2, 5)


# _get_textbox_part() / _get_matches_for_textbox() #

def test_get_textbox_part_returns_role_and_index_for_source_and_target():
    mode = SearchMode.__new__(SearchMode)
    src0, src1 = _FakeTextbox('source'), _FakeTextbox('source')
    tgt0 = _FakeTextbox('target')
    mode.unitview = SimpleNamespace(sources=[src0, src1], targets=[tgt0])

    assert mode._get_textbox_part(src1) == ('source', 1)
    assert mode._get_textbox_part(tgt0) == ('target', 0)


def test_get_textbox_part_raises_for_an_unrecognised_role():
    mode = SearchMode.__new__(SearchMode)
    mode.unitview = SimpleNamespace(sources=[], targets=[])

    with pytest.raises(ValueError):
        mode._get_textbox_part(_FakeTextbox('notes'))


def test_get_matches_for_textbox_filters_by_current_unit_role_and_part_index():
    mode = SearchMode.__new__(SearchMode)
    unit, other_unit = object(), object()
    tgt0, tgt1 = _FakeTextbox('target'), _FakeTextbox('target')
    mode.unitview = SimpleNamespace(unit=unit, sources=[], targets=[tgt0, tgt1])
    m_right_box = SimpleNamespace(unit=unit, part='target', part_n=1, start=0, end=1)
    m_wrong_box = SimpleNamespace(unit=unit, part='target', part_n=0, start=0, end=1)
    m_wrong_unit = SimpleNamespace(unit=other_unit, part='target', part_n=1, start=0, end=1)
    mode.matches = [m_right_box, m_wrong_box, m_wrong_unit]

    assert mode._get_matches_for_textbox(tgt1) == [m_right_box]


# _highlight_matches() / _clear_textbox_highlight() / _make_highlight_tag() #

def test_highlight_matches_clears_highlighting_when_there_is_no_active_search():
    mode = SearchMode.__new__(SearchMode)
    mode.filter = None
    visible_tb = SimpleNamespace(props=SimpleNamespace(visible=True))
    hidden_tb = SimpleNamespace(props=SimpleNamespace(visible=False))
    mode.unitview = SimpleNamespace(sources=[visible_tb], targets=[hidden_tb])
    cleared = []
    mode._clear_textbox_highlight = cleared.append
    mode._highlight_textbox_matches = lambda tb: pytest.fail('must not highlight without an active search')

    mode._highlight_matches()

    assert cleared == [visible_tb]


def test_highlight_matches_highlights_visible_boxes_when_a_search_is_active():
    mode = SearchMode.__new__(SearchMode)
    mode.filter = SimpleNamespace(re_search=re.compile('x'))
    visible_tb = SimpleNamespace(props=SimpleNamespace(visible=True))
    hidden_tb = SimpleNamespace(props=SimpleNamespace(visible=False))
    mode.unitview = SimpleNamespace(sources=[visible_tb], targets=[hidden_tb])
    highlighted = []
    mode._highlight_textbox_matches = highlighted.append
    mode._clear_textbox_highlight = lambda tb: pytest.fail('must not clear during an active search')

    mode._highlight_matches()

    assert highlighted == [visible_tb]


def test_clear_textbox_highlight_removes_an_existing_tag():
    mode = SearchMode.__new__(SearchMode)
    textbox = _FakeTextbox('target', 'a cat sat')
    tagtable = textbox.buffer.get_tag_table()
    tagtable.add(Gtk.TextTag(name='search_highlight'))

    mode._clear_textbox_highlight(textbox)

    assert tagtable.lookup('search_highlight') is None


def test_clear_textbox_highlight_is_a_noop_without_an_existing_tag():
    mode = SearchMode.__new__(SearchMode)
    textbox = _FakeTextbox('target', 'a cat sat')

    mode._clear_textbox_highlight(textbox)  # must not raise


def test_make_highlight_tag_is_named_search_highlight():
    mode = SearchMode.__new__(SearchMode)

    tag = mode._make_highlight_tag()

    assert isinstance(tag, Gtk.TextTag)
    assert tag.get_property('name') == 'search_highlight'


# _highlight_textbox_matches() #

def test_highlight_textbox_matches_tags_each_match_and_selects_the_first_target_match():
    mode = SearchMode.__new__(SearchMode)
    mode.select_first_match = True
    unit = object()
    textbox = _FakeTextbox('target', 'a cat and a cat')
    mode.unitview = SimpleNamespace(unit=unit, sources=[], targets=[textbox])
    mode.matches = [
        SimpleNamespace(unit=unit, part='target', part_n=0, start=2, end=5),
        SimpleNamespace(unit=unit, part='target', part_n=0, start=12, end=15),
    ]

    mode._highlight_textbox_matches(textbox)

    tag = textbox.buffer.get_tag_table().lookup('search_highlight')
    assert tag is not None
    assert textbox.buffer.get_iter_at_offset(2).has_tag(tag)
    assert textbox.buffer.get_iter_at_offset(12).has_tag(tag)
    start, end = textbox.buffer.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (2, 5)


def test_highlight_textbox_matches_does_not_select_a_source_match():
    mode = SearchMode.__new__(SearchMode)
    mode.select_first_match = True
    unit = object()
    textbox = _FakeTextbox('source', 'a cat sat')
    mode.unitview = SimpleNamespace(unit=unit, sources=[textbox], targets=[])
    mode.matches = [SimpleNamespace(unit=unit, part='source', part_n=0, start=2, end=5)]

    mode._highlight_textbox_matches(textbox)

    assert textbox.buffer.get_selection_bounds() == ()


def test_highlight_textbox_matches_does_not_select_when_told_not_to():
    mode = SearchMode.__new__(SearchMode)
    mode.select_first_match = True
    unit = object()
    textbox = _FakeTextbox('target', 'a cat sat')
    mode.unitview = SimpleNamespace(unit=unit, sources=[], targets=[textbox])
    mode.matches = [SimpleNamespace(unit=unit, part='target', part_n=0, start=2, end=5)]

    mode._highlight_textbox_matches(textbox, select_match=False)

    assert textbox.buffer.get_selection_bounds() == ()


# update_search() #

def _update_search_mode(units, search_text, index=0):
    mode = SearchMode.__new__(SearchMode)
    mode.ent_search = Gtk.Entry()
    mode.ent_search.set_text(search_text)
    mode.chk_casesensitive = Gtk.CheckButton()
    mode.chk_regex = Gtk.CheckButton()
    mode.select_first_match = True
    mode.storecursor = SimpleNamespace(model=_FakeStoreModel(units), indices=None, index=index)
    mode._highlight_matches = lambda: None
    mode._search_bg_provider = None
    mode.default_base = '#ffffff'
    return mode


def test_update_search_finds_matches_and_sets_the_cursors_indices(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f: None)
    units = [_xliff_unit('a', 'a cat sat'), _xliff_unit('b', 'no match here'), _xliff_unit('c', 'the cat ran')]
    mode = _update_search_mode(units, 'cat')

    mode.update_search()

    assert mode.storecursor.indices == [0, 2]
    assert [m.unit for m in mode.matches] == [units[0], units[2]]
    assert mode.matchcursor.index == 0
    assert mode.filter.re_search is not None


def test_update_search_points_the_matchcursor_at_the_currently_selected_unit(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f: None)
    units = [_xliff_unit('a', 'cat one'), _xliff_unit('b', 'cat two'), _xliff_unit('c', 'cat three')]
    mode = _update_search_mode(units, 'cat', index=2)

    mode.update_search()

    assert mode.matchcursor.index == 2  # the matches for units 0 and 1 precede it


def test_update_search_caches_each_matchs_current_text(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f: None)
    units = [_xliff_unit('a', 'a cat sat')]
    mode = _update_search_mode(units, 'cat')

    mode.update_search()

    match = mode.matches[0]
    key = (id(match.unit), match.part, match.part_n)
    assert mode._match_text_cache[key] == match.get_getter()()


def test_update_search_falls_back_to_showing_everything_when_nothing_matches(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f: None)
    units = [_xliff_unit('a', 'dog'), _xliff_unit('b', 'fish')]
    mode = _update_search_mode(units, 'cat')

    mode.update_search()

    assert mode.matches == []
    assert mode.filter.re_search is None
    assert mode.storecursor.indices == mode.storecursor.model.stats['total']
    assert mode.ent_search.get_style_context().lookup_color('theme_base_color')  # provider was (re)installed
    assert mode._search_bg_provider is not None


def test_update_search_shows_everything_when_the_search_box_is_empty(monkeypatch):
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f: None)
    units = [_xliff_unit('a', 'dog'), _xliff_unit('b', 'fish')]
    mode = _update_search_mode(units, '')

    mode.update_search()

    assert mode.matches == []
    assert mode.storecursor.indices == mode.storecursor.model.stats['total']


def test_update_search_schedules_a_grab_focus_that_restores_the_cursor_position(monkeypatch):
    scheduled = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', scheduled.append)
    units = [_xliff_unit('a', 'a cat sat')]
    mode = _update_search_mode(units, 'cat')
    mode.ent_search.set_position(1)

    mode.update_search()

    assert len(scheduled) == 1
    assert scheduled[0]() is False  # runs the deferred callback for real
    assert mode.ent_search.props.cursor_position == 1


# event handlers not yet covered above #

def test_on_search_focus_out_records_the_cursor_position():
    mode = SearchMode.__new__(SearchMode)
    entry = SimpleNamespace(get_position=lambda: 7)

    assert mode._on_search_focus_out(entry, None) is False
    assert mode._search_cursor_pos == 7


def test_on_search_focus_in_restores_the_recorded_cursor_position(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    mode._search_cursor_pos = 4
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda f, *a: idle_calls.append((f, a)))
    positions = []
    entry = SimpleNamespace(set_position=positions.append)

    assert mode._on_search_focus_in(entry, None) is False

    assert idle_calls == [(entry.set_position, (4,))]


def test_on_search_focus_in_does_nothing_without_a_recorded_position(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    mode._search_cursor_pos = None
    idle_calls = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.idle_add', lambda *a: idle_calls.append(a))

    mode._on_search_focus_in(SimpleNamespace(set_position=lambda p: None), None)

    assert idle_calls == []


def test_on_search_text_changed_cancels_the_previous_timeout_and_schedules_a_new_one(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    mode._search_timeout = 111
    removed = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.source_remove', removed.append)
    scheduled = []
    monkeypatch.setattr('virtaal.modes.searchmode.GLib.timeout_add', lambda delay, cb: scheduled.append((delay, cb)) or 222)

    mode._on_search_text_changed(SimpleNamespace())

    assert removed == [111]
    assert scheduled == [(SearchMode.SEARCH_DELAY, mode.update_search)]
    assert mode._search_timeout == 222


def test_on_style_set_uses_the_theme_base_color_when_available(monkeypatch):
    mode = SearchMode.__new__(SearchMode)
    bg_calls = []
    mode._set_search_bg = bg_calls.append
    widget = Gtk.Entry()
    fake_rgba = Gdk.RGBA()
    fake_rgba.parse('#112233')
    style = widget.get_style_context()
    monkeypatch.setattr(style, 'lookup_color', lambda name: (True, fake_rgba))

    mode._on_style_set(widget)

    assert mode.default_base == rgba_to_str(fake_rgba)
    assert bg_calls == [mode.default_base]


# The lookup_color()-fails fallback branch (get_background_color()) is
# deliberately not exercised here - it's a pre-existing deprecated GTK3
# call with no clean replacement, shared verbatim by four other views
# (termview.py, theme.py, storeview.py, placeablesguiinfo.py); forcing
# it through the suite's known-deprecation-warnings gate is a separate,
# repo-wide cleanup, not a searchmode-specific test gap.


def test_on_textbox_refreshed_does_nothing_when_the_textbox_is_hidden():
    mode = SearchMode.__new__(SearchMode)
    mode._sync_matches_for_key = lambda key: pytest.fail('must not sync a hidden textbox')
    mode._highlight_textbox_matches = lambda tb, select_match=True: pytest.fail('must not highlight a hidden textbox')
    textbox = SimpleNamespace(props=SimpleNamespace(visible=False))

    mode._on_textbox_refreshed(textbox, elem=object())


def test_on_textbox_refreshed_does_nothing_when_the_element_is_falsy():
    mode = SearchMode.__new__(SearchMode)
    mode._sync_matches_for_key = lambda key: pytest.fail('must not sync without a rendered element')
    mode._highlight_textbox_matches = lambda tb, select_match=True: pytest.fail('must not highlight without a rendered element')
    textbox = SimpleNamespace(props=SimpleNamespace(visible=True))

    mode._on_textbox_refreshed(textbox, elem=None)


def test_on_textbox_refreshed_syncs_matches_then_rehighlights_without_reselecting():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    textbox = _FakeTextbox('target')
    mode.unitview = SimpleNamespace(unit=unit, sources=[], targets=[textbox])
    synced = []
    mode._sync_matches_for_key = synced.append
    highlighted = []
    mode._highlight_textbox_matches = lambda tb, select_match: highlighted.append((tb, select_match))

    mode._on_textbox_refreshed(textbox, elem=object())

    assert synced == [(id(unit), 'target', 0)]
    assert highlighted == [(textbox, False)]


def test_on_textbox_refreshed_skips_the_sync_without_a_current_unit():
    mode = SearchMode.__new__(SearchMode)
    textbox = _FakeTextbox('target')
    mode.unitview = SimpleNamespace(unit=None, sources=[], targets=[textbox])
    synced = []
    mode._sync_matches_for_key = synced.append
    highlighted = []
    mode._highlight_textbox_matches = lambda tb, select_match: highlighted.append((tb, select_match))

    mode._on_textbox_refreshed(textbox, elem=object())

    assert synced == []
    assert highlighted == [(textbox, False)]


def test_on_textbox_refreshed_skips_the_sync_when_the_textbox_role_cannot_be_determined():
    mode = SearchMode.__new__(SearchMode)
    unit = object()
    textbox = _FakeTextbox('notes')
    mode.unitview = SimpleNamespace(unit=unit, sources=[], targets=[])
    synced = []
    mode._sync_matches_for_key = synced.append
    mode._highlight_textbox_matches = lambda tb, select_match: None

    mode._on_textbox_refreshed(textbox, elem=object())

    assert synced == []


# _connect_highlighting() / _connect_textboxes() #

def test_connect_highlighting_subscribes_to_cursor_changed():
    mode = SearchMode.__new__(SearchMode)
    connected = []

    def fake_connect(signal, handler):
        connected.append((signal, handler))
        return 'sigid'
    mode.storecursor = SimpleNamespace(connect=fake_connect)

    mode._connect_highlighting()

    assert connected == [('cursor-changed', mode._on_cursor_changed)]
    assert mode._signalid_cursor_changed == 'sigid'


def test_connect_textboxes_subscribes_every_source_and_target_to_refreshed():
    mode = SearchMode.__new__(SearchMode)
    calls = []

    def make_box(tag):
        def fake_connect(signal, handler, tag=tag):
            calls.append((tag, signal, handler))
            return tag
        return _Fake(connect=fake_connect)
    src, tgt = make_box('src'), make_box('tgt')
    mode.unitview = SimpleNamespace(sources=[src], targets=[tgt])

    mode._connect_textboxes()

    assert calls == [('src', 'refreshed', mode._on_textbox_refreshed), ('tgt', 'refreshed', mode._on_textbox_refreshed)]
    assert mode._textbox_signals == {src: 'src', tgt: 'tgt'}


# __init__() / _create_widgets() / _setup_key_bindings() #

def _real_controller():
    return SimpleNamespace(
        main_controller=SimpleNamespace(
            unit_controller=SimpleNamespace(view=SimpleNamespace(sources=[], targets=[])),
            view=Gtk.Window(),
        )
    )


def test_init_builds_the_expected_widgets_and_initial_state():
    mode = SearchMode(_real_controller())

    assert [type(w) for w in mode.widgets] == [
        Gtk.Entry, Gtk.Button, Gtk.CheckButton, Gtk.CheckButton,
        Gtk.Label, Gtk.Entry, Gtk.Button, Gtk.CheckButton,
    ]
    assert mode.filter is None
    assert mode.matches == []
    assert mode.select_first_match is True
    assert mode._search_timeout == 0
    assert mode._unit_modified_id == 0
    assert mode._match_text_cache == {}
    assert mode._search_bg_provider is None


def test_init_registers_the_search_accelerators_and_accel_group(monkeypatch):
    registered_paths = []
    monkeypatch.setattr(Gtk.AccelMap, 'add_entry', lambda path, key, mods: registered_paths.append(path))
    controller = _real_controller()

    mode = SearchMode(controller)

    assert registered_paths == [
        "<Virtaal>/Edit/Search",
        "<Virtaal>/Edit/Search Ctrl+F",
        "<Virtaal>/Edit/Search: Next",
        "<Virtaal>/Edit/Search: Previous",
        "<Virtaal>/Edit/Search: Close",
    ]
    assert list(Gtk.accel_groups_from_object(controller.main_controller.view)) == [mode.accel_group]


def test_create_widgets_wires_the_case_and_regex_toggles_to_refresh_proxy():
    mode = SearchMode(_real_controller())
    calls = []
    mode._cancel_search_timeout = lambda: calls.append('cancel')
    mode.update_search = lambda: calls.append('update')

    mode.chk_casesensitive.set_active(True)
    assert calls == ['cancel', 'update']

    calls.clear()
    mode.chk_regex.set_active(True)
    assert calls == ['cancel', 'update']
