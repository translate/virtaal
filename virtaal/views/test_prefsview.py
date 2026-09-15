#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views import prefsview
from virtaal.views.prefsview import PreferencesView


class _FakeSelectView:
    def select_item(self, item):
        pass


def test_run_restores_the_parents_focus_on_close(monkeypatch):
    monkeypatch.setattr(prefsview.GLib, 'idle_add', lambda func, *args: func(*args))
    view = PreferencesView.__new__(PreferencesView)
    parent = Gtk.Window()
    dialog = Gtk.Dialog()
    dialog.set_transient_for(parent)
    view._widgets = {'dialog': dialog}
    view.placeables_select = _FakeSelectView()
    view.plugins_select = _FakeSelectView()
    view.controller = type('_FakeController', (), {'update_prefs_gui_data': lambda self: None})()
    view.emit = lambda *args: None
    calls = []
    monkeypatch.setattr(dialog, 'run', lambda: Gtk.ResponseType.CLOSE)
    monkeypatch.setattr(parent, 'present', lambda: calls.append('parent'))

    view.show()

    assert calls == ['parent']
