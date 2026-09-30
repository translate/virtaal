#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

from types import SimpleNamespace

import pytest

import virtaal.plugins.terminology as terminology_module
from virtaal.plugins.terminology import Plugin


@pytest.fixture(autouse=True)
def isolated_config_dir(monkeypatch, tmp_path):
    # This machine's real ~/.virtaal config already has a [terminology]
    # section from prior real app use - isolate every test here from it.
    monkeypatch.setattr('virtaal.common.pan_app.get_config_dir', lambda: str(tmp_path))
    return tmp_path


def _init(monkeypatch, main_controller=None):
    captured = {}

    class FakeTerminologyController:
        def __init__(self, main_controller, config):
            captured['main_controller'] = main_controller
            captured['config'] = config

    monkeypatch.setattr(terminology_module, 'TerminologyController', FakeTerminologyController)
    plugin = Plugin('terminology', main_controller or SimpleNamespace())
    return plugin, captured


def test_init_plugin_parses_the_default_config(monkeypatch):
    main_controller = SimpleNamespace()

    plugin, captured = _init(monkeypatch, main_controller)

    assert plugin.internal_name == 'terminology'
    assert plugin.main_controller is main_controller
    assert plugin.configure_func == plugin.configure
    assert captured['main_controller'] is main_controller
    assert captured['config']['disabled_models'] == ['autoterm']
    assert captured['config']['max_matches'] == 5
    assert captured['config']['min_quality'] == 70
    assert captured['config']['backends_dialog_width'] == 400


def test_init_plugin_loads_and_coerces_an_overridden_config(monkeypatch, isolated_config_dir):
    (isolated_config_dir / Plugin.CONFIG_FILENAME).write_text(
        '[terminology]\nbackends_dialog_width = 250\nmax_matches = 2\n')

    _plugin, captured = _init(monkeypatch)

    assert captured['config']['backends_dialog_width'] == 250
    assert captured['config']['max_matches'] == 2
    assert captured['config']['disabled_models'] == ['autoterm']  # not overridden


def test_init_plugin_force_disables_autoterm_despite_a_stale_saved_config(monkeypatch, isolated_config_dir):
    # A profile saved before autoterm's dead URL was disabled by
    # default has its own, older disabled_models value on disk -
    # config loading must not let that silently re-enable it.
    (isolated_config_dir / Plugin.CONFIG_FILENAME).write_text(
        '[terminology]\ndisabled_models = localfile\n')

    _plugin, captured = _init(monkeypatch)

    assert 'autoterm' in captured['config']['disabled_models']
    assert 'localfile' in captured['config']['disabled_models']


def test_destroy_saves_config_and_delegates_to_the_controller(monkeypatch):
    plugin, _captured = _init(monkeypatch)
    saved = []
    monkeypatch.setattr(plugin, 'save_config', lambda: saved.append(True))
    plugin.controller.destroy = lambda: saved.append('controller')

    plugin.destroy()

    assert saved == [True, 'controller']
