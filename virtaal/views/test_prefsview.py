#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from gi.repository import Gtk

from virtaal.views.baseview import BaseView
from virtaal.views.prefsview import PreferencesView
from virtaal.views.widgets.selectview import SelectView


def _load_widgets():
    view = PreferencesView.__new__(PreferencesView)
    gui = BaseView.load_builder_file(["virtaal", "virtaal.ui"], root='PreferencesDlg', domain="virtaal")
    view._widgets = {
        'scrwnd_placeables': gui.get_object('scrwnd_placeables'),
        'scrwnd_plugins': gui.get_object('scrwnd_plugins'),
    }
    return view


def test_plugins_page_scrolled_window_propagates_natural_width():
    # A plugin's inline "Configure..." button got clipped/hidden - a
    # ScrolledWindow doesn't request its child's actual width by
    # default, it just shrinks it instead.
    view = _load_widgets()

    view._init_plugins_page()

    assert view._widgets['scrwnd_plugins'].get_property('propagate-natural-width')


def test_placeables_page_scrolled_window_propagates_natural_width():
    view = _load_widgets()

    view._init_placeables_page()

    assert view._widgets['scrwnd_placeables'].get_property('propagate-natural-width')


def _notebook_with_pages(plugins_select, placeables_select):
    # Mirrors the real .ui shape: the plugins list is the page's direct
    # child, the placeables list sits inside a wrapping box (with an
    # intro label above it) - the lookup has to walk up to that one.
    notebook = Gtk.Notebook()
    box = Gtk.Box()
    box.add(placeables_select)
    notebook.append_page(box, Gtk.Label())
    notebook.append_page(plugins_select, Gtk.Label())
    return notebook


def test_switch_page_focuses_the_plugins_list(monkeypatch):
    # Tab/Down from the tab strip alone doesn't reliably hand the list
    # itself real keyboard focus (confirmed live) - grab it explicitly
    # once its page becomes current.
    view = PreferencesView.__new__(PreferencesView)
    view.plugins_select = SelectView()
    view.placeables_select = SelectView()
    notebook = _notebook_with_pages(view.plugins_select, view.placeables_select)
    calls = []
    monkeypatch.setattr(view.plugins_select, 'grab_focus', lambda: calls.append('plugins'))
    monkeypatch.setattr(view.placeables_select, 'grab_focus', lambda: calls.append('placeables'))

    view._on_switch_page(notebook, view.plugins_select, 1)

    assert calls == ['plugins']


def test_switch_page_focuses_the_placeables_list(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    view.plugins_select = SelectView()
    view.placeables_select = SelectView()
    notebook = _notebook_with_pages(view.plugins_select, view.placeables_select)
    calls = []
    monkeypatch.setattr(view.plugins_select, 'grab_focus', lambda: calls.append('plugins'))
    monkeypatch.setattr(view.placeables_select, 'grab_focus', lambda: calls.append('placeables'))

    view._on_switch_page(notebook, view.placeables_select.get_parent(), 0)

    assert calls == ['placeables']


def test_switch_page_ignores_an_unrelated_page(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    view.plugins_select = SelectView()
    view.placeables_select = SelectView()
    _notebook_with_pages(view.plugins_select, view.placeables_select)
    calls = []
    monkeypatch.setattr(view.plugins_select, 'grab_focus', lambda: calls.append('plugins'))
    monkeypatch.setattr(view.placeables_select, 'grab_focus', lambda: calls.append('placeables'))

    view._on_switch_page(Gtk.Notebook(), Gtk.Label(), 0)

    assert calls == []
