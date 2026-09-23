#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.common import pan_app
from virtaal.controllers.prefscontroller import PreferencesController


class _FakeSettings:
    def __init__(self, uilang=''):
        self.language = {'sourcefont': '', 'targetfont': '', 'uilang': uilang}
        self.translator = {'name': '', 'email': '', 'team': ''}
        self.placeable_state = {}
        self.plugin_state = {}


class _FakeUnitControllerView:
    def update_languages(self):
        pass


class _FakeMainControllerView:
    def __init__(self):
        self.language_change_notices = 0

    def show_language_change_notice(self):
        self.language_change_notices += 1


class _FakeMainController:
    def __init__(self):
        self.unit_controller = type('_UC', (), {'view': _FakeUnitControllerView()})()
        self.view = _FakeMainControllerView()


class _FakeView:
    def __init__(self, ui_language):
        self.font_data = {'source': '', 'target': ''}
        self.user_data = {'name': '', 'email': '', 'team': ''}
        self.ui_language = ui_language


def _make_controller(monkeypatch, saved_uilang):
    monkeypatch.setattr(pan_app, 'settings', _FakeSettings(uilang=saved_uilang))
    controller = PreferencesController.__new__(PreferencesController)
    controller.main_controller = _FakeMainController()
    return controller


def test_prefs_done_saves_a_changed_ui_language(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert pan_app.settings.language['uilang'] == 'af'


def test_prefs_done_shows_a_restart_notice_when_the_language_changed(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert controller.main_controller.view.language_change_notices == 1


def test_prefs_done_does_nothing_when_the_language_is_unchanged(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='af')

    controller._on_prefs_done(_FakeView(ui_language='af'))

    assert pan_app.settings.language['uilang'] == 'af'
    assert controller.main_controller.view.language_change_notices == 0


def test_update_language_gui_data_reads_the_saved_setting(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='fr')
    controller.view = _FakeView(ui_language='')

    controller._update_language_gui_data()

    assert controller.view.ui_language == 'fr'


class _FakeViewSignal:
    def __init__(self, controller):
        self.controller = controller
        self.connected = None

    def connect(self, signal, handler):
        self.connected = (signal, handler)


def test_init_creates_and_connects_the_view(monkeypatch):
    monkeypatch.setattr('virtaal.views.prefsview.PreferencesView', _FakeViewSignal)
    main_controller = type('_MC', (), {
        'placeables_controller': object(),
        'plugin_controller': object(),
    })()

    controller = PreferencesController(main_controller)

    assert controller.view.controller is controller
    assert controller.view.connected == ('prefs-done', controller._on_prefs_done)


class _FakePlaceablesController:
    def __init__(self):
        self.added = []
        self.removed = []
        self.parser_info = {}
        self.parsers = []

    def add_parsers(self, parser):
        self.added.append(parser)

    def remove_parsers(self, parser):
        self.removed.append(parser)


def _bare_controller(monkeypatch, saved_uilang=''):
    controller = _make_controller(monkeypatch, saved_uilang)
    controller.placeables_controller = _FakePlaceablesController()
    return controller


class _FakeParser:
    # Placeable parsers are classmethods, so `parser.__self__` is the
    # class itself (which has a `__name__`), not an instance.
    @classmethod
    def parse(cls):
        pass


def test_set_placeable_enabled_adds_the_parser_when_enabled(monkeypatch):
    controller = _bare_controller(monkeypatch)
    parser = _FakeParser.parse

    controller.set_placeable_enabled(parser, enabled=True)

    assert controller.placeables_controller.added == [parser]
    assert pan_app.settings.placeable_state['_fakeparser'] == 'enabled'


def test_set_placeable_enabled_removes_the_parser_when_not_enabled(monkeypatch):
    controller = _bare_controller(monkeypatch)
    parser = _FakeParser.parse

    controller.set_placeable_enabled(parser, enabled=False)

    assert controller.placeables_controller.removed == [parser]
    assert pan_app.settings.placeable_state['_fakeparser'] == 'disabled'


class _FakePluginController:
    def __init__(self):
        self.enabled = []
        self.disabled = []
        self.plugins = {}

    def enable_plugin(self, name):
        self.enabled.append(name)

    def disable_plugin(self, name):
        self.disabled.append(name)

    def _find_plugin_names(self):
        return []


def _controller_with_plugins(monkeypatch, saved_uilang=''):
    controller = _make_controller(monkeypatch, saved_uilang)
    controller.placeables_controller = _FakePlaceablesController()
    controller.plugin_controller = _FakePluginController()
    controller.view = _FakeView(ui_language='')
    return controller


def test_set_plugin_enabled_enables_the_plugin(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)

    controller.set_plugin_enabled('myplugin', enabled=True)

    assert controller.plugin_controller.enabled == ['myplugin']
    assert pan_app.settings.plugin_state['myplugin'] == 'enabled'


def test_set_plugin_enabled_disables_the_plugin(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)

    controller.set_plugin_enabled('myplugin', enabled=False)

    assert controller.plugin_controller.disabled == ['myplugin']
    assert pan_app.settings.plugin_state['myplugin'] == 'disabled'


def test_update_config_plugin_state_refreshes_the_prefs_gui(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)
    calls = []
    monkeypatch.setattr(controller, 'update_prefs_gui_data', lambda: calls.append(True))

    controller.update_config_plugin_state('myplugin', disabled=False)

    assert calls == [True]


def test_update_prefs_gui_data_refreshes_every_section(monkeypatch):
    controller = _bare_controller(monkeypatch)
    controller.plugin_controller = _FakePluginController()
    controller.view = _FakeView(ui_language='')
    calls = []
    for name in ('_update_font_gui_data', '_update_language_gui_data',
                 '_update_placeables_gui_data', '_update_plugin_gui_data',
                 '_update_user_gui_data'):
        monkeypatch.setattr(controller, name, lambda name=name: calls.append(name))

    controller.update_prefs_gui_data()

    assert calls == ['_update_font_gui_data', '_update_language_gui_data',
                      '_update_placeables_gui_data', '_update_plugin_gui_data',
                      '_update_user_gui_data']


def test_update_font_gui_data_reads_the_saved_fonts(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')
    pan_app.settings.language['sourcefont'] = 'Sans 10'
    pan_app.settings.language['targetfont'] = 'Serif 12'
    controller.view = _FakeView(ui_language='')

    controller._update_font_gui_data()

    assert controller.view.font_data == {'source': 'Sans 10', 'target': 'Serif 12'}


def test_update_user_gui_data_reads_the_saved_translator_details(monkeypatch):
    controller = _make_controller(monkeypatch, saved_uilang='')
    pan_app.settings.translator.update(name='Jane', email='jane@example.com', team='af')
    controller.view = _FakeView(ui_language='')

    controller._update_user_gui_data()

    assert controller.view.user_data == {'name': 'Jane', 'email': 'jane@example.com', 'team': 'af'}


def test_update_placeables_gui_data_marks_currently_active_parsers_as_enabled(monkeypatch):
    controller = _bare_controller(monkeypatch)
    controller.view = _FakeView(ui_language='')
    parser_a, parser_b = (lambda: None), (lambda: None)
    controller.placeables_controller.parser_info = {
        parser_a: ('B name', 'b desc'),
        parser_b: ('A name', 'a desc'),
    }
    controller.placeables_controller.parsers = [parser_b]

    controller._update_placeables_gui_data()

    assert controller.view.placeables_data == [
        {'name': 'A name', 'desc': 'a desc', 'enabled': True, 'data': parser_b},
        {'name': 'B name', 'desc': 'b desc', 'enabled': False, 'data': parser_a},
    ]


class _Plugin:
    def __init__(self, display_name, description, configure_func=None):
        self.display_name = display_name
        self.description = description
        self.configure_func = configure_func


def test_update_plugin_gui_data_marks_a_loaded_plugin_as_enabled(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)
    controller.plugin_controller._find_plugin_names = lambda: ['loaded']
    controller.plugin_controller.plugins = {'loaded': _Plugin('Loaded', 'desc', configure_func='cfg')}

    controller._update_plugin_gui_data()

    assert controller.view.plugin_data == [
        {'name': 'Loaded', 'desc': 'desc', 'enabled': True,
         'data': {'internal_name': 'loaded'}, 'config': 'cfg'},
    ]


def test_update_plugin_gui_data_marks_an_unloaded_plugin_as_disabled(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)
    controller.plugin_controller._find_plugin_names = lambda: ['unloaded']
    controller.plugin_controller.get_plugin_info = lambda name: {
        'display_name': 'Unloaded', 'description': 'desc',
    }

    controller._update_plugin_gui_data()

    assert controller.view.plugin_data == [
        {'name': 'Unloaded', 'desc': 'desc', 'enabled': False,
         'data': {'internal_name': 'unloaded'}, 'config': None},
    ]


def test_update_plugin_gui_data_skips_a_plugin_whose_info_raises(monkeypatch):
    controller = _controller_with_plugins(monkeypatch)
    controller.plugin_controller._find_plugin_names = lambda: ['broken']

    def _raise(name):
        raise Exception('boom')
    controller.plugin_controller.get_plugin_info = _raise

    controller._update_plugin_gui_data()

    assert controller.view.plugin_data == []
