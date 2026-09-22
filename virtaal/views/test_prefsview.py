#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import pytest
from gi.repository import Gtk

from virtaal.views import baseview, prefsview
from virtaal.views.baseview import BaseView
from virtaal.views.prefsview import PreferencesView


@pytest.fixture(autouse=True)
def _fresh_builder_cache(monkeypatch):
    # _load_widgets() below loads real widgets from virtaal.ui - a
    # cached builder would hand back the very same GtkComboBoxText
    # object (and whatever it was left showing) across tests.
    monkeypatch.setattr(baseview, '_builders', {})


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
        'cmb_ui_language': gui.get_object('cmb_ui_language'),
        'scrwnd_placeables': gui.get_object('scrwnd_placeables'),
        'scrwnd_plugins': gui.get_object('scrwnd_plugins'),
    }
    return view


def test_init_language_gui_puts_system_default_first_then_the_available_languages(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_available_ui_languages',
                         lambda: [('af', 'Afrikaans'), ('fr', 'French')])
    view = _load_widgets()

    view._init_language_gui()

    ids = [row[1] for row in view._widgets['cmb_ui_language'].get_model()]
    assert ids == ['', 'af', 'fr']


def test_ui_language_property_round_trips_through_the_combo(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_available_ui_languages', lambda: [('af', 'Afrikaans')])
    view = _load_widgets()
    view._init_language_gui()

    view.ui_language = 'af'

    assert view.ui_language == 'af'


def test_ui_language_defaults_to_empty_string_when_nothing_selected(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_available_ui_languages', lambda: [])
    view = _load_widgets()
    view._init_language_gui()

    assert view.ui_language == ''


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


def _make_plugin_items(count, enabled_name=None):
    return [
        {
            'name': 'Plugin %02d' % i,
            'desc': '',
            'enabled': 'Plugin %02d' % i == enabled_name,
            'data': {'internal_name': 'plugin%02d' % i},
            'config': None,
        }
        for i in range(count)
    ]


def test_plugin_data_restores_scroll_position_after_a_rebuild(monkeypatch):
    # Restoring scroll position is deferred via GLib.idle_add() -
    # captured and called directly here rather than pumping the real
    # main loop: an unrealized treeview (no window, no allocation)
    # never finishes GTK's own idle-driven row-height revalidation,
    # hanging a real macOS CI runner for 10+ minutes before being
    # force-cancelled.
    idle_calls = []
    monkeypatch.setattr(prefsview.GLib, 'idle_add', lambda func, *args: idle_calls.append((func, args)))

    view = _load_widgets()
    view._init_plugins_page()

    view.plugin_data = _make_plugin_items(50, enabled_name='Plugin 25')
    view.plugins_select.select_item({'data': {'internal_name': 'plugin25'}})
    vadj = view.plugins_select.props.vadjustment
    vadj.set_upper(2000)
    vadj.set_value(900)

    view.plugin_data = _make_plugin_items(50, enabled_name='Plugin 25')

    # One idle_add per plugin_data assignment above - the second one
    # is the rebuild whose scroll position this test cares about.
    assert len(idle_calls) == 2
    func, args = idle_calls[-1]
    func(*args)
    assert vadj.get_value() == 900
