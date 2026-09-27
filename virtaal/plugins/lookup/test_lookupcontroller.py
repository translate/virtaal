#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

from virtaal.plugins.lookup.lookupcontroller import LookupController


def _bare_controller(**kwargs):
    controller = LookupController.__new__(LookupController)
    for key, value in kwargs.items():
        setattr(controller, key, value)
    return controller


def test_init_builds_the_disabled_model_list_and_loads_plugins(monkeypatch):
    monkeypatch.setattr(
        'virtaal.plugins.lookup.lookupcontroller.LookupView', lambda controller: SimpleNamespace())
    captured = {}

    def fake_for_backend(owner, classname, category, interface, get_disabled):
        captured['args'] = (owner, classname, category, interface, get_disabled)
        return SimpleNamespace(load_plugins=lambda: captured.setdefault('loaded', True))
    monkeypatch.setattr(
        'virtaal.controllers.plugincontroller.PluginController.for_backend', fake_for_backend)

    plugin = SimpleNamespace(main_controller=object())
    config = {'disabled_models': ['weblookup']}

    controller = LookupController(plugin, config)

    assert controller.main_controller is plugin.main_controller
    assert controller.plugin is plugin
    assert controller.disabled_model_names == ['baselookupmodel', 'weblookup']
    owner, classname, category, _interface, get_disabled = captured['args']
    assert (owner, classname, category) == (controller, 'LookupModel', 'lookup')
    assert get_disabled() == ['baselookupmodel', 'weblookup']
    assert captured['loaded'] is True


def test_init_defaults_disabled_models_to_empty_when_not_configured(monkeypatch):
    monkeypatch.setattr(
        'virtaal.plugins.lookup.lookupcontroller.LookupView', lambda controller: SimpleNamespace())
    monkeypatch.setattr(
        'virtaal.controllers.plugincontroller.PluginController.for_backend',
        lambda *a: SimpleNamespace(load_plugins=lambda: None))

    controller = LookupController(SimpleNamespace(main_controller=object()), {})

    assert controller.disabled_model_names == ['baselookupmodel']


def test_destroy_destroys_the_view_and_shuts_down_the_plugin_controller():
    calls = []
    controller = _bare_controller(
        view=SimpleNamespace(destroy=lambda: calls.append('view')),
        plugin_controller=SimpleNamespace(shutdown=lambda: calls.append('plugins')),
    )

    controller.destroy()

    assert calls == ['view', 'plugins']
