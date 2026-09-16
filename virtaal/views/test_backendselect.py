#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from virtaal.views.backendselect import select_backends


class _FakeSelectDialog:
    """Stands in for a real SelectDialog - captures what it was built
    and run with, without touching GTK at all."""

    def __init__(self, title=None, message=None, parent=None, size=None):
        self.title = title
        self.message = message
        self.parent = parent
        self.size = size
        self.icon = None
        self.handlers = {}
        self.items = None

    def set_icon(self, icon):
        self.icon = icon

    def connect(self, signal_name, handler):
        self.handlers[signal_name] = handler

    def run(self, items=None):
        self.items = items


class _FakePlugin:
    def __init__(self, configure_func=None):
        self.configure_func = configure_func


class _FakePluginController:
    def __init__(self, plugin_names, infos, plugins=None):
        self._plugin_names = plugin_names
        self._infos = infos
        self.plugins = plugins or {}
        self.enabled = []
        self.disabled = []

    def _find_plugin_names(self):
        return self._plugin_names

    def get_plugin_info(self, name):
        return self._infos[name]

    def enable_plugin(self, name):
        self.enabled.append(name)

    def disable_plugin(self, name):
        self.disabled.append(name)


class _FakeMainWindow:
    def get_icon(self):
        return 'the-app-icon'


class _FakeMainController:
    class view:
        main_window = _FakeMainWindow()


def test_base_model_name_is_excluded_from_the_item_list(monkeypatch):
    pc = _FakePluginController(
        ['basemodel', 'realbackend'],
        {'realbackend': {'display_name': 'Real Backend', 'description': 'desc'}})
    captured = {}

    def fake_select_dialog(**kwargs):
        dlg = _FakeSelectDialog(**kwargs)
        captured['dlg'] = dlg
        return dlg
    monkeypatch.setattr('virtaal.views.widgets.selectdialog.SelectDialog', fake_select_dialog)

    select_backends(_FakeMainController(), pc, {'disabled_models': []}, 'basemodel',
                     title='Title', message='Message', size=(1, 2))

    names = [item['data']['internal_name'] for item in captured['dlg'].items]
    assert names == ['realbackend']


def test_item_config_is_the_configure_func_not_the_whole_plugin(monkeypatch):
    real_configure = lambda parent: None
    pc = _FakePluginController(
        ['backend1'],
        {'backend1': {'display_name': 'Backend 1', 'description': 'desc'}},
        plugins={'backend1': _FakePlugin(configure_func=real_configure)})
    captured = {}

    def fake_select_dialog(**kwargs):
        dlg = _FakeSelectDialog(**kwargs)
        captured['dlg'] = dlg
        return dlg
    monkeypatch.setattr('virtaal.views.widgets.selectdialog.SelectDialog', fake_select_dialog)

    select_backends(_FakeMainController(), pc, {'disabled_models': []}, 'basemodel',
                     title='Title', message='Message', size=(1, 2))

    items = captured['dlg'].items
    assert len(items) == 1
    assert items[0]['config'] is real_configure


def test_disabled_backend_has_no_config_even_with_a_configure_func(monkeypatch):
    pc = _FakePluginController(
        ['backend1'],
        {'backend1': {'display_name': 'Backend 1', 'description': 'desc'}},
        plugins={})  # not enabled
    captured = {}

    def fake_select_dialog(**kwargs):
        dlg = _FakeSelectDialog(**kwargs)
        captured['dlg'] = dlg
        return dlg
    monkeypatch.setattr('virtaal.views.widgets.selectdialog.SelectDialog', fake_select_dialog)

    select_backends(_FakeMainController(), pc, {'disabled_models': []}, 'basemodel',
                     title='Title', message='Message', size=(1, 2))

    items = captured['dlg'].items
    assert items[0]['enabled'] is False
    assert items[0]['config'] is None


def test_item_enabled_removes_the_backend_from_disabled_models(monkeypatch):
    pc = _FakePluginController(['backend1'], {'backend1': {'display_name': 'B', 'description': 'd'}})
    captured = {}

    def fake_select_dialog(**kwargs):
        dlg = _FakeSelectDialog(**kwargs)
        captured['dlg'] = dlg
        return dlg
    monkeypatch.setattr('virtaal.views.widgets.selectdialog.SelectDialog', fake_select_dialog)
    config = {'disabled_models': ['backend1']}

    select_backends(_FakeMainController(), pc, config, 'basemodel',
                     title='Title', message='Message', size=(1, 2))
    item = captured['dlg'].items[0]
    captured['dlg'].handlers['item-enabled'](captured['dlg'], item)

    assert 'backend1' in pc.enabled
    assert 'backend1' not in config['disabled_models']


def test_item_disabled_adds_the_backend_to_disabled_models(monkeypatch):
    pc = _FakePluginController(
        ['backend1'], {'backend1': {'display_name': 'B', 'description': 'd'}},
        plugins={'backend1': _FakePlugin()})
    captured = {}

    def fake_select_dialog(**kwargs):
        dlg = _FakeSelectDialog(**kwargs)
        captured['dlg'] = dlg
        return dlg
    monkeypatch.setattr('virtaal.views.widgets.selectdialog.SelectDialog', fake_select_dialog)
    config = {'disabled_models': []}

    select_backends(_FakeMainController(), pc, config, 'basemodel',
                     title='Title', message='Message', size=(1, 2))
    item = captured['dlg'].items[0]
    captured['dlg'].handlers['item-disabled'](captured['dlg'], item)

    assert 'backend1' in pc.disabled
    assert 'backend1' in config['disabled_models']
