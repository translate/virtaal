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


# display_matches(): tooltip only names the first nine (Ctrl+1..Ctrl+9)
# - only that many accelerators actually exist (_setup_key_bindings()).

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
