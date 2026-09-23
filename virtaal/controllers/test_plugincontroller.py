#!/usr/bin/env python
#
# Copyright (C) Virtaal contributors.
#
# This file is part of Virtaal. It is distributed under the GPL2 or
# later license. See the LICENSE file for a copy of the license and
# the AUTHORS.md file for copyright and authorship information.

import builtins
import logging
import os
from types import SimpleNamespace

import pytest

from virtaal.controllers import plugincontroller
from virtaal.controllers.baseplugin import PluginUnsupported
from virtaal.controllers.plugincontroller import PluginController


def test_resourcepath_plugin_dir_construction(monkeypatch):
    """__init__() called .decode(sys.getfilesystemencoding()) on
    os.environ['RESOURCEPATH'] - a Python 2 idiom (os.environ values
    were bytes there) that raises AttributeError on Python 3, where
    they're already str. RESOURCEPATH is set on every macOS frozen
    launch (translate.misc.file_discovery checks the same var), so
    this crashed PluginController.__init__() there every time."""
    monkeypatch.setenv('RESOURCEPATH', '/tmp/fake_resources')

    # PLUGIN_DIRS is a class attribute that __init__() mutates in
    # place (self.PLUGIN_DIRS.insert(...), no reassignment) - restore
    # it so this test doesn't leave every later PluginController
    # instantiation with a stale extra entry.
    original_dirs = list(PluginController.PLUGIN_DIRS)
    try:
        pc = PluginController(controller=object(), classname='TestPlugin')
        assert pc.PLUGIN_DIRS[0] == os.path.join('/tmp/fake_resources', 'virtaal_plugins')
    finally:
        PluginController.PLUGIN_DIRS[:] = original_dirs


def _make_controller():
    pc = PluginController(controller=object(), classname='TestPlugin')
    pc.PLUGIN_MODULES = ['some.candidate.location']
    return pc


def test_get_plugin_class_stays_quiet_when_a_candidate_location_is_missing(monkeypatch, caplog):
    # Several candidate package locations are tried in turn (e.g. the
    # optional virtaal_plugins.* directory before the bundled
    # virtaal.plugins.* one) - one of them simply not existing at all
    # is expected, not an error worth logging.
    pc = _make_controller()
    real_import = builtins.__import__
    def fake_import(name, *a, **k):
        if name.startswith('some.candidate.location'):
            raise ModuleNotFoundError("No module named 'some'", name='some')
        return real_import(name, *a, **k)
    monkeypatch.setattr('builtins.__import__', fake_import)
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(Exception, match='Could not find plug-in'):
        pc._get_plugin_class('myplugin')

    assert not any('from ' in r.message and 'import' in r.message for r in caplog.records)


def test_get_plugin_class_logs_a_plugins_own_missing_dependency(monkeypatch, caplog):
    # e.g. _ipython_console needing the optional ipython package - a
    # real, existing plugin module whose own internal import fails,
    # not "no such plugin".
    pc = _make_controller()
    real_import = builtins.__import__
    def fake_import(name, *a, **k):
        if name.startswith('some.candidate.location'):
            raise ModuleNotFoundError("No module named 'ipython'", name='ipython')
        return real_import(name, *a, **k)
    monkeypatch.setattr('builtins.__import__', fake_import)
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(Exception, match='Could not find plug-in'):
        pc._get_plugin_class('myplugin')

    assert any('from ' in r.message and 'import' in r.message for r in caplog.records)


# __init__() / for_backend() #

def test_init_registers_itself_on_the_owning_controller_by_default():
    controller = SimpleNamespace()

    pc = PluginController(controller)

    assert controller.plugin_controller is pc


def test_init_prepends_the_windows_plugin_dir(monkeypatch):
    monkeypatch.setattr(plugincontroller.platform, 'is_windows', True)
    monkeypatch.setattr(plugincontroller.pan_app, 'main_dir', '/fake/main/dir')
    original_dirs = list(PluginController.PLUGIN_DIRS)
    try:
        pc = PluginController(controller=object(), classname='TestPlugin')
        assert pc.PLUGIN_DIRS[0] == os.path.join('/fake/main/dir', 'virtaal_plugins')
    finally:
        PluginController.PLUGIN_DIRS[:] = original_dirs


def test_for_backend_builds_a_specialized_controller():
    owner = object()
    get_disabled = lambda: []

    pc = PluginController.for_backend(owner, 'TMModel', 'tm', object, get_disabled,
                                       class_info_attribs=('display_name',))

    assert pc.controller is owner
    assert pc.PLUGIN_CLASSNAME == 'TMModel'
    assert pc.PLUGIN_CLASS_INFO_ATTRIBS == ['display_name']
    assert pc.PLUGIN_INTERFACE is object
    assert pc.PLUGIN_MODULES == ['virtaal_plugins.tm.models', 'virtaal.plugins.tm.models']
    assert pc.get_disabled_plugins is get_disabled
    assert all(d.endswith(os.path.join('tm', 'models')) for d in pc.PLUGIN_DIRS)


# disable_plugin() #

def test_disable_plugin_destroys_and_removes_it():
    pc = _make_controller()
    destroyed = []
    plugin = SimpleNamespace(destroy=lambda: destroyed.append(True))
    pc.plugins['myplugin'] = plugin
    pc.pluginmodules['myplugin'] = object()
    emitted = []
    pc.connect('plugin-disabled', lambda _pc, p: emitted.append(p))

    pc.disable_plugin('myplugin')

    assert destroyed == [True]
    assert emitted == [plugin]
    assert 'myplugin' not in pc.plugins
    assert 'myplugin' not in pc.pluginmodules


def test_disable_plugin_does_nothing_for_an_unknown_name():
    pc = _make_controller()

    pc.disable_plugin('nope')  # must not raise


# enable_plugin() #

def test_enable_plugin_returns_none_when_already_enabled():
    pc = _make_controller()
    pc.plugins['myplugin'] = object()

    assert pc.enable_plugin('myplugin') is None


def test_enable_plugin_constructs_and_registers_the_plugin_class():
    pc = _make_controller()
    created = []

    class FakePlugin:
        display_name = 'Fake'

        def __init__(self, name, controller):
            created.append((name, controller))

    pc._get_plugin_class = lambda name: FakePlugin
    emitted = []
    pc.connect('plugin-enabled', lambda _pc, p: emitted.append(p))

    result = pc.enable_plugin('myplugin')

    assert isinstance(result, FakePlugin)
    assert created == [('myplugin', pc.controller)]
    assert emitted == [result]
    assert pc.plugins['myplugin'] is result


def test_enable_plugin_returns_none_when_unsupported():
    pc = _make_controller()

    def _raise(name, controller):
        raise PluginUnsupported('no thanks')
    pc._get_plugin_class = lambda name: _raise

    assert pc.enable_plugin('myplugin') is None
    assert 'myplugin' not in pc.plugins


def test_enable_plugin_returns_none_and_logs_on_unexpected_error(caplog):
    pc = _make_controller()

    def _raise(name, controller):
        raise RuntimeError('boom')
    pc._get_plugin_class = lambda name: _raise

    with caplog.at_level(logging.ERROR):
        result = pc.enable_plugin('myplugin')

    assert result is None
    assert any('Failed to load plugin' in r.message for r in caplog.records)


# get_plugin_info() #

def test_get_plugin_info_collects_the_class_info_attribs():
    pc = _make_controller()

    class FakePlugin:
        display_name = 'Fake'
        description = 'A fake plugin'
        version = '1.0'
    pc._get_plugin_class = lambda name: FakePlugin

    assert pc.get_plugin_info('fake') == {
        'description': 'A fake plugin',
        'display_name': 'Fake',
        'version': '1.0',
    }


# load_plugins() #

def test_load_plugins_queues_only_the_enabled_ones(monkeypatch):
    pc = _make_controller()
    pc.get_disabled_plugins = lambda: ['skip_me']
    pc._find_plugin_names = lambda: ['a', 'skip_me', 'b']
    idle_calls = []
    monkeypatch.setattr(plugincontroller.GLib, 'idle_add', lambda func, name: idle_calls.append((func, name)))
    pc.plugins['stale'] = object()
    pc.pluginmodules['stale'] = object()

    pc.load_plugins()

    assert pc.plugins == {}
    assert pc.pluginmodules == {}
    assert [name for (_f, name) in idle_calls] == ['a', 'b']
    assert all(f == pc.enable_plugin for f, _name in idle_calls)


# shutdown() #

def test_shutdown_disables_every_loaded_plugin():
    pc = _make_controller()
    calls = []
    pc.disable_plugin = calls.append
    pc.plugins = {'a': object(), 'b': object()}

    pc.shutdown()

    assert set(calls) == {'a', 'b'}


# get_disabled_plugins() #

def test_get_disabled_plugins_reads_from_settings(monkeypatch):
    pc = _make_controller()
    monkeypatch.setattr(plugincontroller.pan_app.settings, 'plugin_state',
                         {'a': 'Enabled', 'b': 'Disabled', 'c': 'DISABLED'})

    assert set(pc.get_disabled_plugins()) == {'b', 'c'}


# _get_plugin_class() #

def test_get_plugin_class_returns_a_loaded_plugins_class():
    pc = _make_controller()

    class FakePlugin:
        pass
    pc.plugins['x'] = FakePlugin()

    assert pc._get_plugin_class('x') is FakePlugin


def test_get_plugin_class_imports_a_real_plugin_module():
    # _helloworld is a real, always-importable dev plugin - exercises
    # the real success path (import, class lookup, interface check,
    # module caching) without needing a synthetic module.
    pc = PluginController(controller=object(), classname='Plugin')

    plugin_class = pc._get_plugin_class('_helloworld')

    assert plugin_class.__name__ == 'Plugin'
    assert plugin_class.__module__ == 'virtaal.plugins._helloworld'
    assert pc.pluginmodules['_helloworld'].__name__ == 'virtaal.plugins._helloworld'


def test_get_plugin_class_rejects_a_class_not_implementing_the_interface():
    pc = PluginController(controller=object(), classname='Plugin')
    pc.PLUGIN_INTERFACE = int  # _helloworld.Plugin is not an int subclass

    with pytest.raises(Exception, match='not a valid plug-in class'):
        pc._get_plugin_class('_helloworld')


def test_get_plugin_class_raises_when_the_module_has_no_such_class():
    pc = PluginController(controller=object(), classname='NoSuchClass')

    with pytest.raises(Exception, match='has no class called'):
        pc._get_plugin_class('_helloworld')


# _find_plugin_names() #

def _make_plugin_package(tmp_path, monkeypatch, names):
    import sys
    import types
    for name in names:
        (tmp_path / f'{name}.py').write_text('')
    package = types.ModuleType('fake_plugin_package')
    package.__path__ = [str(tmp_path)]
    monkeypatch.setitem(sys.modules, 'fake_plugin_package', package)
    return package


def test_find_plugin_names_lists_real_submodules(tmp_path, monkeypatch):
    _make_plugin_package(tmp_path, monkeypatch, ['pluginone', 'plugintwo'])
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plugin_package']

    assert set(pc._find_plugin_names()) == {'pluginone', 'plugintwo'}


def test_find_plugin_names_skips_underscored_names_unless_debug(tmp_path, monkeypatch):
    _make_plugin_package(tmp_path, monkeypatch, ['visible', '_hidden'])
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plugin_package']
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', False)
    monkeypatch.setattr(plugincontroller.platform, 'is_frozen', False)

    assert pc._find_plugin_names() == ['visible']


def test_find_plugin_names_includes_underscored_names_in_debug(tmp_path, monkeypatch):
    _make_plugin_package(tmp_path, monkeypatch, ['visible', '_hidden'])
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plugin_package']
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    monkeypatch.setattr(plugincontroller.platform, 'is_frozen', False)

    assert set(pc._find_plugin_names()) == {'visible', '_hidden'}


def test_find_plugin_names_never_includes_underscored_names_when_frozen(tmp_path, monkeypatch):
    _make_plugin_package(tmp_path, monkeypatch, ['visible', '_hidden'])
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plugin_package']
    monkeypatch.setattr(plugincontroller.pan_app, 'DEBUG', True)
    monkeypatch.setattr(plugincontroller.platform, 'is_frozen', True)

    assert pc._find_plugin_names() == ['visible']


def test_find_plugin_names_skips_a_module_that_cannot_be_imported():
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['no.such.package.at.all']

    assert pc._find_plugin_names() == []


def test_find_plugin_names_skips_a_plain_module_with_no_path(monkeypatch):
    import sys
    import types
    plain_module = types.ModuleType('fake_plain_module')  # no __path__: not a package
    monkeypatch.setitem(sys.modules, 'fake_plain_module', plain_module)
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plain_module']

    assert pc._find_plugin_names() == []


def test_find_plugin_names_skips_wrongly_named_submodules(tmp_path, monkeypatch):
    _make_plugin_package(tmp_path, monkeypatch, ['real_plugin', 'test_not_a_plugin'])
    pc = _make_controller()
    pc.PLUGIN_MODULES = ['fake_plugin_package']

    assert pc._find_plugin_names() == ['real_plugin']


# _is_wrong_plugin_name() #

@pytest.mark.parametrize('name,expected', [
    ('.hidden', True),
    ('test_something', True),
    ('__pycache__', True),
    ('a_real_plugin', False),
])
def test_is_wrong_plugin_name(name, expected):
    assert PluginController._is_wrong_plugin_name(name) is expected
