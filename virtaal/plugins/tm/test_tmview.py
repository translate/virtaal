#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from gi.repository import GObject, Gtk

from virtaal.plugins.tm.tmview import TMView


class _FakeTreeview:
    def __init__(self):
        self.selected = []
        self.activated = []

    def get_selection(self):
        return SimpleNamespace(select_iter=lambda itr: self.selected.append(itr))

    def row_activated(self, path, column):
        self.activated.append((path, column))


def _tmview(liststore=None, isvisible=False, active=True, may_show=True):
    view = TMView.__new__(TMView)
    view.isvisible = isvisible
    view._may_show_tmwindow = may_show
    view._should_show_tmwindow = False
    if liststore is None:
        liststore = Gtk.ListStore(GObject.TYPE_PYOBJECT, GObject.TYPE_STRING)
    view.tmwindow = SimpleNamespace(
        liststore=liststore, treeview=_FakeTreeview(), tvc_match='tvc_match',
        show_all=lambda: None, hide=lambda: None, update_geometry=lambda widget: None)
    view.mnu_suggestions = SimpleNamespace(get_active=lambda: active)
    return view


# select_match_index(): Ctrl+n shortcut navigation into the TM list

def test_select_match_index_does_nothing_when_the_window_is_not_visible():
    view = _tmview(isvisible=False)
    view.tmwindow.liststore.append([{'source': 'a'}, ''])

    view.select_match_index(1)

    assert view.tmwindow.treeview.selected == []


def test_select_match_index_ignores_a_negative_index():
    view = _tmview(isvisible=True)
    view.tmwindow.liststore.append([{'source': 'a'}, ''])

    view.select_match_index(-1)

    assert view.tmwindow.treeview.selected == []


def test_select_match_index_selects_and_activates_the_given_row():
    view = _tmview(isvisible=True)
    for source in ('first', 'second', 'third'):
        view.tmwindow.liststore.append([{'source': source}, ''])

    view.select_match_index(2)

    assert len(view.tmwindow.treeview.selected) == 1
    assert len(view.tmwindow.treeview.activated) == 1
    path, column = view.tmwindow.treeview.activated[0]
    assert column == 'tvc_match'
    itr = view.tmwindow.liststore.get_iter(path)
    assert view.tmwindow.liststore.get_value(itr, 0) == {'source': 'second'}


def test_select_match_index_does_nothing_past_the_end_of_the_list():
    view = _tmview(isvisible=True)
    view.tmwindow.liststore.append([{'source': 'only'}, ''])

    view.select_match_index(5)

    assert view.tmwindow.treeview.selected == []
    assert view.tmwindow.treeview.activated == []


# display_matches(): tooltip only names the first nine (Ctrl+1..Ctrl+9)

def test_display_matches_adds_a_shortcut_tooltip_for_the_first_nine_only():
    view = _tmview()
    shown = []
    view.show = lambda force=False: shown.append('show')
    view.update_geometry = lambda: shown.append('geometry')
    matches = [{'source': str(i)} for i in range(11)]

    view.display_matches(matches)

    tooltips = [row[1] for row in view.tmwindow.liststore]
    assert tooltips[:9] == ['Ctrl+%d' % n for n in range(1, 10)]
    assert tooltips[9:] == ['', '']
    assert shown == ['show', 'geometry']


def test_display_matches_clears_previous_matches_first():
    view = _tmview()
    view.tmwindow.liststore.append([{'source': 'stale'}, ''])
    view.show = lambda force=False: None
    view.update_geometry = lambda: None

    view.display_matches([])

    assert len(view.tmwindow.liststore) == 0


def test_display_matches_does_not_show_the_window_when_there_are_no_matches():
    view = _tmview()
    calls = []
    view.show = lambda force=False: calls.append('show')
    view.update_geometry = lambda: calls.append('geometry')

    view.display_matches([])

    assert calls == []


# show()/hide()/clear(): visibility guards

def test_show_does_nothing_when_the_suggestions_menu_item_is_inactive():
    view = _tmview(active=False)
    calls = []
    view.tmwindow.show_all = lambda: calls.append('shown')

    view.show()

    assert calls == []
    assert view.isvisible is False


def test_show_does_nothing_when_already_visible_and_not_forced():
    view = _tmview(isvisible=True)
    calls = []
    view.tmwindow.show_all = lambda: calls.append('shown')

    view.show()

    assert calls == []


def test_show_redisplays_an_already_visible_window_when_forced():
    view = _tmview(isvisible=True)
    calls = []
    view.tmwindow.show_all = lambda: calls.append('shown')

    view.show(force=True)

    assert calls == ['shown']


def test_show_does_nothing_while_shadowed_by_another_grab():
    view = _tmview(may_show=False)
    calls = []
    view.tmwindow.show_all = lambda: calls.append('shown')

    view.show()

    assert calls == []


def test_show_marks_a_blocked_match_as_pending_instead_of_dropping_it():
    view = _tmview(may_show=False)

    view.show()

    assert view._should_show_tmwindow is True


def test_show_displays_the_window_and_updates_state():
    view = _tmview()
    view._should_show_tmwindow = True
    calls = []
    view.tmwindow.show_all = lambda: calls.append('shown')

    view.show()

    assert calls == ['shown']
    assert view.isvisible is True
    assert view._should_show_tmwindow is False


def test_hide_marks_the_window_as_not_visible():
    view = _tmview(isvisible=True)
    calls = []
    view.tmwindow.hide = lambda: calls.append('hidden')

    view.hide()

    assert calls == ['hidden']
    assert view.isvisible is False


def test_clear_empties_the_matches_and_hides_the_window():
    view = _tmview(isvisible=True)
    view.tmwindow.liststore.append([{'source': 'stale'}, ''])
    hidden = []
    view.tmwindow.hide = lambda: hidden.append(1)

    view.clear()

    assert len(view.tmwindow.liststore) == 0
    assert hidden == [1]


# _on_grab_notify_mainwindow(): a same-app modal dialog (Preferences)
# shadows the main window without a focus-out event, so grab-notify is
# what actually hides/re-shows the popup around it.

def _view_for_grab_notify(should_show=False, isvisible=False, storecursor=object()):
    view = _tmview(isvisible=isvisible)
    view._should_show_tmwindow = should_show
    view.controller = SimpleNamespace(storecursor=storecursor)
    view._get_selected_unit_view = lambda: 'the-selected-view'
    return view


def test_grab_notify_regained_focus_reshows_a_pending_window():
    view = _view_for_grab_notify(should_show=True, isvisible=False)
    shown = []
    view.show = lambda: shown.append('shown')
    geometry_calls = []
    view.tmwindow.update_geometry = lambda widget: geometry_calls.append(widget)

    view._on_grab_notify_mainwindow(None, True)

    assert view._may_show_tmwindow is True
    assert shown == ['shown']
    assert geometry_calls == ['the-selected-view']


def test_grab_notify_regained_focus_skips_show_when_nothing_was_pending():
    view = _view_for_grab_notify(should_show=False, isvisible=False)
    shown = []
    view.show = lambda: shown.append('shown')

    view._on_grab_notify_mainwindow(None, True)

    assert shown == []


def test_grab_notify_regained_focus_skips_show_when_already_visible():
    view = _view_for_grab_notify(should_show=True, isvisible=True)
    shown = []
    view.show = lambda: shown.append('shown')

    view._on_grab_notify_mainwindow(None, True)

    assert shown == []


def test_grab_notify_regained_focus_skips_show_without_a_loaded_store():
    view = _view_for_grab_notify(should_show=True, isvisible=False, storecursor=None)
    shown = []
    view.show = lambda: shown.append('shown')

    view._on_grab_notify_mainwindow(None, True)

    assert shown == []


def test_grab_notify_shadowed_hides_a_visible_window_and_marks_it_pending():
    view = _view_for_grab_notify(isvisible=True)
    hidden = []
    view.hide = lambda: hidden.append('hidden')

    view._on_grab_notify_mainwindow(None, False)

    assert view._may_show_tmwindow is False
    assert hidden == ['hidden']
    assert view._should_show_tmwindow is True


def test_grab_notify_shadowed_does_nothing_when_already_hidden():
    view = _view_for_grab_notify(isvisible=False)
    hidden = []
    view.hide = lambda: hidden.append('hidden')

    view._on_grab_notify_mainwindow(None, False)

    assert hidden == []
    assert view._may_show_tmwindow is False


# _on_active_notify_mainwindow(): real WM-level focus changes (Alt+Tab
# to another app), which grab-notify never sees.

def test_active_notify_mainwindow_hides_a_visible_window_when_deactivated():
    view = _view_for_grab_notify(isvisible=True)
    hidden = []
    view.hide = lambda: hidden.append('hidden')

    view._on_active_notify_mainwindow(SimpleNamespace(props=SimpleNamespace(is_active=False)), None)

    assert view._may_show_tmwindow is False
    assert hidden == ['hidden']
    assert view._should_show_tmwindow is True


def test_active_notify_mainwindow_reshows_a_pending_window_when_activated():
    view = _view_for_grab_notify(should_show=True, isvisible=False)
    shown = []
    view.show = lambda: shown.append('shown')
    geometry_calls = []
    view.tmwindow.update_geometry = lambda widget: geometry_calls.append(widget)

    view._on_active_notify_mainwindow(SimpleNamespace(props=SimpleNamespace(is_active=True)), None)

    assert view._may_show_tmwindow is True
    assert shown == ['shown']
    assert geometry_calls == ['the-selected-view']


# _on_configure_mainwindow(): recompute geometry only for a pending
# (shadowed-but-should-show) window, not on every window move/resize.

def test_configure_mainwindow_recalculates_when_a_show_is_pending():
    # bug 1809: tvc_tm_source needs an explicit queue_resize() here or
    # its width calculation goes unbounded on the next real layout.
    view = _tmview()
    view._should_show_tmwindow = True
    view.tmwindow.tvc_tm_source = SimpleNamespace(queue_resize=lambda: calls.append('resize'))
    calls = []
    view.update_geometry = lambda: calls.append('geometry')

    view._on_configure_mainwindow(None, None)

    assert calls == ['resize', 'geometry']


def test_configure_mainwindow_does_nothing_without_a_pending_show():
    view = _tmview()
    view._should_show_tmwindow = False
    calls = []
    view.update_geometry = lambda: calls.append('geometry')

    view._on_configure_mainwindow(None, None)  # must not raise

    assert calls == []


# _on_store_view_scroll() / _on_toggle_show_tm()

def test_store_view_scroll_hides_a_visible_window():
    view = _tmview(isvisible=True)
    hidden = []
    view.hide = lambda: hidden.append(1)

    view._on_store_view_scroll()

    assert hidden == [1]


def test_store_view_scroll_does_nothing_when_already_hidden():
    view = _tmview(isvisible=False)
    hidden = []
    view.hide = lambda: hidden.append(1)

    view._on_store_view_scroll()

    assert hidden == []


def test_toggle_show_tm_hides_when_deactivated_while_visible():
    view = _tmview(isvisible=True, active=False)
    hidden = []
    view.hide = lambda: hidden.append(1)

    view._on_toggle_show_tm()

    assert hidden == [1]


def test_toggle_show_tm_starts_a_query_when_activated_while_hidden():
    view = _tmview(isvisible=False, active=True)
    view.controller = SimpleNamespace(start_query=lambda: queries.append(1))
    queries = []

    view._on_toggle_show_tm()

    assert queries == [1]


def test_toggle_show_tm_does_nothing_when_state_already_matches():
    view = _tmview(isvisible=True, active=True)
    hidden = []
    view.hide = lambda: hidden.append(1)

    view._on_toggle_show_tm()  # must not raise

    assert hidden == []


# get_target_width() / _get_selected_unit_view()

def test_get_target_width_returns_minus_one_without_a_unit_view():
    view = TMView.__new__(TMView)
    view.controller = SimpleNamespace()

    assert view.get_target_width() == -1


def test_get_target_width_reads_the_focused_targets_allocation():
    view = TMView.__new__(TMView)
    textview = SimpleNamespace(get_allocation=lambda: SimpleNamespace(width=321))
    view.controller = SimpleNamespace(unit_view=SimpleNamespace(focused_target_n=0, targets=[textview]))

    assert view.get_target_width() == 321


def test_get_selected_unit_view_returns_none_without_a_focused_unit():
    view = TMView.__new__(TMView)
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        unit_controller=SimpleNamespace(view=SimpleNamespace(focused_target_n=None, targets=[]))))

    assert view._get_selected_unit_view() is None


def test_get_selected_unit_view_returns_the_focused_target():
    view = TMView.__new__(TMView)
    target = object()
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(
        unit_controller=SimpleNamespace(view=SimpleNamespace(focused_target_n=1, targets=['first', target]))))

    assert view._get_selected_unit_view() is target
