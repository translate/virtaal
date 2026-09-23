#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest
from gi.repository import Gdk, Gtk

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


class _FakeGui:
    def __init__(self, objects):
        self._objects = objects

    def get_object(self, name):
        return self._objects[name]


class _FakeMainView:
    def __init__(self, gui, main_window=None):
        self.gui = gui
        self.main_window = main_window
        self.accel_groups_added = []
        self.synced = 0

    def add_accel_group(self, group):
        self.accel_groups_added.append(group)

    def sync_menubar(self):
        self.synced += 1


def test_setup_key_bindings_registers_the_accelerator(monkeypatch):
    # Asserting against the real (global, process-wide) Gtk.AccelMap here
    # is order-dependent - other tests/production code touch the same
    # entry - so check the call instead of the resulting global state.
    calls = []
    monkeypatch.setattr(prefsview.Gtk.AccelMap, 'add_entry', lambda *a: calls.append(a))
    view = PreferencesView.__new__(PreferencesView)

    view._setup_key_bindings()

    assert calls == [("<Virtaal>/Edit/Preferences", Gdk.KEY_comma, Gdk.ModifierType.CONTROL_MASK)]


def test_setup_menu_item_creates_an_accel_group_when_none_exists(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    menu_edit = Gtk.Menu()
    mnu_prefs = Gtk.MenuItem()
    mainview = _FakeMainView(_FakeGui({'menu_edit': menu_edit, 'mnu_prefs': mnu_prefs}))
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(view=mainview))
    calls = []
    monkeypatch.setattr(view, '_show_preferences', lambda *a: calls.append(a))

    view._setup_menu_item()

    assert mnu_prefs.get_accel_path() == "<Virtaal>/Edit/Preferences"
    assert menu_edit.get_accel_group() is not None
    assert mainview.accel_groups_added == [menu_edit.get_accel_group()]
    assert mainview.synced == 1
    mnu_prefs.emit('activate')
    assert calls == [(mnu_prefs,)]


def test_setup_menu_item_reuses_an_existing_accel_group():
    view = PreferencesView.__new__(PreferencesView)
    menu_edit = Gtk.Menu()
    existing_group = Gtk.AccelGroup()
    menu_edit.set_accel_group(existing_group)
    mnu_prefs = Gtk.MenuItem()
    mainview = _FakeMainView(_FakeGui({'menu_edit': menu_edit, 'mnu_prefs': mnu_prefs}))
    view.controller = SimpleNamespace(main_controller=SimpleNamespace(view=mainview))

    view._setup_menu_item()

    assert menu_edit.get_accel_group() is existing_group
    assert mainview.accel_groups_added == []


def test_init_sets_up_widgets_dict_and_bindings():
    menu_edit = Gtk.Menu()
    mnu_prefs = Gtk.MenuItem()
    mainview = _FakeMainView(_FakeGui({'menu_edit': menu_edit, 'mnu_prefs': mnu_prefs}))
    controller = SimpleNamespace(main_controller=SimpleNamespace(view=mainview))

    view = PreferencesView(controller)

    assert view.controller is controller
    assert view._widgets == {}
    assert mnu_prefs.get_accel_path() == "<Virtaal>/Edit/Preferences"


def _load_full_view(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_available_ui_languages', lambda: [])
    view = PreferencesView.__new__(PreferencesView)
    main_window = Gtk.Window()
    view.controller = SimpleNamespace(
        main_controller=SimpleNamespace(view=SimpleNamespace(main_window=main_window)),
    )
    view._widgets = {}
    view._init_gui()
    return view


def test_get_widgets_makes_the_dialog_transient_for_the_main_window(monkeypatch):
    view = _load_full_view(monkeypatch)

    assert view._widgets['dialog'].get_transient_for() is view.controller.main_controller.view.main_window


def test_init_gui_wires_the_default_fonts_button(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_default_font', lambda: 'Sans 10')
    view = _load_full_view(monkeypatch)
    view._widgets['fbtn_source'].set_font('Serif 20')
    view._widgets['fbtn_target'].set_font('Serif 20')

    view._widgets['btn_default_fonts'].emit('clicked')

    assert view._widgets['fbtn_source'].get_font() == 'Sans 10'
    assert view._widgets['fbtn_target'].get_font() == 'Sans 10'


def test_on_font_button_clicked_presents_the_open_font_dialog_and_restores_focus(monkeypatch):
    idle_calls = []
    monkeypatch.setattr(prefsview.GLib, 'idle_add', lambda func, *args: idle_calls.append((func, args)))
    view = _load_full_view(monkeypatch)
    prefs_dialog = view._widgets['dialog']
    prefs_dialog.show()
    font_dialog = Gtk.Dialog(transient_for=prefs_dialog)
    font_dialog.show()
    presented = []
    monkeypatch.setattr(font_dialog, 'present', lambda: presented.append(True))

    view._on_font_button_clicked(view._widgets['fbtn_source'])
    # _on_font_button_clicked runs its work via GLib.idle_add - fire it now.
    func, args = idle_calls[-1]
    func(*args)

    assert presented == [True]
    hide_calls = []
    monkeypatch.setattr(prefs_dialog, 'present', lambda: hide_calls.append(True))
    font_dialog.emit('hide')
    hide_func, hide_args = idle_calls[-1]
    hide_func(*hide_args)
    assert hide_calls == [True]


def test_font_data_round_trips_through_the_font_buttons(monkeypatch):
    view = _load_full_view(monkeypatch)

    view.font_data = {'source': 'Sans 10', 'target': 'Serif 12'}

    assert view.font_data == {'source': 'Sans 10', 'target': 'Serif 12'}


def test_font_data_setter_rejects_a_non_dict_value(monkeypatch):
    view = _load_full_view(monkeypatch)

    with pytest.raises(ValueError):
        view.font_data = 'not a dict'


def test_placeables_data_returns_the_select_views_items(monkeypatch):
    view = _load_full_view(monkeypatch)

    assert view.placeables_data == []


def test_placeables_data_restores_scroll_position_after_a_rebuild(monkeypatch):
    idle_calls = []
    monkeypatch.setattr(prefsview.GLib, 'idle_add', lambda func, *args: idle_calls.append((func, args)))
    view = _load_full_view(monkeypatch)

    view.placeables_data = _make_plugin_items(50, enabled_name='Plugin 25')
    view.placeables_select.select_item({'data': {'internal_name': 'plugin25'}})
    vadj = view.placeables_select.props.vadjustment
    vadj.set_upper(2000)
    vadj.set_value(900)

    view.placeables_data = _make_plugin_items(50, enabled_name='Plugin 25')

    func, args = idle_calls[-1]
    func(*args)
    assert vadj.get_value() == 900


def test_plugin_data_returns_the_select_views_items(monkeypatch):
    view = _load_full_view(monkeypatch)

    assert view.plugin_data == []


def test_user_data_round_trips_through_the_entries(monkeypatch):
    view = _load_full_view(monkeypatch)

    view.user_data = {'name': 'Jane', 'email': 'jane@example.com', 'team': 'af'}

    assert view.user_data == {'name': 'Jane', 'email': 'jane@example.com', 'team': 'af'}


def test_user_data_setter_only_updates_the_given_keys(monkeypatch):
    view = _load_full_view(monkeypatch)
    view.user_data = {'name': 'Jane', 'email': 'jane@example.com', 'team': 'af'}

    view.user_data = {'name': 'Joe'}

    assert view.user_data == {'name': 'Joe', 'email': 'jane@example.com', 'team': 'af'}


def test_user_data_setter_rejects_a_non_dict_value(monkeypatch):
    view = _load_full_view(monkeypatch)

    with pytest.raises(ValueError):
        view.user_data = 'not a dict'


def test_show_initialises_the_gui_on_first_call(monkeypatch):
    monkeypatch.setattr(prefsview.pan_app, 'get_available_ui_languages', lambda: [])
    monkeypatch.setattr(prefsview.GLib, 'idle_add', lambda func, *args: None)
    view = PreferencesView.__new__(PreferencesView)
    main_window = Gtk.Window()
    controller = SimpleNamespace(
        main_controller=SimpleNamespace(view=SimpleNamespace(main_window=main_window)),
        update_prefs_gui_data=lambda: None,
    )
    view.controller = controller
    view._widgets = {}
    view.emit = lambda *args: None
    monkeypatch.setattr(prefsview.Gtk.Dialog, 'run', lambda self: Gtk.ResponseType.CLOSE)

    view.show()

    assert view._widgets  # _init_gui() populated it


def test_on_placeable_toggled_enables_the_parser(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    calls = []
    view.controller = SimpleNamespace(
        set_placeable_enabled=lambda parser, enabled: calls.append((parser, enabled)),
    )

    view._on_placeable_toggled(None, {'data': 'someparser', 'enabled': True})

    assert calls == [('someparser', True)]


def test_on_plugin_toggled_disables_the_plugin(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    calls = []
    view.controller = SimpleNamespace(
        set_plugin_enabled=lambda plugin_name, enabled: calls.append((plugin_name, enabled)),
    )

    view._on_plugin_toggled(None, {'data': {'internal_name': 'myplugin'}, 'enabled': False})

    assert calls == [('myplugin', False)]


def test_show_preferences_shows_the_dialog(monkeypatch):
    view = PreferencesView.__new__(PreferencesView)
    calls = []
    monkeypatch.setattr(view, 'show', lambda: calls.append(True))

    view._show_preferences('menuitem')

    assert calls == [True]
