#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk

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


def _make_view(column_width, cursor, is_resizing=False):
    column = _FakeColumn(column_width)
    calls = []
    view = SimpleNamespace(
        get_columns=lambda: [column],
        get_cursor=lambda: cursor,
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
        _restart_editing=lambda path, column: calls.append(((path, column), {'start_editing': True})),
        is_resizing=is_resizing,
        _schedule_revalidate_visible_estimated_rows=lambda: None,
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

    assert StoreTreeView._set_column_width(view, 800) is True
    StoreTreeView._on_size_allocate(view, True)

    assert column.get_fixed_width() == 798
    assert calls == [((path, editcol), {'start_editing': True})]


def test_on_size_allocate_tracks_width_but_skips_restarting_editing_mid_resize():
    # Restarting the editing cycle on every allocation during a live
    # resize drag locks the editing row's editor to a stale, wide
    # width (#3595) - the column width itself still tracks regardless.
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=1, cursor=(path, editcol), is_resizing=True)

    assert StoreTreeView._set_column_width(view, 800) is True
    StoreTreeView._on_size_allocate(view, True)

    assert column.get_fixed_width() == 798
    assert calls == []


def test_on_size_allocate_is_a_noop_when_the_width_is_unchanged():
    path, editcol = object(), object()
    view, column, calls = _make_view(column_width=798, cursor=(path, editcol))

    assert StoreTreeView._set_column_width(view, 800) is False
    StoreTreeView._on_size_allocate(view, False)

    assert calls == []


def test_on_size_allocate_does_nothing_extra_without_a_current_row():
    view, column, calls = _make_view(column_width=1, cursor=(None, None))

    StoreTreeView._set_column_width(view, 800)
    StoreTreeView._on_size_allocate(view, True)

    assert column.get_fixed_width() == 798
    assert calls == []


def test_set_column_width_does_nothing_without_a_column():
    view = SimpleNamespace(get_columns=lambda: [])

    assert StoreTreeView._set_column_width(view, 800) is False


def test_size_allocate_lays_the_column_out_at_the_new_width():
    # Otherwise, while narrowing, the column and its editor stay a step
    # wider than the view.
    treeview = _real_storetreeview()
    column = treeview.get_columns()[0]
    window = Gtk.OffscreenWindow()
    window.add(treeview)
    window.show_all()
    try:
        for width in (720, 700):
            allocation = Gdk.Rectangle()
            allocation.x, allocation.y, allocation.width, allocation.height = 0, 0, width, 100
            treeview.size_allocate(allocation)
            assert column.get_fixed_width() == width - 2
            assert column.get_width() == width
    finally:
        window.destroy()


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


def test_set_model_clears_previously_estimated_row_ids():
    view = _real_storetreeview()
    view.mark_row_estimated('stale')

    view.set_model(['unit0'])

    assert view._estimated_unit_ids == set()


def test_set_model_clears_the_cached_visible_range():
    view = _real_storetreeview()
    view.set_model(['unit0'])
    view.get_visible_range = lambda: (Gtk.TreePath((0,)), Gtk.TreePath((0,)))
    view._revalidate_visible_estimated_rows()
    assert view.get_cached_visible_range() == (0, 0)

    view.set_model(['unit0', 'unit1'])

    assert view.get_cached_visible_range() is None


# mark_row_estimated() / mark_row_measured_exactly() / _revalidate_visible_estimated_rows() #
# - the estimate/exact split's other half, StoreCellRenderer._row_needs_exact_height(),
# lives in test_storecellrenderer.py.

def test_mark_row_estimated_and_measured_exactly_track_by_unit_identity():
    view = _real_storetreeview()
    unit = object()

    view.mark_row_estimated(unit)
    assert id(unit) in view._estimated_unit_ids

    view.mark_row_measured_exactly(unit)
    assert id(unit) not in view._estimated_unit_ids


def test_revalidate_visible_estimated_rows_refreshes_the_cache_with_nothing_estimated():
    view = _real_storetreeview()
    view.set_model(['unit0'])
    view.get_visible_range = lambda: (Gtk.TreePath((0,)), Gtk.TreePath((0,)))

    view._revalidate_visible_estimated_rows()  # must not raise

    assert view.get_cached_visible_range() == (0, 0)


def test_revalidate_visible_estimated_rows_is_a_noop_without_a_model():
    view = _real_storetreeview()
    view.mark_row_estimated('x')

    view._revalidate_visible_estimated_rows()  # must not raise


def test_revalidate_visible_estimated_rows_clears_the_cache_when_the_range_is_unknown():
    view = _real_storetreeview()
    view.set_model(['unit0'])
    view.mark_row_estimated('unit0')
    view.get_visible_range = lambda: None

    view._revalidate_visible_estimated_rows()  # must not raise

    assert view.get_cached_visible_range() is None


def test_revalidate_visible_estimated_rows_forces_a_row_changed_within_the_buffer():
    view = _real_storetreeview()
    units = list(range(200))
    view.set_model(units)
    view.get_visible_range = lambda: (Gtk.TreePath((0,)), Gtk.TreePath((5,)))
    view.mark_row_estimated(units[5])  # within the buffer (up to 5 + 25)
    view.mark_row_estimated(units[150])  # far outside it

    model = view.get_model()
    changed = []
    model.row_changed = lambda path, it: changed.append(path.get_indices()[0])

    view._revalidate_visible_estimated_rows()

    assert changed == [5]


def test_vadjustment_notify_connects_scrolling_to_revalidation():
    view = _real_storetreeview()
    calls = []
    view._revalidate_visible_estimated_rows = lambda: calls.append(True)
    scrolled = Gtk.ScrolledWindow()
    scrolled.add(view)  # assigns a real vadjustment, firing notify::vadjustment

    vadjustment = view.props.vadjustment
    assert vadjustment is not None
    vadjustment.emit('value-changed')

    # Deferred via GLib.idle_add(), not run synchronously from the
    # signal handler - see _schedule_revalidate_visible_estimated_rows().
    assert calls == []
    while Gtk.events_pending():
        Gtk.main_iteration()
    assert calls == [True]


def test_schedule_revalidate_visible_estimated_rows_coalesces_repeat_calls():
    view = _real_storetreeview()
    calls = []
    view._revalidate_visible_estimated_rows = lambda: calls.append(True)

    view._schedule_revalidate_visible_estimated_rows()
    view._schedule_revalidate_visible_estimated_rows()
    view._schedule_revalidate_visible_estimated_rows()
    while Gtk.events_pending():
        Gtk.main_iteration()

    assert calls == [True]


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


def _make_move_view(cursor_move, monkeypatch, timeout_calls=None):
    if timeout_calls is not None:
        monkeypatch.setattr(GLib, 'timeout_add', lambda ms, func: timeout_calls.append((ms, func)) or 'throttle-id')
    cursor = SimpleNamespace(index=0)

    def move(offset):
        cursor_move(offset)
        cursor.index += offset
    cursor.move = move
    view = SimpleNamespace(
        view=SimpleNamespace(
            controller=SimpleNamespace(get_store=lambda: object()),
            cursor=cursor,
        ),
        _waiting_for_row_change=0,
        _pending_move_offset=0,
        _pending_move_advances=False,
        _move_throttle_id=None,
    )
    view._apply_pending_move = lambda: StoreTreeView._apply_pending_move(view)
    view._on_move_throttle = lambda: StoreTreeView._on_move_throttle(view)
    return view


def test_keyboard_move_moves_the_cursor_by_the_given_offset(monkeypatch):
    calls = []
    view = _make_move_view(calls.append, monkeypatch, timeout_calls=[])

    assert StoreTreeView._keyboard_move(view, 5) is True
    assert calls == [5]


def _make_stuck_move_view(monkeypatch):
    # The cursor can't move: at the first or last unit outside search and
    # checks, or when the navigation list has a single unit.
    view = _make_move_view(lambda offset: None, monkeypatch, timeout_calls=[])
    view.view.cursor.move = lambda offset: None
    finished = []
    view.view.controller.main_controller = SimpleNamespace(
        unit_controller=SimpleNamespace(finish_current_unit=lambda: finished.append('finish')))
    view.refresh_current_row = lambda: finished.append('refresh')
    return view, finished


def test_an_advance_landing_on_the_same_unit_finishes_and_reloads_it(monkeypatch):
    view, finished = _make_stuck_move_view(monkeypatch)

    StoreTreeView._keyboard_move(view, 1, advance=True)

    assert finished == ['finish', 'refresh']
    assert view._pending_move_advances is False


def test_a_navigation_key_that_cannot_move_does_nothing(monkeypatch):
    # Reloading the unit here made the editor jitter (#4087).
    view, finished = _make_stuck_move_view(monkeypatch)

    StoreTreeView._keyboard_move(view, 1)
    StoreTreeView._keyboard_move(view, -1)

    assert finished == []


def test_an_advance_within_a_throttled_burst_still_finishes_the_unit(monkeypatch):
    view, finished = _make_stuck_move_view(monkeypatch)
    view._move_throttle_id = 'throttle-id'  # a burst is under way

    StoreTreeView._keyboard_move(view, 1)
    StoreTreeView._keyboard_move(view, 1, advance=True)
    assert finished == []
    StoreTreeView._on_move_throttle(view)

    assert finished == ['finish', 'refresh']


def test_a_move_to_another_unit_does_not_finish_it_twice(monkeypatch):
    view = _make_move_view(lambda offset: None, monkeypatch, timeout_calls=[])
    view.view.controller.main_controller = None  # would fail if finish was attempted

    StoreTreeView._keyboard_move(view, 1)

    assert view.view.cursor.index == 1


def test_keyboard_move_throttles_repeats_within_a_burst(monkeypatch):
    # The first move of a burst applies immediately (calls == [1]) and
    # starts a throttle timer - a second move arriving before that
    # timer ticks must not apply straight away, only accumulate, so a
    # held-down nav key doesn't fire a full editing-cycle per repeat
    # (#3805).
    calls = []
    timeout_calls = []
    view = _make_move_view(calls.append, monkeypatch, timeout_calls=timeout_calls)

    StoreTreeView._keyboard_move(view, 1)
    StoreTreeView._keyboard_move(view, 1)

    assert calls == [1]
    assert view._pending_move_offset == 1
    assert view._move_throttle_id == 'throttle-id'
    assert timeout_calls[0][0] == 50


def test_on_move_throttle_applies_and_keeps_ticking_while_offset_is_pending():
    calls = []
    view = SimpleNamespace(
        _pending_move_offset=3,
        _move_throttle_id='throttle-id',
    )
    view._apply_pending_move = lambda: (calls.append(view._pending_move_offset), setattr(view, '_pending_move_offset', 0))

    assert StoreTreeView._on_move_throttle(view) is True
    assert calls == [3]


def test_on_move_throttle_stops_once_caught_up():
    view = SimpleNamespace(_pending_move_offset=0, _move_throttle_id='throttle-id')

    assert StoreTreeView._on_move_throttle(view) is False
    assert view._move_throttle_id is None


def test_move_methods_delegate_to_keyboard_move_with_the_right_offset():
    calls = []
    view = SimpleNamespace(_keyboard_move=calls.append)

    StoreTreeView._move_up(view, None, None, None, None)
    StoreTreeView._move_down(view, None, None, None, None)
    StoreTreeView._move_pgup(view, None, None, None, None)
    StoreTreeView._move_pgdown(view, None, None, None, None)

    assert calls == [-1, 1, -10, 10]


# _keyboard_jump() / _move_first() / _move_last() #

def _make_jump_view(indices, index):
    from virtaal.controllers.cursor import Cursor
    cursor = Cursor(None, indices, circular=False)
    cursor.index = index
    finished = []
    view = SimpleNamespace(
        view=SimpleNamespace(
            controller=SimpleNamespace(
                get_store=lambda: object(),
                main_controller=SimpleNamespace(
                    unit_controller=SimpleNamespace(finish_current_unit=lambda: finished.append('finish'))),
            ),
            cursor=cursor,
        ),
        _waiting_for_row_change=0,
        _pending_move_offset=0,
        _pending_move_advances=False,
        refresh_current_row=lambda: finished.append('refresh'),
    )
    return view, cursor, finished


def test_keyboard_jump_moves_to_the_ends_of_the_navigation_list():
    # In a mode like Incomplete, the ends are its first and last unit,
    # not the file's.
    view, cursor, finished = _make_jump_view([2, 5, 8], 5)

    assert StoreTreeView._keyboard_jump(view, last=True) is True
    assert cursor.index == 8
    StoreTreeView._keyboard_jump(view, last=False)
    assert cursor.index == 2
    assert finished == []


def test_keyboard_jump_to_the_unit_already_there_does_nothing():
    view, cursor, finished = _make_jump_view([2, 5, 8], 8)

    StoreTreeView._keyboard_jump(view, last=True)

    assert cursor.index == 8
    assert finished == []


def test_keyboard_jump_from_a_visited_unit():
    view, cursor, _finished = _make_jump_view([2, 5, 8], 5)
    cursor.visit(6)

    StoreTreeView._keyboard_jump(view, last=False)

    assert cursor.index == 2


def test_keyboard_jump_drops_moves_waiting_for_the_throttle():
    view, cursor, _finished = _make_jump_view([2, 5, 8], 5)
    view._pending_move_offset = 3
    view._pending_move_advances = True

    StoreTreeView._keyboard_jump(view, last=False)

    assert view._pending_move_offset == 0
    assert view._pending_move_advances is False
    assert cursor.index == 2


def test_keyboard_jump_does_nothing_without_a_store_or_units():
    view, cursor, _finished = _make_jump_view([2, 5, 8], 5)
    view.view.controller.get_store = lambda: None
    assert StoreTreeView._keyboard_jump(view, last=True) is None

    view, cursor, _finished = _make_jump_view([], 0)
    assert StoreTreeView._keyboard_jump(view, last=True) is True
    assert cursor.index == -1


def test_keyboard_jump_defers_while_a_row_change_is_pending():
    view, cursor, _finished = _make_jump_view([2, 5, 8], 5)
    view._waiting_for_row_change = 1

    assert StoreTreeView._keyboard_jump(view, last=True) is True
    assert cursor.index == 5


def test_move_first_and_last_delegate_to_keyboard_jump():
    calls = []
    view = SimpleNamespace(_keyboard_jump=lambda last: calls.append(last))

    StoreTreeView._move_first(view, None, None, None, None)
    StoreTreeView._move_last(view, None, None, None, None)

    assert calls == [False, True]


# _on_button_press() #

def test_on_button_press_ignores_clicks_outside_the_treeviews_own_window():
    view = _real_storetreeview()
    event = SimpleNamespace(window=object())  # never equals the real bin window

    assert StoreTreeView._on_button_press(view, view, event) is True


def test_on_button_press_ignores_a_click_with_no_row_underneath():
    view = _real_storetreeview()
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)

    assert StoreTreeView._on_button_press(view, view, event) is True


def test_on_button_press_visits_the_clicked_row_staying_in_the_mode():
    view = _real_storetreeview()
    view.set_model(['unit0', 'unit1'])
    view.get_model().store_index_to_path = lambda i: (i,)
    view.get_model().path_to_store_index = lambda p: p[0]
    visited = []
    view.view.cursor = SimpleNamespace(visit=visited.append)
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)
    monkeypatch_get_path_at_pos = (Gtk.TreePath((1,)), view.get_columns()[0], 0, 0)
    view.get_path_at_pos = lambda x, y: monkeypatch_get_path_at_pos
    view.get_cursor = lambda: (Gtk.TreePath((0,)), view.get_columns()[0])

    StoreTreeView._on_button_press(view, view, event)

    assert visited == [1]


def test_on_button_press_does_nothing_extra_when_the_row_is_unchanged():
    view = _real_storetreeview()
    view.set_model(['unit0'])
    visited = []
    view.view.cursor = SimpleNamespace(visit=visited.append)
    event = SimpleNamespace(window=view.get_bin_window(), x=5.0, y=5.0)
    same_path = Gtk.TreePath((0,))
    view.get_path_at_pos = lambda x, y: (same_path, view.get_columns()[0], 0, 0)
    view.get_cursor = lambda: (same_path, view.get_columns()[0])

    StoreTreeView._on_button_press(view, view, event)

    assert visited == []


# _on_cell_edited() #

def test_on_cell_edited_advances_when_told_to():
    calls = []
    view = SimpleNamespace(_keyboard_move=lambda offset, advance: calls.append((offset, advance)) or True)

    result = StoreTreeView._on_cell_edited(view, None, None, True, None, None)

    assert calls == [(1, True)]
    assert result is True


def test_on_cell_edited_stays_put_without_advancing():
    view = SimpleNamespace(_keyboard_move=lambda offset, advance: (_ for _ in ()).throw(AssertionError()))

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


def test_on_configure_settled_clears_state_and_restarts_editing():
    # Also does its own, unconditional set_cursor(start_editing=True) -
    # _on_size_allocate()'s own call was skipped throughout the drag
    # and might never fire here either (#3595).
    path, editcol = object(), object()
    calls = []
    column = _FakeColumn(798)
    view = SimpleNamespace(
        _configure_timeout_id='timer-id',
        is_resizing=True,
        queue_resize=lambda: calls.append('queue_resize'),
        get_columns=lambda: [column],
        get_cursor=lambda: (path, editcol),
        set_cursor=lambda *args, **kwargs: calls.append((args, kwargs)),
        _restart_editing=lambda path, column: calls.append(((path, column), {'start_editing': True})),
        _window_size=lambda: None,
    )

    result = StoreTreeView._on_configure_settled(view)

    assert result is False
    assert view._configure_timeout_id is None
    assert view.is_resizing is False
    assert calls == ['queue_resize', ((path, editcol), {'start_editing': True})]


def test_on_destroy_cancels_a_pending_timer(monkeypatch):
    removed = []
    monkeypatch.setattr(GLib, 'source_remove', removed.append)
    view = SimpleNamespace(_configure_timeout_id='timer-id', _move_throttle_id=None)

    StoreTreeView._on_destroy(view, None)

    assert removed == ['timer-id']
    assert view._configure_timeout_id is None


def test_on_destroy_cancels_a_pending_move_throttle_timer(monkeypatch):
    removed = []
    monkeypatch.setattr(GLib, 'source_remove', removed.append)
    view = SimpleNamespace(_configure_timeout_id=None, _move_throttle_id='timer-id')

    StoreTreeView._on_destroy(view, None)

    assert removed == ['timer-id']
    assert view._move_throttle_id is None


def test_on_destroy_does_nothing_without_a_pending_timer():
    view = SimpleNamespace(_configure_timeout_id=None, _move_throttle_id=None)

    StoreTreeView._on_destroy(view, None)  # must not raise


# _window_size() #

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


# set_visible_rows() #

def test_set_visible_rows_updates_a_small_change_in_place():
    view = _real_storetreeview()
    view.set_model(['unit%d' % i for i in range(10)])
    model = view.get_model()

    change = view.set_visible_rows([2, 3, 4])

    assert change == 'changed'
    assert view.get_model() is model
    assert model.visible_rows == [2, 3, 4]


def test_set_visible_rows_rebuilds_for_a_large_change_keeping_the_edited_unit():
    view = _real_storetreeview()
    units = ['unit%d' % i for i in range(500)]
    view.set_model(units)
    view.get_model()._current_editable = 250

    change = view.set_visible_rows([249, 250, 251])

    assert change == 'rebuilt'
    assert view.get_model().visible_rows == [249, 250, 251]
    assert view.get_model()._current_editable == 250


def test_set_visible_rows_ignores_an_unchanged_list():
    view = _real_storetreeview()
    view.set_model(['a', 'b'], rows=[1])
    model = view.get_model()

    assert view.set_visible_rows([1]) is None
    assert view.get_model() is model


def test_gtk_cursor_moves_while_rows_change_dont_move_the_store_cursor():
    view = _real_storetreeview()
    view.set_model(['unit%d' % i for i in range(10)])
    view.view.cursor = SimpleNamespace(index=5)
    view.set_cursor(Gtk.TreePath((5,)), view.get_columns()[0], False)
    view.view.cursor.index = 0  # the store cursor is elsewhere

    view.set_visible_rows([0, 1, 2])  # deletes GTK's cursor row

    assert view.view.cursor.index == 0


def test_select_index_with_force_restarts_editing_an_already_selected_row():
    view = _real_storetreeview()
    view.set_model(['a', 'b'])
    started = []
    view._start_editing_cycle = lambda model, path: started.append(str(path))
    view.get_selection().select_path(Gtk.TreePath((1,)))

    view.select_index(1)
    view.select_index(1, force=True)

    assert started == ['1']



# _restart_editing() #

def _window_with_search_box():
    view = _real_storetreeview()
    view.set_model(['unit0', 'unit1'])
    entry = Gtk.Entry()
    entry.set_text('file')
    editor = Gtk.TextView()  # stands in for the unit editor GTK focuses
    box = Gtk.Box()
    box.add(entry)
    box.add(view)
    window = Gtk.Window()
    window.add(box)
    view.set_cursor = lambda path, column, start_editing: window.set_focus(editor)
    return window, view, entry


def test_restarting_editing_after_a_resize_leaves_focus_in_the_search_box():
    # The first time Search's controls appear, the window grows on macOS.
    window, view, entry = _window_with_search_box()
    window.set_focus(entry)

    view._restart_editing(Gtk.TreePath((0,)), view.get_columns()[0])

    assert window.get_focus() is entry
    assert entry.get_selection_bounds() == ()


def test_restarting_editing_with_focus_in_the_tree_view_lets_editing_take_it():
    window, view, _entry = _window_with_search_box()
    window.set_focus(view)

    view._restart_editing(Gtk.TreePath((0,)), view.get_columns()[0])

    assert isinstance(window.get_focus(), Gtk.TextView)
