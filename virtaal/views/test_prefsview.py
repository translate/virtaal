#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views import prefsview
from virtaal.views.baseview import BaseView
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


def _load_widgets():
    view = PreferencesView.__new__(PreferencesView)
    gui = BaseView.load_builder_file(["virtaal", "virtaal.ui"], root='PreferencesDlg', domain="virtaal")
    view._widgets = {
        'scrwnd_placeables': gui.get_object('scrwnd_placeables'),
        'scrwnd_plugins': gui.get_object('scrwnd_plugins'),
    }
    return view


def test_plugins_page_scrolled_window_propagates_natural_width():
    view = _load_widgets()

    view._init_plugins_page()

    assert view._widgets['scrwnd_plugins'].get_property('propagate-natural-width')


def test_placeables_page_scrolled_window_propagates_natural_width():
    view = _load_widgets()

    view._init_placeables_page()

    assert view._widgets['scrwnd_placeables'].get_property('propagate-natural-width')


def test_plugins_page_scrolled_window_is_not_focusable():
    # The .ui file marks it focusable, which swallows Tab/Down meant
    # for the list inside it.
    view = _load_widgets()

    view._init_plugins_page()

    assert not view._widgets['scrwnd_plugins'].get_can_focus()


def test_placeables_page_scrolled_window_is_not_focusable():
    view = _load_widgets()

    view._init_placeables_page()

    assert not view._widgets['scrwnd_placeables'].get_can_focus()
