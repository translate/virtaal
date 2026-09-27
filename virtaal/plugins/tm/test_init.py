#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest

import virtaal.plugins.tm as tm_module
from virtaal.plugins.tm import Plugin


@pytest.fixture(autouse=True)
def isolated_config_dir(monkeypatch, tmp_path):
    # This machine's real ~/.virtaal config already has a [tm] section
    # from prior real app use - isolate every test in this file from it.
    monkeypatch.setattr('virtaal.common.pan_app.get_config_dir', lambda: str(tmp_path))
    return tmp_path


def _init(monkeypatch, main_controller=None):
    captured = {}

    class FakeTMController:
        def __init__(self, main_controller, config):
            captured['main_controller'] = main_controller
            captured['config'] = config

    monkeypatch.setattr(tm_module, 'TMController', FakeTMController)
    plugin = Plugin('tm', main_controller or SimpleNamespace())
    return plugin, captured


def test_init_plugin_parses_the_default_config(monkeypatch):
    main_controller = SimpleNamespace()

    plugin, captured = _init(monkeypatch, main_controller)

    assert plugin.internal_name == 'tm'
    assert plugin.main_controller is main_controller
    assert plugin.configure_func == plugin.configure
    assert captured['main_controller'] is main_controller
    assert captured['config']['disabled_models'] == [
        '_dummytm', 'remotetm', 'apertium', 'google_translate', 'moses']
    assert captured['config']['max_matches'] == 5
    assert captured['config']['min_quality'] == 70


def test_init_plugin_loads_and_coerces_an_overridden_config(monkeypatch, isolated_config_dir):
    (isolated_config_dir / Plugin.CONFIG_FILENAME).write_text(
        '[tm]\nmax_matches = 3\ndisabled_models = apertium\n')

    _plugin, captured = _init(monkeypatch)

    assert captured['config']['max_matches'] == 3
    assert captured['config']['disabled_models'] == ['apertium']
    assert captured['config']['min_quality'] == 70  # not overridden - falls back to the default


def test_destroy_saves_config_and_delegates_to_the_controller(monkeypatch):
    plugin, _captured = _init(monkeypatch)
    saved = []
    monkeypatch.setattr(plugin, 'save_config', lambda: saved.append(True))
    plugin.controller.destroy = lambda: saved.append('controller')

    plugin.destroy()

    assert saved == [True, 'controller']
