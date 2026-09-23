#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import logging
from types import SimpleNamespace

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

from virtaal.views.widgets.storetreemodel import StoreTreeModel
from virtaal.views.widgets.storetreeview import StoreTreeView


def _real_storetreeview():
    """A real StoreTreeView, built the same way the app does - the menu
    accelerator wiring in _install_callbacks() needs a real Gtk.Builder
    with the real menu items it looks up."""
    builder = Gtk.Builder()
    builder.add_from_file('share/virtaal/virtaal.ui')
    mainview = SimpleNamespace(gui=builder)
    fake_view = SimpleNamespace(controller=SimpleNamespace(main_controller=SimpleNamespace(view=mainview)))
    return StoreTreeView(fake_view)


class _FakeColumn:
    def __init__(self, width):
        self._width = width

    def get_fixed_width(self):
        return self._width

    def set_fixed_width(self, width):
        self._width = width


def _make_view(column_width, cursor):
    column = _FakeColumn(column_width)
    calls = []
    view = SimpleNamespace(
        get_columns=lambda: [column],
        get_cursor=lambda: cursor,
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    return view, column, calls


def test_on_size_allocate_restarts_editing_the_current_row_when_the_width_changes():
    # A FIXED column doesn't renegotiate row heights on its own when
    # its width changes - most visible on the very first allocation,
    # where the toplevel isn't realized yet and do_get_size() measures
    # the current row against a bogus ~1px width (#3526). Confirmed
    # live: queue_resize() alone didn't fix it, re-running the same
    # start_editing cursor cycle select_index() uses on a manual
    # navigation does.
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=1, cursor=(path, editcol))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert column.get_fixed_width() == 798
    assert calls == [((path, editcol), {'start_editing': True})]


def test_on_size_allocate_is_a_noop_when_the_width_is_unchanged():
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=798, cursor=(path, editcol))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert calls == []


def test_on_size_allocate_does_nothing_extra_without_a_current_row():
    view, column, calls = _make_view(column_width=1, cursor=(None, None))
    allocation = SimpleNamespace(width=800)

    StoreTreeView._on_size_allocate(view, None, allocation)

    assert column.get_fixed_width() == 798
    assert calls == []


def test_on_size_allocate_does_nothing_without_a_column():
    view = SimpleNamespace(get_columns=lambda: [])

    StoreTreeView._on_size_allocate(view, None, SimpleNamespace(width=800))  # must not raise


def test_refresh_current_row_redoes_the_editing_cycle_in_place():
    # A one-shot set_cursor(start_editing=True) restarted editing but
    # left the row's terminology highlighting unrendered - select_index()
    # only ever gets the highlighting right by also calling
    # set_editable() and repeating set_cursor() once more on idle
    # (#3240). refresh_current_row() drives that same full cycle for
    # the already-current row, which select_index() itself skips.
    model = StoreTreeModel(['unit0'])
    path = Gtk.TreePath((0,))
    column = _FakeColumn(1)
    calls = []
    view = SimpleNamespace(
        get_model=lambda: model,
        get_columns=lambda: [column],
        get_cursor=lambda: (path, column),
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
        _waiting_for_row_change=0,
    )
    view._start_editing_cycle = lambda *a, **kw: StoreTreeView._start_editing_cycle(view, *a, **kw)

    StoreTreeView.refresh_current_row(view)

    assert calls == [((path, column), {'start_editing': True})]
    assert view._waiting_for_row_change == 1


def test_refresh_current_row_does_nothing_without_a_current_row():
    model = StoreTreeModel([])
    calls = []
    view = SimpleNamespace(
        get_model=lambda: model,
        get_cursor=lambda: (None, None),
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    StoreTreeView.refresh_current_row(view)

    assert calls == []


def test_refresh_current_row_does_nothing_without_a_valid_model():
    view = SimpleNamespace(get_model=lambda: None)

    StoreTreeView.refresh_current_row(view)  # must not raise


# reset_column_width() #

def test_reset_column_width_relaxes_a_fixed_width():
    column = _FakeColumn(500)
    view = SimpleNamespace(get_columns=lambda: [column])

    StoreTreeView.reset_column_width(view)

    assert column.get_fixed_width() == 1


def test_reset_column_width_does_nothing_without_a_column():
    view = SimpleNamespace(get_columns=lambda: [])

    StoreTreeView.reset_column_width(view)  # must not raise


# select_index() #

def test_select_index_does_nothing_without_a_valid_model():
    view = SimpleNamespace(get_model=lambda: None)

    StoreTreeView.select_index(view, 0)  # must not raise


# _start_editing_cycle()'s deferred change_cursor() #

def test_start_editing_cycle_reruns_set_cursor_on_idle_for_the_same_model(monkeypatch):
    model = StoreTreeModel(['unit0'])
    path = Gtk.TreePath((0,))
    column = _FakeColumn(1)
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, **kw: idle_calls.append(func))
    calls = []
    view = SimpleNamespace(
        get_columns=lambda: [column],
        get_model=lambda: model,
        set_cursor=lambda *a, **kw: calls.append((a, kw)),
        _waiting_for_row_change=0,
    )

    StoreTreeView._start_editing_cycle(view, model, path)
    [change_cursor] = idle_calls
    change_cursor()

    assert view._waiting_for_row_change == 0
    assert calls == [((path, column), {'start_editing': True})] * 2


def test_start_editing_cycle_skips_the_deferred_set_cursor_for_a_stale_model(monkeypatch):
    model = StoreTreeModel(['unit0'])
    other_model = StoreTreeModel(['unit0'])
    path = Gtk.TreePath((0,))
    column = _FakeColumn(1)
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func, **kw: idle_calls.append(func))
    calls = []
    view = SimpleNamespace(
        get_columns=lambda: [column],
        get_model=lambda: other_model,  # a different file's model is now current
        set_cursor=lambda *a, **kw: calls.append((a, kw)),
        _waiting_for_row_change=0,
    )

    StoreTreeView._start_editing_cycle(view, model, path)
    [change_cursor] = idle_calls
    change_cursor()

    assert view._waiting_for_row_change == 0
    assert calls == [((path, column), {'start_editing': True})]  # only the immediate one


# set_model() #

def test_set_model_wraps_a_real_storemodel():
    view = _real_storetreeview()

    view.set_model(['unit0'])

    assert isinstance(view.get_model(), StoreTreeModel)


def test_set_model_clears_with_a_falsy_storemodel():
    view = _real_storetreeview()
    view.set_model(['unit0'])

    view.set_model(None)

    assert view.get_model() is None


# _keyboard_move() / _move_*() #

def test_keyboard_move_does_nothing_without_a_store():
    view = SimpleNamespace(view=SimpleNamespace(controller=SimpleNamespace(get_store=lambda: None)))

    assert StoreTreeView._keyboard_move(view, 1) is None


def test_keyboard_move_defers_while_a_row_change_is_pending():
    view = SimpleNamespace(
        view=SimpleNamespace(controller=SimpleNamespace(get_store=lambda: object())),
        _waiting_for_row_change=1,
    )

    assert StoreTreeView._keyboard_move(view, 1) is True


def test_keyboard_move_moves_the_cursor_by_the_given_offset():
    calls = []
    view = SimpleNamespace(
        view=SimpleNamespace(
            controller=SimpleNamespace(get_store=lambda: object()),
            cursor=SimpleNamespace(move=calls.append),
        ),
        _waiting_for_row_change=0,
    )

    assert StoreTreeView._keyboard_move(view, 5) is True
    assert calls == [5]


def test_keyboard_move_tolerates_an_out_of_range_move():
    def _raise(offset):
        raise IndexError()
    view = SimpleNamespace(
        view=SimpleNamespace(
            controller=SimpleNamespace(get_store=lambda: object()),
            cursor=SimpleNamespace(move=_raise),
        ),
        _waiting_for_row_change=0,
    )

    assert StoreTreeView._keyboard_move(view, 1) is True


def test_move_methods_delegate_to_keyboard_move_with_the_right_offset():
    calls = []
    view = SimpleNamespace(_keyboard_move=calls.append)

    StoreTreeView._move_up(view, None, None, None, None)
    StoreTreeView._move_down(view, None, None, None, None)
    StoreTreeView._move_pgup(view, None, None, None, None)
    StoreTreeView._move_pgdown(view, None, None, None, None)

    assert calls == [-1, 1, -10, 10]


# _on_button_press() #

def test_on_button_press_ignores_clicks_outside_the_treeviews_own_window():
    view = _real_storetreeview()
    event = SimpleNamespace(window=object())  # never equals the real bin window

    assert StoreTreeView._on_button_press(view, view, event) is True


def test_on_button_press_ignores_a_click_with_no_row_underneath():
    view = _real_storetreeview()
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)

    assert StoreTreeView._on_button_press(view, view, event) is True


def test_on_button_press_selects_the_clicked_row_and_switches_to_default_mode():
    view = _real_storetreeview()
    view.set_model(['unit0', 'unit1'])
    view.get_model().store_index_to_path = lambda i: (i,)
    view.get_model().path_to_store_index = lambda p: p[0]
    calls = []
    view.view.cursor = SimpleNamespace(indices=[], index=None)
    view.view.controller.main_controller.mode_controller = SimpleNamespace(
        select_default_mode=lambda: calls.append('default-mode'))
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)
    monkeypatch_get_path_at_pos = (Gtk.TreePath((1,)), view.get_columns()[0], 0, 0)
    view.get_path_at_pos = lambda x, y: monkeypatch_get_path_at_pos
    view.get_cursor = lambda: (Gtk.TreePath((0,)), view.get_columns()[0])

    StoreTreeView._on_button_press(view, view, event)

    assert calls == ['default-mode']
    assert view.view.cursor.index == 1


def test_on_button_press_does_nothing_extra_when_the_row_is_unchanged():
    view = _real_storetreeview()
    view.set_model(['unit0'])
    calls = []
    view.view.cursor = SimpleNamespace(indices=[], index=None)
    view.view.controller.main_controller.mode_controller = SimpleNamespace(
        select_default_mode=lambda: calls.append('default-mode'))
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)
    same_path = Gtk.TreePath((0,))
    view.get_path_at_pos = lambda x, y: (same_path, view.get_columns()[0], 0, 0)
    view.get_cursor = lambda: (same_path, view.get_columns()[0])

    StoreTreeView._on_button_press(view, view, event)

    assert calls == []


# _on_cell_edited() #

def test_on_cell_edited_advances_when_told_to():
    calls = []
    view = SimpleNamespace(_keyboard_move=lambda offset: calls.append(offset) or True)

    result = StoreTreeView._on_cell_edited(view, None, None, True, None, None)

    assert calls == [1]
    assert result is True


def test_on_cell_edited_stays_put_without_advancing():
    view = SimpleNamespace(_keyboard_move=lambda offset: (_ for _ in ()).throw(AssertionError()))

    assert StoreTreeView._on_cell_edited(view, None, None, False, None, None) is True


# on_configure_event() / _on_configure_settled() / _on_destroy() #

def test_on_configure_event_starts_a_debounce_timer(monkeypatch):
    timeout_calls = []
    monkeypatch.setattr(GLib, 'timeout_add', lambda ms, func: timeout_calls.append((ms, func)) or 'timer-id')
    view = SimpleNamespace(_configure_timeout_id=None, is_resizing=False, _on_configure_settled=lambda: None)

    result = StoreTreeView.on_configure_event(view, None, SimpleNamespace(width=100, height=100))

    assert result is False
    assert view.is_resizing is True
    assert view._configure_timeout_id == 'timer-id'
    assert timeout_calls[0][0] == 200


def test_on_configure_event_cancels_a_previous_pending_timer(monkeypatch):
    removed = []
    monkeypatch.setattr(GLib, 'source_remove', removed.append)
    monkeypatch.setattr(GLib, 'timeout_add', lambda ms, func: 'new-timer-id')
    view = SimpleNamespace(_configure_timeout_id='old-timer-id', is_resizing=False, _on_configure_settled=lambda: None)

    StoreTreeView.on_configure_event(view, None, SimpleNamespace(width=100, height=100))

    assert removed == ['old-timer-id']
    assert view._configure_timeout_id == 'new-timer-id'


def test_on_configure_settled_clears_state_and_restores_the_cursor():
    calls = []
    view = SimpleNamespace(
        _configure_timeout_id='timer-id',
        is_resizing=True,
        queue_resize=lambda: calls.append('queue_resize'),
        _restore_cursor=lambda: calls.append('restore_cursor'),
        _window_size=lambda: None,
    )

    result = StoreTreeView._on_configure_settled(view)

    assert result is False
    assert view._configure_timeout_id is None
    assert view.is_resizing is False
    assert calls == ['queue_resize', 'restore_cursor']


def test_on_destroy_cancels_a_pending_timer(monkeypatch):
    removed = []
    monkeypatch.setattr(GLib, 'source_remove', removed.append)
    view = SimpleNamespace(_configure_timeout_id='timer-id')

    StoreTreeView._on_destroy(view, None)

    assert removed == ['timer-id']
    assert view._configure_timeout_id is None


def test_on_destroy_does_nothing_without_a_pending_timer():
    view = SimpleNamespace(_configure_timeout_id=None)

    StoreTreeView._on_destroy(view, None)  # must not raise


# _on_focus_in() #

def test_on_focus_in_restores_the_cursor():
    calls = []
    view = SimpleNamespace(_restore_cursor=lambda: calls.append(True))

    result = StoreTreeView._on_focus_in(view, None, None)

    assert result is False
    assert calls == [True]


# _window_size() / _restore_cursor() #

def test_window_size_returns_none_without_a_toplevel():
    view = SimpleNamespace(get_toplevel=lambda: None)

    assert StoreTreeView._window_size(view) is None


def test_window_size_returns_none_for_an_unrealized_window():
    window = Gtk.Window()
    view = SimpleNamespace(get_toplevel=lambda: window)

    assert StoreTreeView._window_size(view) is None


def test_window_size_returns_the_real_size_for_a_realized_window():
    window = Gtk.Window()
    window.realize()
    view = SimpleNamespace(get_toplevel=lambda: window)

    size = StoreTreeView._window_size(view)

    assert size is not None


def test_restore_cursor_warns_on_an_unexpectedly_wide_window(caplog):
    view = SimpleNamespace(_window_size=lambda: (2000, 100))

    with caplog.at_level(logging.WARNING):
        StoreTreeView._restore_cursor(view)

    assert any('window width' in r.message for r in caplog.records)


def test_restore_cursor_is_quiet_for_a_normal_width(caplog):
    view = SimpleNamespace(_window_size=lambda: (800, 100))

    with caplog.at_level(logging.WARNING):
        StoreTreeView._restore_cursor(view)

    assert caplog.records == []


# _on_cursor_changed() #

def test_on_cursor_changed_returns_true_without_a_model():
    treeview = SimpleNamespace(get_model=lambda: None)
    view = SimpleNamespace(get_cursor=lambda: (None, None))

    assert StoreTreeView._on_cursor_changed(view, treeview) is True


def test_on_cursor_changed_updates_the_view_cursor_and_schedules_a_scroll(monkeypatch):
    model = StoreTreeModel(['unit0', 'unit1'])
    path = Gtk.TreePath((1,))
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func: idle_calls.append(func))
    view = SimpleNamespace(
        get_cursor=lambda: (path, None),
        get_model=lambda: model,
        view=SimpleNamespace(cursor=SimpleNamespace(index=0)),
    )

    StoreTreeView._on_cursor_changed(view, view)

    assert view.view.cursor.index == 1
    assert len(idle_calls) == 1


def test_on_cursor_changed_do_scroll_scrolls_to_the_still_current_cursor(monkeypatch):
    model = StoreTreeModel(['unit0'])
    path = Gtk.TreePath((0,))
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func: idle_calls.append(func))
    scroll_calls = []
    column = object()
    view = SimpleNamespace(
        get_cursor=lambda: (path, None),
        get_model=lambda: model,
        get_column=lambda i: column,
        scroll_to_cell=lambda *a: scroll_calls.append(a),
        view=SimpleNamespace(cursor=SimpleNamespace(index=0)),
    )

    StoreTreeView._on_cursor_changed(view, view)
    [do_scroll] = idle_calls
    result = do_scroll()

    assert result is False
    assert scroll_calls == [(path, column, True, 0.5, 0.0)]


def test_on_cursor_changed_do_scroll_gives_up_if_the_cursor_became_invalid(monkeypatch):
    model = StoreTreeModel(['unit0'])
    idle_calls = []
    monkeypatch.setattr(GLib, 'idle_add', lambda func: idle_calls.append(func))
    scroll_calls = []
    view = SimpleNamespace(
        get_cursor=lambda: (None, None),  # invalid by the time do_scroll runs
        get_model=lambda: model,
        scroll_to_cell=lambda *a: scroll_calls.append(a),
        view=SimpleNamespace(cursor=SimpleNamespace(index=0)),
    )

    StoreTreeView._on_cursor_changed(view, view)
    [do_scroll] = idle_calls

    result = do_scroll()

    assert result is False
    assert scroll_calls == []


# _on_key_press() / _on_modified() #

def test_on_key_press_always_swallows_the_event():
    assert StoreTreeView._on_key_press(SimpleNamespace(), None, None) is True


def test_on_modified_emits_the_modified_signal():
    calls = []
    view = SimpleNamespace(emit=lambda name: calls.append(name))

    result = StoreTreeView._on_modified(view, None)

    assert result is True
    assert calls == ['modified']
